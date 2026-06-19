from typing import Optional, Type
from .entity import ModelEntity
from ..cache import CacheHelper, CacheConfig, CacheStatus, KeyNamespace, CacheCategory
from ..cache.connection import EnhancedRedisConnection
import logging

logger = logging.getLogger(__name__)

__all__ = ["RedisOperator"]


class RedisOperator(object):
    def __init__(
        self,
        entity_class: Type[ModelEntity],
        redis_conn=None,
        redis_key_postfix: str = None,
        expire: int = 3600 * 4,
        namespace: str = "backend",
        module: str = "entity",
    ):
        self.entity_class = entity_class
        self.redis_key_postfix = redis_key_postfix
        self.expire = expire
        self.namespace = namespace
        self.module = module
        self._cache_helper: Optional[CacheHelper] = None

        if redis_conn is None:
            self.redis_conn = None
        elif isinstance(redis_conn, EnhancedRedisConnection):
            self.redis_conn = redis_conn
            self._cache_helper = CacheHelper(
                redis_conn=redis_conn,
                config=CacheConfig(ttl=expire),
                namespace=f"{namespace}:{module}",
            )
        else:
            self.redis_conn = redis_conn
            self._cache_helper = None

    def _build_key(self, postfix: str = None, **kwargs) -> str:
        key_parts = [self.entity_class.object_name()]

        for field in self.entity_class.primary_key_fields():
            if field in kwargs:
                key_parts.append(str(kwargs[field]))
            else:
                raise ValueError(f"Missing value for primary key field: {field}")

        if postfix:
            key_parts.append(postfix)

        return ":".join(key_parts)

    def _deserialize_entity(self, data: dict) -> Optional[ModelEntity]:
        try:
            return self.entity_class.build(data)
        except Exception as e:
            logger.error(f"Error building entity from Redis data: {e}")
            return None

    async def get(self, **kwargs) -> Optional[ModelEntity]:
        if self.redis_conn is None:
            return None

        key = self._build_key(self.redis_key_postfix, **kwargs)

        if self._cache_helper:
            result = await self._cache_helper.get(key)
            if result.hit and result.value:
                entity = self._deserialize_entity(result.value)
                if entity:
                    return entity
                else:
                    await self._cache_helper.delete(key)
            return None
        else:
            data = await self.redis_conn.get_object(key)
            if data:
                entity = self._deserialize_entity(data)
                if entity:
                    return entity
                else:
                    await self.redis_conn.pop(key)
            return None

    async def set(self, entity: ModelEntity):
        if self.redis_conn is None:
            return

        pk_fields = self.entity_class.primary_key_fields()
        pk_values = {field: getattr(entity, field) for field in pk_fields}
        key = self._build_key(**pk_values, postfix=self.redis_key_postfix)
        entity_dict = entity.to_redis_dict()

        if self._cache_helper:
            await self._cache_helper.set(key, entity_dict, ttl=self.expire)
        else:
            await self.redis_conn.set_object(key, entity_dict, self.expire)

    async def pop(self, entity: ModelEntity):
        if self.redis_conn is None:
            return

        pk_fields = self.entity_class.primary_key_fields()
        pk_values = {field: getattr(entity, field) for field in pk_fields}
        key = self._build_key(**pk_values, postfix=self.redis_key_postfix)

        if self._cache_helper:
            await self._cache_helper.delete(key)
        else:
            await self.redis_conn.pop(key)

    async def invalidate(self, **kwargs):
        if self.redis_conn is None:
            return

        key = self._build_key(self.redis_key_postfix, **kwargs)

        if self._cache_helper:
            await self._cache_helper.delete(key)
        else:
            await self.redis_conn.pop(key)

    def get_cache_helper(self) -> Optional[CacheHelper]:
        return self._cache_helper
