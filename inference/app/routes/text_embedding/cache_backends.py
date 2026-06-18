import asyncio
import json
import time
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple

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
        async with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            embedding, ts = entry
            if time.time() - ts > ttl:
                del self._cache[key]
                return None
            return embedding

    async def set(self, key: str, embedding: List[float], ttl: int, max_size: Optional[int] = None) -> None:
        if max_size is None:
            max_size = CONFIG.EMBEDDING_CACHE_MAX_SIZE
        async with self._lock:
            if len(self._cache) >= max_size:
                self._evict_oldest(max_size // 2)
            self._cache[key] = (embedding, time.time())

    def _evict_oldest(self, remove_count: int) -> None:
        sorted_items = sorted(self._cache.items(), key=lambda item: item[1][1])
        for key, _ in sorted_items[:remove_count]:
            del self._cache[key]

    async def evict_expired(self, ttl: int) -> int:
        async with self._lock:
            now = time.time()
            expired_keys = [k for k, (_, ts) in self._cache.items() if now - ts > ttl]
            for k in expired_keys:
                del self._cache[k]
            if expired_keys:
                logger.info(f"in_memory_cache: evicted {len(expired_keys)} expired entries")
            return len(expired_keys)

    def stats(self) -> Dict:
        return {"size": len(self._cache)}


class RedisCacheBackend(EmbeddingCacheBackend):
    _instance: Optional["RedisCacheBackend"] = None
    _init_lock = asyncio.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, redis_url: Optional[str] = None):
        if not hasattr(self, "initialized"):
            self.redis_url = redis_url or CONFIG.REDIS_URL
            self.redis: Optional["aioredis.Redis"] = None
            self.initialized = False
            self._connect_lock = asyncio.Lock()

    @property
    def name(self) -> str:
        return "redis"

    async def _ensure_connection(self) -> bool:
        if not self.redis_url:
            return False
        async with self._connect_lock:
            if not self.initialized or self.redis is None:
                try:
                    import aioredis
                    self.redis = await aioredis.from_url(self.redis_url)
                    await self.redis.config_set("maxmemory-policy", "allkeys-lru")
                    self.initialized = True
                    logger.info(f"Redis embedding cache connected: {self.redis_url}")
                except Exception as e:
                    logger.error(f"Failed to connect to Redis for embedding cache: {e}")
                    if self.redis is not None:
                        try:
                            await self.redis.close()
                        except Exception:
                            pass
                        self.redis = None
                    self.initialized = False
                    return False
        return True

    async def get(self, key: str, ttl: int) -> Optional[List[float]]:
        if not await self._ensure_connection():
            return None
        try:
            value_bytes = await self.redis.get(key)
            if value_bytes is None:
                return None
            return json.loads(value_bytes)
        except Exception as e:
            logger.error(f"Redis get failed for embedding cache: {e}")
            return None

    async def set(self, key: str, embedding: List[float], ttl: int, max_size: Optional[int] = None) -> None:
        if not await self._ensure_connection():
            return
        try:
            value_str = json.dumps(embedding)
            await self.redis.set(key, value_str, ex=ttl)
        except Exception as e:
            logger.error(f"Redis set failed for embedding cache: {e}")

    async def evict_expired(self, ttl: int) -> int:
        return 0

    def stats(self) -> Dict:
        return {"connected": self.initialized}


def get_cache_backend() -> EmbeddingCacheBackend:
    if CONFIG.REDIS_URL:
        try:
            backend = RedisCacheBackend(CONFIG.REDIS_URL)
            return backend
        except Exception as e:
            logger.warning(f"Failed to initialize Redis cache backend, falling back to memory: {e}")
    return InMemoryCacheBackend()


_cache_backend: Optional[EmbeddingCacheBackend] = None


def init_cache_backend() -> EmbeddingCacheBackend:
    global _cache_backend
    _cache_backend = get_cache_backend()
    return _cache_backend


def get_current_cache_backend() -> EmbeddingCacheBackend:
    global _cache_backend
    if _cache_backend is None:
        _cache_backend = get_cache_backend()
    return _cache_backend
