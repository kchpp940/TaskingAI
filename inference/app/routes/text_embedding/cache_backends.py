import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple

from app.database import redis_conn
from config import CONFIG

logger = logging.getLogger(__name__)


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
        import time as _time
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
        import time as _time
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
        import time as _time
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

    def _is_available(self) -> bool:
        return redis_conn.initialized and redis_conn.redis is not None

    async def get(self, key: str, ttl: int) -> Optional[List[float]]:
        if not self._is_available():
            return None
        try:
            return await redis_conn.get_list(key)
        except Exception as e:
            logger.error(f"Redis get failed for embedding cache: {e}")
            return None

    async def set(self, key: str, embedding: List[float], ttl: int, max_size: Optional[int] = None) -> None:
        if not self._is_available():
            return
        try:
            await redis_conn.set_list(key, embedding, expire=ttl)
        except Exception as e:
            logger.error(f"Redis set failed for embedding cache: {e}")

    async def evict_expired(self, ttl: int) -> int:
        return 0

    def stats(self) -> Dict:
        return {"connected": redis_conn.initialized}


_cache_backend: Optional[EmbeddingCacheBackend] = None


def get_cache_backend() -> EmbeddingCacheBackend:
    global _cache_backend
    if _cache_backend is not None:
        return _cache_backend
    if CONFIG.REDIS_URL:
        _cache_backend = RedisCacheBackend()
        return _cache_backend
    _cache_backend = InMemoryCacheBackend()
    return _cache_backend


def init_cache_backend() -> EmbeddingCacheBackend:
    global _cache_backend
    backend = get_cache_backend()
    logger.info(f"Embedding cache backend initialized: {backend.name}")
    return backend


def get_current_cache_backend() -> EmbeddingCacheBackend:
    return get_cache_backend()
