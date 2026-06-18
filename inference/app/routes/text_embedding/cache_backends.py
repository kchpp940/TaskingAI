import asyncio
import logging
import time as _time
from abc import ABC, abstractmethod
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from app.database import redis_conn
from config import CONFIG

logger = logging.getLogger(__name__)


@dataclass
class CacheBackendStatus:
    configured_backend: str = ""
    effective_backend: str = ""
    fallback_reason: Optional[str] = None
    fallbacks: Dict[str, int] = field(default_factory=dict)


_cache_status_ctx: ContextVar[CacheBackendStatus] = ContextVar(
    "embedding_cache_status", default=CacheBackendStatus()
)


def _ctx() -> CacheBackendStatus:
    return _cache_status_ctx.get()


def begin_request() -> CacheBackendStatus:
    status = CacheBackendStatus(
        configured_backend=_configured_backend_name(),
    )
    _cache_status_ctx.set(status)
    return status


def end_request() -> CacheBackendStatus:
    status = _ctx()
    return status


def _configured_backend_name() -> str:
    return "redis" if CONFIG.REDIS_URL else "memory"


def _record_fallback(reason: str, to_backend: str) -> None:
    status = _ctx()
    status.effective_backend = to_backend
    status.fallback_reason = reason
    status.fallbacks[reason] = status.fallbacks.get(reason, 0) + 1


class EmbeddingCacheBackend(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    async def get(self, key: str, ttl: int) -> Optional[List[float]]:
        pass

    @abstractmethod
    async def set(self, key: str, embedding: List[float], ttl: int, max_size: Optional[int] = None) -> None:
        pass

    @abstractmethod
    async def evict_expired(self, ttl: int) -> int:
        pass

    @abstractmethod
    def stats(self) -> Dict:
        pass


class InMemoryCacheBackend(EmbeddingCacheBackend):
    def __init__(self):
        self._cache: Dict[str, Tuple[List[float], float]] = {}
        self._lock = asyncio.Lock()

    @property
    def name(self) -> str:
        return "memory"

    async def get(self, key: str, ttl: int) -> Optional[List[float]]:
        async with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            embedding, ts = entry
            if _time.time() - ts > ttl:
                del self._cache[key]
                return None
            return embedding

    async def set(self, key: str, embedding: List[float], ttl: int, max_size: Optional[int] = None) -> None:
        if max_size is None:
            max_size = CONFIG.EMBEDDING_CACHE_MAX_SIZE
        async with self._lock:
            if len(self._cache) >= max_size:
                self._evict_oldest(max_size // 2)
            self._cache[key] = (embedding, _time.time())

    def _evict_oldest(self, remove_count: int) -> None:
        sorted_items = sorted(self._cache.items(), key=lambda item: item[1][1])
        for key, _ in sorted_items[:remove_count]:
            del self._cache[key]

    async def evict_expired(self, ttl: int) -> int:
        async with self._lock:
            now = _time.time()
            expired_keys = [k for k, (_, ts) in self._cache.items() if now - ts > ttl]
            for k in expired_keys:
                del self._cache[k]
            if expired_keys:
                logger.info(f"in_memory_cache: evicted {len(expired_keys)} expired entries")
            return len(expired_keys)

    def stats(self) -> Dict:
        return {"size": len(self._cache)}


class RedisCacheBackend(EmbeddingCacheBackend):
    def __init__(self):
        pass

    @property
    def name(self) -> str:
        return "redis"

    def is_available(self) -> bool:
        return redis_conn.initialized and redis_conn.redis is not None

    async def get(self, key: str, ttl: int) -> Optional[List[float]]:
        if not self.is_available():
            raise ConnectionError("redis not initialized")
        return await redis_conn.get_list(key)

    async def set(self, key: str, embedding: List[float], ttl: int, max_size: Optional[int] = None) -> None:
        if not self.is_available():
            raise ConnectionError("redis not initialized")
        await redis_conn.set_list(key, embedding, expire=ttl)

    async def evict_expired(self, ttl: int) -> int:
        return 0

    def stats(self) -> Dict:
        return {"connected": redis_conn.initialized}


class FailoverCacheBackend(EmbeddingCacheBackend):
    """Composite backend: prefer Redis; on unavailability or operation failure, fall back to memory."""

    def __init__(self, redis: RedisCacheBackend, memory: InMemoryCacheBackend):
        self.redis = redis
        self.memory = memory
        self._config_name = _configured_backend_name()

    @property
    def name(self) -> str:
        return self._config_name

    @property
    def configured_name(self) -> str:
        return self._config_name

    def _resolve_effective(self, require_redis_alive: bool = True) -> Tuple[EmbeddingCacheBackend, str]:
        if self._config_name == "redis":
            if require_redis_alive and self.redis.is_available():
                return self.redis, self.redis.name
            return self.memory, self.memory.name
        return self.memory, self.memory.name

    async def get(self, key: str, ttl: int) -> Optional[List[float]]:
        status = _ctx()
        if status.configured_backend != self._config_name:
            status.configured_backend = self._config_name

        if self._config_name == "memory":
            status.effective_backend = "memory"
            if not status.fallback_reason:
                status.fallback_reason = "redis_not_configured"
            return await self.memory.get(key, ttl)

        if not self.redis.is_available():
            _record_fallback("redis_not_initialized", "memory")
            return await self.memory.get(key, ttl)

        try:
            result = await self.redis.get(key, ttl)
            status.effective_backend = "redis"
            return result
        except Exception as e:
            logger.warning(f"Redis get operation failed, fallback to memory: {e}")
            _record_fallback("redis_operation_failed", "memory")
            try:
                return await self.memory.get(key, ttl)
            except Exception as e2:
                logger.error(f"Memory fallback get also failed: {e2}")
                return None

    async def set(self, key: str, embedding: List[float], ttl: int, max_size: Optional[int] = None) -> None:
        status = _ctx()
        if status.configured_backend != self._config_name:
            status.configured_backend = self._config_name

        if self._config_name == "memory":
            status.effective_backend = "memory"
            if not status.fallback_reason:
                status.fallback_reason = "redis_not_configured"
            await self.memory.set(key, embedding, ttl, max_size)
            return

        if not self.redis.is_available():
            _record_fallback("redis_not_initialized", "memory")
            await self.memory.set(key, embedding, ttl, max_size)
            return

        try:
            await self.redis.set(key, embedding, ttl, max_size)
            status.effective_backend = "redis"
        except Exception as e:
            logger.warning(f"Redis set operation failed, fallback to memory: {e}")
            _record_fallback("redis_operation_failed", "memory")
            try:
                await self.memory.set(key, embedding, ttl, max_size)
            except Exception as e2:
                logger.error(f"Memory fallback set also failed: {e2}")

    async def evict_expired(self, ttl: int) -> int:
        effective, _ = self._resolve_effective()
        return await effective.evict_expired(ttl)

    def stats(self) -> Dict:
        effective, effective_name = self._resolve_effective()
        result = effective.stats()
        result["configured"] = self._config_name
        result["effective"] = effective_name
        return result


_cache_backend: Optional[FailoverCacheBackend] = None


def get_cache_backend() -> FailoverCacheBackend:
    global _cache_backend
    if _cache_backend is not None:
        return _cache_backend
    redis_backend = RedisCacheBackend()
    memory_backend = InMemoryCacheBackend()
    _cache_backend = FailoverCacheBackend(redis=redis_backend, memory=memory_backend)
    return _cache_backend


def init_cache_backend() -> FailoverCacheBackend:
    global _cache_backend
    backend = get_cache_backend()
    configured = backend.configured_name
    redis_ok = backend.redis.is_available() if configured == "redis" else False
    logger.info(
        f"Embedding cache backend initialized: configured={configured} "
        f"redis_available={redis_ok}"
    )
    return backend


def get_current_cache_backend() -> FailoverCacheBackend:
    return get_cache_backend()


def get_backend_names() -> Tuple[str, str]:
    backend = get_cache_backend()
    status = _ctx()
    configured = status.configured_backend or backend.configured_name
    effective = status.effective_backend or configured
    return configured, effective


def get_fallback_reason() -> Optional[str]:
    return _ctx().fallback_reason

