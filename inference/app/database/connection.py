import aioredis
import asyncio
import json
import logging
from typing import Dict, List, Optional

from config import CONFIG

logger = logging.getLogger(__name__)


class RedisConnection:
    _instance = None
    _lock = asyncio.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, url: str):
        self.url = url
        if not hasattr(self, "initialized"):
            self.redis: Optional[aioredis.Redis] = None
            self.initialized = False
            self.health_check_failures = 0

    async def init(self):
        async with self._lock:
            if not self.url:
                logger.warning("REDIS_URL is not set, Redis cache disabled.")
                self.initialized = False
                return
            if not self.initialized or self.redis is None:
                if self.redis is not None:
                    try:
                        await self.redis.close()
                    except Exception:
                        pass
                self.redis = await aioredis.from_url(self.url)
                try:
                    await self.redis.config_set("maxmemory-policy", "allkeys-lru")
                    logger.info("Set redis maxmemory-policy to allkeys-lru")
                except Exception as e:
                    logger.warning(f"Failed to set redis maxmemory-policy: {e}")
                logger.info("Redis pool initialized or reinitialized.")
                self.initialized = True
                self.health_check_failures = 0

    async def close(self):
        async with self._lock:
            if self.redis is not None and self.initialized:
                try:
                    await self.redis.close()
                except Exception:
                    pass
                self.redis = None
                self.initialized = False
                self.health_check_failures = 0
                logger.info("Redis pool closed.")

    async def restart_redis(self):
        await self.close()
        await self.init()
        logger.info("Redis client has been restarted.")

    async def health_check(self):
        if self.redis is None:
            self.health_check_failures += 1
            logger.error(f"Redis health check failed: redis is not initialized, failures={self.health_check_failures}")
            return False
        try:
            pong = await self.redis.ping()
            if pong:
                self.health_check_failures = 0
                return True
            else:
                self.health_check_failures += 1
                logger.error(f"Redis health check failed: did not receive PONG, failures={self.health_check_failures}")
        except asyncio.CancelledError:
            self.health_check_failures += 1
            logger.error(f"Redis health check failed: operation was cancelled, failures={self.health_check_failures}")
        except Exception as e:
            self.health_check_failures += 1
            logger.error(f"Redis health check failed: error={e}, failures={self.health_check_failures}")

        if self.health_check_failures > 10:
            logger.warning("Redis health check failed 10 times, attempting to restart Redis client.")
            await self.restart_redis()
            self.health_check_failures = 0

        return False

    async def clean_data(self):
        if self.redis is None:
            return
        try:
            await self.redis.flushdb()
            logger.info("Redis flush done.")
        except Exception as e:
            logger.error(f"Redis flush failed: {e}")

    async def set_string(self, key: str, value: str, expire: int = 3600 * 4):
        if self.redis is None:
            return
        try:
            await self.redis.set(key, value, ex=expire)
            logger.debug(f"set_string: key={key}")
        except asyncio.CancelledError:
            logger.error(f"set_string: operation was cancelled, key={key}")
        except Exception as e:
            logger.error(f"set_string: error={e}")

    async def set_object(self, key: str, value: Dict, expire: int = 3600 * 4):
        if self.redis is None:
            return
        try:
            await self.redis.set(key, json.dumps(value), ex=expire)
            logger.debug(f"set_object: key={key}")
        except asyncio.CancelledError:
            logger.error(f"set_object: operation was cancelled, key={key}")
        except Exception as e:
            logger.error(f"set_object: error={e}")

    async def set_list(self, key: str, value: List, expire: int = 3600 * 4):
        if self.redis is None:
            return
        try:
            await self.redis.set(key, json.dumps(value), ex=expire)
            logger.debug(f"set_list: key={key}")
        except asyncio.CancelledError:
            logger.error(f"set_list: operation was cancelled, key={key}")
        except Exception as e:
            logger.error(f"set_list: error={e}")

    async def set_int(self, key: str, value: int, expire: int = 3600 * 4):
        if self.redis is None:
            return
        try:
            await self.redis.set(key, value, ex=expire)
            logger.debug(f"set_int: key={key}, value={value}")
        except asyncio.CancelledError:
            logger.error(f"set_int: operation was cancelled, key={key}")
        except Exception as e:
            logger.error(f"set_int: error={e}")

    async def pop(self, key: str):
        if self.redis is None:
            return
        try:
            await self.redis.delete(key)
            logger.debug(f"pop: key={key}")
        except asyncio.CancelledError:
            logger.error(f"pop: operation was cancelled, key={key}")
        except Exception as e:
            logger.error(f"pop: error={e}")

    async def get_string(self, key: str) -> Optional[str]:
        if self.redis is None:
            return None
        try:
            value_bytes = await self.redis.get(key)
            if value_bytes is not None:
                if isinstance(value_bytes, bytes):
                    value = value_bytes.decode()
                else:
                    value = value_bytes
                logger.debug(f"get_string: key={key}")
                return value
            return None
        except asyncio.CancelledError:
            logger.error(f"get_string: operation was cancelled, key={key}")
            return None
        except Exception as e:
            logger.error(f"get_string: error={e}")
            return None

    async def get_object(self, key: str) -> Optional[Dict]:
        if self.redis is None:
            return None
        try:
            value_string = await self.redis.get(key)
            logger.debug(f"get_object: key={key}")
            if value_string:
                if isinstance(value_string, bytes):
                    value_string = value_string.decode()
                return json.loads(value_string)
        except asyncio.CancelledError:
            logger.error(f"get_object: operation was cancelled, key={key}")
            return None
        except Exception as e:
            logger.error(f"get_object: error={e}")
            return None

    async def get_list(self, key: str) -> Optional[List]:
        if self.redis is None:
            return None
        try:
            value_string = await self.redis.get(key)
            logger.debug(f"get_list: key={key}")
            if value_string:
                if isinstance(value_string, bytes):
                    value_string = value_string.decode()
                return json.loads(value_string)
        except asyncio.CancelledError:
            logger.error(f"get_list: operation was cancelled, key={key}")
            return None
        except Exception as e:
            logger.error(f"get_list: error={e}")
            return None

    async def get_int(self, key: str) -> Optional[int]:
        if self.redis is None:
            return None
        try:
            value = await self.redis.get(key)
            logger.debug(f"get_int: key={key}")
            if value:
                if isinstance(value, bytes):
                    value = value.decode()
                return int(value)
        except asyncio.CancelledError:
            logger.error(f"get_int: operation was cancelled, key={key}")
            return None
        except Exception as e:
            logger.error(f"get_int: error={e}")
            return None


redis_conn = RedisConnection(url=CONFIG.REDIS_URL)


async def init_database():
    logger.info("Initializing redis connection..")
    await redis_conn.init()


async def close_database():
    logger.info("Closing redis connection..")
    await redis_conn.close()
