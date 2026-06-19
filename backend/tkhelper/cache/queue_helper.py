import json
import asyncio
import logging
import time
from typing import Any, Optional, List, Dict, TypeVar, Generic, Callable

from .base import (
    QueueConfig,
    QueueResult,
    CacheStatus,
    FallbackReason,
    OperationType,
    DEFAULT_MAX_RETRIES,
    DEFAULT_RETRY_DELAY,
)
from .connection import EnhancedRedisConnection
from .observability import CacheOperationTimer, get_cache_logger

T = TypeVar("T")

logger = logging.getLogger(__name__)


class QueueHelper(Generic[T]):
    def __init__(
        self,
        redis_conn: EnhancedRedisConnection,
        queue_name: str,
        config: Optional[QueueConfig] = None,
        namespace: str = "default",
    ):
        self.redis_conn = redis_conn
        self.queue_name = queue_name
        self.config = config or QueueConfig()
        self.namespace = namespace or self.config.namespace
        self._cache_logger = get_cache_logger()
        self._fallback_queue: List = []
        self._processing_items: List = []

    async def push(
        self,
        item: Any,
        serializer: Optional[Callable[[Any], str]] = None,
    ) -> QueueResult[int]:
        timer = CacheOperationTimer(
            cache_key=self.queue_name,
            operation=OperationType.PUSH,
            namespace=self.namespace,
        )

        try:
            if serializer:
                item_str = serializer(item)
            elif isinstance(item, (dict, list, tuple)):
                item_str = json.dumps(item)
            elif isinstance(item, str):
                item_str = item
            else:
                item_str = str(item)
        except Exception as e:
            ctx = timer.record(CacheStatus.ERROR, FallbackReason.SERIALIZATION_ERROR, str(e))
            return QueueResult(
                items=[],
                status=CacheStatus.ERROR,
                fallback_reason=FallbackReason.SERIALIZATION_ERROR,
                latency_ms=ctx.latency_ms,
            )

        timer.value_size = len(item_str)

        if self.redis_conn.is_available():
            last_error = None
            for attempt in range(self.config.max_retries):
                timer.retry_count = attempt
                try:
                    redis = self.redis_conn.get_client()
                    if not redis:
                        raise RuntimeError("Redis client is None")

                    length = await redis.rpush(self.queue_name, item_str)

                    if self.config.max_size and length > self.config.max_size:
                        await redis.ltrim(self.queue_name, -self.config.max_size, -1)
                        length = self.config.max_size

                    if self.config.enable_fallback:
                        self._fallback_queue.append(item)

                    ctx = timer.record(CacheStatus.HIT)
                    return QueueResult(
                        items=[item],
                        status=CacheStatus.HIT,
                        latency_ms=ctx.latency_ms,
                        retry_count=attempt,
                        queue_length=length,
                    )
                except asyncio.CancelledError:
                    timer.record(CacheStatus.ERROR, error_message="Operation cancelled")
                    raise
                except Exception as e:
                    last_error = str(e)
                    logger.debug(f"Queue push attempt {attempt + 1} failed: {e}")
                    if attempt < self.config.max_retries - 1:
                        await asyncio.sleep(self.config.retry_delay * (2 ** attempt))

        if self.config.enable_fallback:
            self._fallback_queue.append(item)
            ctx = timer.record(CacheStatus.FALLBACK, FallbackReason.REDIS_UNAVAILABLE)
            return QueueResult(
                items=[item],
                status=CacheStatus.FALLBACK,
                fallback_reason=FallbackReason.REDIS_UNAVAILABLE,
                latency_ms=ctx.latency_ms,
                queue_length=len(self._fallback_queue),
            )

        ctx = timer.record(CacheStatus.ERROR, error_message=last_error)
        return QueueResult(
            items=[],
            status=CacheStatus.ERROR,
            fallback_reason=FallbackReason.CONNECTION_ERROR,
            latency_ms=ctx.latency_ms,
            retry_count=self.config.max_retries,
        )

    async def pop(
        self,
        deserializer: Optional[Callable[[str], T]] = None,
        timeout: int = 0,
    ) -> QueueResult[T]:
        timer = CacheOperationTimer(
            cache_key=self.queue_name,
            operation=OperationType.POP,
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

                    if timeout > 0:
                        result = await redis.blpop(self.queue_name, timeout=timeout)
                        if result is None:
                            ctx = timer.record(CacheStatus.MISS)
                            return QueueResult(
                                items=[],
                                status=CacheStatus.MISS,
                                latency_ms=ctx.latency_ms,
                                retry_count=attempt,
                            )
                        _, item_str = result
                    else:
                        item_str = await redis.lpop(self.queue_name)
                        if item_str is None:
                            ctx = timer.record(CacheStatus.MISS)
                            return QueueResult(
                                items=[],
                                status=CacheStatus.MISS,
                                latency_ms=ctx.latency_ms,
                                retry_count=attempt,
                            )

                    if deserializer:
                        item = deserializer(item_str)
                    else:
                        try:
                            item = json.loads(item_str)
                        except json.JSONDecodeError:
                            item = item_str

                    length = await redis.llen(self.queue_name)

                    ctx = timer.record(CacheStatus.HIT)
                    return QueueResult(
                        items=[item],
                        status=CacheStatus.HIT,
                        latency_ms=ctx.latency_ms,
                        retry_count=attempt,
                        queue_length=length,
                    )
                except asyncio.CancelledError:
                    timer.record(CacheStatus.ERROR, error_message="Operation cancelled")
                    raise
                except Exception as e:
                    last_error = str(e)
                    logger.debug(f"Queue pop attempt {attempt + 1} failed: {e}")
                    if attempt < self.config.max_retries - 1:
                        await asyncio.sleep(self.config.retry_delay * (2 ** attempt))

        if self.config.enable_fallback and self._fallback_queue:
            item = self._fallback_queue.pop(0)
            ctx = timer.record(CacheStatus.FALLBACK, FallbackReason.REDIS_UNAVAILABLE)
            return QueueResult(
                items=[item],
                status=CacheStatus.FALLBACK,
                fallback_reason=FallbackReason.REDIS_UNAVAILABLE,
                latency_ms=ctx.latency_ms,
                queue_length=len(self._fallback_queue),
            )

        if self.config.enable_fallback and not self.redis_conn.is_available():
            ctx = timer.record(CacheStatus.FALLBACK, FallbackReason.REDIS_UNAVAILABLE)
            return QueueResult(
                items=[],
                status=CacheStatus.FALLBACK,
                fallback_reason=FallbackReason.REDIS_UNAVAILABLE,
                latency_ms=ctx.latency_ms,
                queue_length=len(self._fallback_queue),
            )

        ctx = timer.record(CacheStatus.ERROR, error_message=last_error)
        return QueueResult(
            items=[],
            status=CacheStatus.ERROR,
            fallback_reason=FallbackReason.CONNECTION_ERROR,
            latency_ms=ctx.latency_ms,
            retry_count=self.config.max_retries,
        )

    async def length(self) -> QueueResult[int]:
        timer = CacheOperationTimer(
            cache_key=self.queue_name,
            operation=OperationType.LEN,
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

                    length = await redis.llen(self.queue_name)

                    ctx = timer.record(CacheStatus.HIT)
                    return QueueResult(
                        items=[length],
                        status=CacheStatus.HIT,
                        latency_ms=ctx.latency_ms,
                        retry_count=attempt,
                        queue_length=length,
                    )
                except asyncio.CancelledError:
                    timer.record(CacheStatus.ERROR, error_message="Operation cancelled")
                    raise
                except Exception as e:
                    last_error = str(e)
                    logger.debug(f"Queue len attempt {attempt + 1} failed: {e}")
                    if attempt < self.config.max_retries - 1:
                        await asyncio.sleep(self.config.retry_delay * (2 ** attempt))

        if self.config.enable_fallback:
            length = len(self._fallback_queue)
            ctx = timer.record(CacheStatus.FALLBACK, FallbackReason.REDIS_UNAVAILABLE)
            return QueueResult(
                items=[length],
                status=CacheStatus.FALLBACK,
                fallback_reason=FallbackReason.REDIS_UNAVAILABLE,
                latency_ms=ctx.latency_ms,
                queue_length=length,
            )

        ctx = timer.record(CacheStatus.ERROR, error_message=last_error)
        return QueueResult(
            items=[],
            status=CacheStatus.ERROR,
            fallback_reason=FallbackReason.CONNECTION_ERROR,
            latency_ms=ctx.latency_ms,
            retry_count=self.config.max_retries,
        )

    def is_using_fallback(self) -> bool:
        return not self.redis_conn.is_available() and self.config.enable_fallback
