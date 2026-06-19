import asyncio
import logging
import time
from typing import Optional, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

try:
    import aioredis
    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False


@dataclass
class ConnectionStats:
    initialized: bool = False
    health_check_failures: int = 0
    total_operations: int = 0
    failed_operations: int = 0
    last_health_check: float = 0.0
    last_error: Optional[str] = None
    reconnect_count: int = 0


class EnhancedRedisConnection:
    _instances: Dict[str, "EnhancedRedisConnection"] = {}
    _lock: Optional[asyncio.Lock] = None

    def __init__(self, url: str = "", name: str = "default"):
        self.url = url
        self.name = name
        self.redis = None
        self.stats = ConnectionStats()
        self._init_lock = asyncio.Lock()

    @classmethod
    def _get_class_lock(cls) -> asyncio.Lock:
        if cls._lock is None:
            cls._lock = asyncio.Lock()
        return cls._lock

    @classmethod
    async def get_instance(cls, url: str, name: str = "default") -> "EnhancedRedisConnection":
        lock = cls._get_class_lock()
        async with lock:
            if name not in cls._instances:
                instance = cls(url, name)
                await instance.init()
                cls._instances[name] = instance
        return cls._instances[name]

    async def init(self) -> None:
        if not HAS_REDIS:
            logger.warning(f"[{self.name}] aioredis not installed, using memory fallback only")
            return

        async with self._init_lock:
            if not self.stats.initialized or self.redis is None:
                if self.redis is not None:
                    try:
                        await self.redis.close()
                    except Exception as e:
                        logger.warning(f"[{self.name}] Error closing old redis connection: {e}")

                try:
                    self.redis = aioredis.from_url(self.url)
                    await self.redis.config_set("maxmemory-policy", "allkeys-lru")
                    logger.info(f"[{self.name}] Redis connection initialized, maxmemory-policy=allkeys-lru")
                    self.stats.initialized = True
                    self.stats.health_check_failures = 0
                    self.stats.last_error = None
                except Exception as e:
                    self.stats.last_error = str(e)
                    self.stats.health_check_failures += 1
                    logger.error(f"[{self.name}] Failed to initialize Redis: {e}")
                    if self.redis:
                        try:
                            await self.redis.close()
                        except Exception:
                            pass
                        self.redis = None

    async def close(self) -> None:
        async with self._init_lock:
            if self.redis is not None and self.stats.initialized:
                try:
                    await self.redis.close()
                except Exception as e:
                    logger.warning(f"[{self.name}] Error closing Redis: {e}")
                finally:
                    self.redis = None
                    self.stats.initialized = False
                    self.stats.health_check_failures = 0
                    logger.info(f"[{self.name}] Redis connection closed")

    async def health_check(self) -> bool:
        if not HAS_REDIS or self.redis is None:
            self.stats.health_check_failures += 1
            self.stats.last_health_check = time.time()
            return False

        try:
            pong = await self.redis.ping()
            if pong:
                self.stats.health_check_failures = 0
                self.stats.last_health_check = time.time()
                return True
        except asyncio.CancelledError:
            self.stats.health_check_failures += 1
            self.stats.last_health_check = time.time()
            raise
        except Exception as e:
            self.stats.health_check_failures += 1
            self.stats.last_health_check = time.time()
            self.stats.last_error = str(e)
            logger.error(f"[{self.name}] Health check failed: {e}, failures={self.stats.health_check_failures}")

        if self.stats.health_check_failures > 10:
            logger.warning(f"[{self.name}] Health check failed 10 times, attempting reconnect")
            await self.reconnect()

        return False

    async def reconnect(self) -> None:
        self.stats.reconnect_count += 1
        logger.info(f"[{self.name}] Reconnecting Redis (attempt #{self.stats.reconnect_count})")
        await self.close()
        await self.init()
        self.stats.health_check_failures = 0

    def is_available(self) -> bool:
        return HAS_REDIS and self.redis is not None and self.stats.initialized

    def get_stats(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "initialized": self.stats.initialized,
            "health_check_failures": self.stats.health_check_failures,
            "total_operations": self.stats.total_operations,
            "failed_operations": self.stats.failed_operations,
            "last_health_check": self.stats.last_health_check,
            "last_error": self.stats.last_error,
            "reconnect_count": self.stats.reconnect_count,
            "is_available": self.is_available(),
            "has_redis_lib": HAS_REDIS,
        }

    async def flushdb(self) -> None:
        if self.redis:
            await self.redis.flushdb()
            logger.info(f"[{self.name}] Redis flushdb done")

    def get_client(self):
        return self.redis


_connections: Dict[str, EnhancedRedisConnection] = {}
_connections_lock = asyncio.Lock()


async def get_redis_connection(url: str, name: str = "default") -> EnhancedRedisConnection:
    global _connections
    async with _connections_lock:
        if name not in _connections:
            _connections[name] = EnhancedRedisConnection(url, name)
            await _connections[name].init()
    return _connections[name]
