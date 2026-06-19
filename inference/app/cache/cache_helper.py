import json
import asyncio
import logging
import time
from typing import Any, Optional, Dict, TypeVar, Generic, Callable, Awaitable

from .base import (
    CacheConfig,
    CacheResult,
    CacheStatus,
    FallbackReason,
    OperationType,
    DEFAULT_TTL,
)
from .connection import EnhancedRedisConnection
from .observability import CacheOperationTimer, get_cache_logger

T = TypeVar("T")

logger = logging.getLogger(__name__)


class CacheHelper(Generic[T]):
    def __init__(
        self,
        redis_conn: EnhancedRedisConnection,
        config: Optional[CacheConfig] = None,
        namespace: str = "default",
    ):
        self.redis_conn = redis_conn
        self.config = config or CacheConfig()
        self.namespace = namespace or self.config.namespace
        self._cache_logger = get_cache_logger()
        self._memory_fallback: Dict[str, tuple] = {}

    async def get(
        self,
        key: str,
        deserializer: Optional[Callable[[str], T]] = None,
    ) -> CacheResult[T]:
        timer = CacheOperationTimer(
            cache_key=key,
            operation=OperationType.GET,
            namespace=self.namespace,
        )

        if not self.redis_conn.is_available():
            result = self._memory_get(key, deserializer)
            if result.status == CacheStatus.HIT:
                ctx = timer.record(CacheStatus.FALLBACK, FallbackReason.REDIS_UNAVAILABLE)
                result.fallback_reason = FallbackReason.REDIS_UNAVAILABLE
                result.status = CacheStatus.FALLBACK
                result.latency_ms = ctx.latency_ms
            else:
                ctx = timer.record(CacheStatus.FALLBACK, FallbackReason.REDIS_UNAVAILABLE)
                result.fallback_reason = FallbackReason.REDIS_UNAVAILABLE
                result.latency_ms = ctx.latency_ms
            return result

        last_error = None
        for attempt in range(self.config.max_retries):
            timer.retry_count = attempt
            try:
                redis = self.redis_conn.get_client()
                if not redis:
                    raise RuntimeError("Redis client is None")

                value_str = await redis.get(key)

                if value_str is None:
                    ctx = timer.record(CacheStatus.MISS)
                    return CacheResult(
                        value=None,
                        status=CacheStatus.MISS,
                        latency_ms=ctx.latency_ms,
                        retry_count=attempt,
                    )

                if deserializer:
                    value = deserializer(value_str)
                else:
                    try:
                        value = json.loads(value_str)
                    except json.JSONDecodeError:
                        value = value_str

                ttl_remaining = await redis.ttl(key)

                timer.value_size = len(value_str) if isinstance(value_str, (str, bytes)) else None
                ctx = timer.record(CacheStatus.HIT)
                return CacheResult(
                    value=value,
                    status=CacheStatus.HIT,
                    latency_ms=ctx.latency_ms,
                    retry_count=attempt,
                    ttl_remaining=ttl_remaining if ttl_remaining > 0 else None,
                )

            except asyncio.CancelledError:
                timer.record(CacheStatus.ERROR, error_message="Operation cancelled")
                raise
            except Exception as e:
                last_error = str(e)
                logger.debug(f"Cache get attempt {attempt + 1} failed for key {key}: {e}")
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(self.config.retry_delay * (2 ** attempt))

        if self.config.enable_fallback:
            result = self._memory_get(key, deserializer)
            ctx = timer.record(CacheStatus.FALLBACK, FallbackReason.CONNECTION_ERROR)
            result.fallback_reason = FallbackReason.CONNECTION_ERROR
            result.status = CacheStatus.FALLBACK
            result.latency_ms = ctx.latency_ms
            return result

        ctx = timer.record(CacheStatus.ERROR, error_message=last_error)
        return CacheResult(
            value=None,
            status=CacheStatus.ERROR,
            fallback_reason=FallbackReason.CONNECTION_ERROR,
            latency_ms=ctx.latency_ms,
            retry_count=self.config.max_retries,
        )

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        serializer: Optional[Callable[[Any], str]] = None,
    ) -> CacheResult[bool]:
        timer = CacheOperationTimer(
            cache_key=key,
            operation=OperationType.SET,
            namespace=self.namespace,
        )
        timer.ttl = ttl or self.config.ttl

        effective_ttl = ttl if ttl is not None else self.config.ttl

        try:
            if serializer:
                value_str = serializer(value)
            elif isinstance(value, (dict, list, tuple)):
                value_str = json.dumps(value)
            elif isinstance(value, str):
                value_str = value
            else:
                value_str = str(value)
        except Exception as e:
            ctx = timer.record(CacheStatus.ERROR, FallbackReason.SERIALIZATION_ERROR, str(e))
            return CacheResult(
                value=False,
                status=CacheStatus.ERROR,
                fallback_reason=FallbackReason.SERIALIZATION_ERROR,
                latency_ms=ctx.latency_ms,
            )

        timer.value_size = len(value_str)

        if self.redis_conn.is_available():
            last_error = None
            for attempt in range(self.config.max_retries):
                timer.retry_count = attempt
                try:
                    redis = self.redis_conn.get_client()
                    if not redis:
                        raise RuntimeError("Redis client is None")

                    await redis.set(key, value_str, ex=effective_ttl)

                    if self.config.enable_fallback:
                        self._memory_set(key, value, effective_ttl)

                    ctx = timer.record(CacheStatus.HIT)
                    return CacheResult(
                        value=True,
                        status=CacheStatus.HIT,
                        latency_ms=ctx.latency_ms,
                        retry_count=attempt,
                    )
                except asyncio.CancelledError:
                    timer.record(CacheStatus.ERROR, error_message="Operation cancelled")
                    raise
                except Exception as e:
                    last_error = str(e)
                    logger.debug(f"Cache set attempt {attempt + 1} failed for key {key}: {e}")
                    if attempt < self.config.max_retries - 1:
                        await asyncio.sleep(self.config.retry_delay * (2 ** attempt))

        if self.config.enable_fallback:
            self._memory_set(key, value, effective_ttl)
            ctx = timer.record(CacheStatus.FALLBACK, FallbackReason.REDIS_UNAVAILABLE)
            return CacheResult(
                value=True,
                status=CacheStatus.FALLBACK,
                fallback_reason=FallbackReason.REDIS_UNAVAILABLE,
                latency_ms=ctx.latency_ms,
            )

        ctx = timer.record(CacheStatus.ERROR, error_message=last_error)
        return CacheResult(
            value=False,
            status=CacheStatus.ERROR,
            fallback_reason=FallbackReason.CONNECTION_ERROR,
            latency_ms=ctx.latency_ms,
            retry_count=self.config.max_retries,
        )

    async def delete(self, key: str) -> CacheResult[bool]:
        timer = CacheOperationTimer(
            cache_key=key,
            operation=OperationType.DELETE,
            namespace=self.namespace,
        )

        if self.redis_conn.is_available():
            last_error = None
            for attempt in range(self.config.max_retries):
                timer.retry_count = attempt
                try:
                    redis = self.redis_conn.get_client()
                    if not redis:
                        raise RuntimeError("Redis client is None")

                    await redis.delete(key)

                    if key in self._memory_fallback:
                        del self._memory_fallback[key]

                    ctx = timer.record(CacheStatus.HIT)
                    return CacheResult(
                        value=True,
                        status=CacheStatus.HIT,
                        latency_ms=ctx.latency_ms,
                        retry_count=attempt,
                    )
                except asyncio.CancelledError:
                    timer.record(CacheStatus.ERROR, error_message="Operation cancelled")
                    raise
                except Exception as e:
                    last_error = str(e)
                    logger.debug(f"Cache delete attempt {attempt + 1} failed for key {key}: {e}")
                    if attempt < self.config.max_retries - 1:
                        await asyncio.sleep(self.config.retry_delay * (2 ** attempt))

        if key in self._memory_fallback:
            del self._memory_fallback[key]

        if self.config.enable_fallback and not self.redis_conn.is_available():
            ctx = timer.record(CacheStatus.FALLBACK, FallbackReason.REDIS_UNAVAILABLE)
            return CacheResult(
                value=True,
                status=CacheStatus.FALLBACK,
                fallback_reason=FallbackReason.REDIS_UNAVAILABLE,
                latency_ms=ctx.latency_ms,
            )

        ctx = timer.record(CacheStatus.ERROR, error_message=last_error)
        return CacheResult(
            value=False,
            status=CacheStatus.ERROR,
            fallback_reason=FallbackReason.CONNECTION_ERROR,
            latency_ms=ctx.latency_ms,
            retry_count=self.config.max_retries,
        )

    async def get_or_set(
        self,
        key: str,
        fetch_func: Callable[[], Awaitable[T]],
        ttl: Optional[int] = None,
        deserializer: Optional[Callable[[str], T]] = None,
        serializer: Optional[Callable[[T], str]] = None,
    ) -> CacheResult[T]:
        cache_result = await self.get(key, deserializer)

        if cache_result.hit:
            return cache_result

        try:
            value = await fetch_func()
        except Exception as e:
            logger.error(f"Failed to fetch value for cache key {key}: {e}")
            raise

        await self.set(key, value, ttl, serializer)

        return CacheResult(
            value=value,
            status=CacheStatus.MISS,
            latency_ms=cache_result.latency_ms,
        )

    def _memory_get(
        self,
        key: str,
        deserializer: Optional[Callable[[str], T]] = None,
    ) -> CacheResult[T]:
        if key in self._memory_fallback:
            value, expire_time = self._memory_fallback[key]
            if time.time() < expire_time:
                return CacheResult(value=value, status=CacheStatus.HIT)
            else:
                del self._memory_fallback[key]
        return CacheResult(value=None, status=CacheStatus.MISS)

    def _memory_set(self, key: str, value: Any, ttl: int) -> None:
        expire_time = time.time() + ttl
        self._memory_fallback[key] = (value, expire_time)
        self._cleanup_memory()

    def _cleanup_memory(self) -> None:
        if len(self._memory_fallback) > 1000:
            now = time.time()
            expired_keys = [k for k, (_, exp) in self._memory_fallback.items() if exp <= now]
            for k in expired_keys:
                del self._memory_fallback[k]
