import json
import time
import uuid
import logging
from dataclasses import dataclass, asdict, field
from typing import Any, Optional, Dict

from common.cache import (
    CacheConfig,
    CacheHelper,
    CacheStatus,
    build_cache_key,
    KeyNamespace,
    CacheCategory,
    EnhancedRedisConnection,
)

logger = logging.getLogger(__name__)

DEFAULT_ARTIFACT_TTL = 3600 * 24

__all__ = [
    "ArtifactCacheEntry",
    "ArtifactCache",
    "artifact_cache",
    "get_artifact_cache",
    "set_artifact_cache",
    "delete_artifact_cache",
    "init_artifact_cache",
]


@dataclass
class ArtifactCacheEntry:
    artifact_id: str
    artifact_type: str
    plugin_id: str
    version: str
    storage_key: str
    storage_provider: str = "local"
    metadata: Dict[str, Any] = field(default_factory=dict)
    size: int = 0
    content_hash: str = ""
    created_at: float = field(default_factory=time.time)
    expires_at: float = 0.0
    access_count: int = 0
    last_accessed: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ArtifactCacheEntry":
        return cls(**data)


def _serialize_artifact(entry: ArtifactCacheEntry) -> str:
    return json.dumps(entry.to_dict())


def _deserialize_artifact(data: str) -> ArtifactCacheEntry:
    parsed = json.loads(data)
    return ArtifactCacheEntry.from_dict(parsed)


class ArtifactCache:
    def __init__(
        self,
        redis_conn: EnhancedRedisConnection,
        ttl: int = DEFAULT_ARTIFACT_TTL,
        module: str = "artifact",
    ):
        self.redis_conn = redis_conn
        self.ttl = ttl
        self.module = module
        self._cache_helper = CacheHelper[ArtifactCacheEntry](
            redis_conn=redis_conn,
            config=CacheConfig(
                ttl=ttl,
                enable_fallback=True,
                namespace=KeyNamespace.PLUGIN,
            ),
            namespace=KeyNamespace.PLUGIN,
        )

    def _build_key(self, artifact_id: str, plugin_id: str, artifact_type: str) -> str:
        return build_cache_key(
            KeyNamespace.PLUGIN,
            self.module,
            CacheCategory.ARTIFACT,
            plugin_id,
            artifact_type,
            artifact_id,
        )

    async def get(
        self,
        artifact_id: str,
        plugin_id: str,
        artifact_type: str,
    ) -> Optional[ArtifactCacheEntry]:
        key = self._build_key(artifact_id, plugin_id, artifact_type)
        result = await self._cache_helper.get(key, deserializer=_deserialize_artifact)
        if result.value is not None:
            entry = result.value
            entry.access_count += 1
            entry.last_accessed = time.time()
            if result.status != CacheStatus.FALLBACK:
                await self._cache_helper.set(key, entry, ttl=self.ttl, serializer=_serialize_artifact)
            return entry
        return None

    async def set(
        self,
        entry: ArtifactCacheEntry,
        ttl: Optional[int] = None,
    ) -> bool:
        key = self._build_key(entry.artifact_id, entry.plugin_id, entry.artifact_type)
        effective_ttl = ttl if ttl is not None else self.ttl
        entry.expires_at = time.time() + effective_ttl
        result = await self._cache_helper.set(key, entry, ttl=effective_ttl, serializer=_serialize_artifact)
        return result.value is True or result.status == CacheStatus.FALLBACK

    async def delete(
        self,
        artifact_id: str,
        plugin_id: str,
        artifact_type: str,
    ) -> bool:
        key = self._build_key(artifact_id, plugin_id, artifact_type)
        result = await self._cache_helper.delete(key)
        return result.value is True or result.status == CacheStatus.FALLBACK

    async def create(
        self,
        plugin_id: str,
        artifact_type: str,
        storage_key: str,
        version: str = "latest",
        storage_provider: str = "local",
        metadata: Optional[Dict[str, Any]] = None,
        size: int = 0,
        content_hash: str = "",
        ttl: Optional[int] = None,
    ) -> ArtifactCacheEntry:
        artifact_id = str(uuid.uuid4())
        entry = ArtifactCacheEntry(
            artifact_id=artifact_id,
            artifact_type=artifact_type,
            plugin_id=plugin_id,
            version=version,
            storage_key=storage_key,
            storage_provider=storage_provider,
            metadata=metadata or {},
            size=size,
            content_hash=content_hash,
        )
        await self.set(entry, ttl=ttl)
        logger.info(
            f"Artifact created: artifact_id={artifact_id}, "
            f"plugin_id={plugin_id}, type={artifact_type}, size={size}"
        )
        return entry

    async def exists(
        self,
        artifact_id: str,
        plugin_id: str,
        artifact_type: str,
    ) -> bool:
        entry = await self.get(artifact_id, plugin_id, artifact_type)
        return entry is not None

    async def renew(
        self,
        artifact_id: str,
        plugin_id: str,
        artifact_type: str,
        ttl: Optional[int] = None,
    ) -> bool:
        entry = await self.get(artifact_id, plugin_id, artifact_type)
        if entry is None:
            return False
        return await self.set(entry, ttl=ttl)

    def is_using_fallback(self) -> bool:
        return self._cache_helper.is_using_fallback()


artifact_cache: Optional[ArtifactCache] = None


def get_default_artifact_cache() -> ArtifactCache:
    global artifact_cache
    if artifact_cache is None:
        conn = EnhancedRedisConnection(url="", name="plugin_artifact")
        artifact_cache = ArtifactCache(redis_conn=conn)
    return artifact_cache


def init_artifact_cache(redis_conn: EnhancedRedisConnection, ttl: int = DEFAULT_ARTIFACT_TTL) -> ArtifactCache:
    global artifact_cache
    artifact_cache = ArtifactCache(redis_conn=redis_conn, ttl=ttl)
    return artifact_cache


async def get_artifact_cache(
    artifact_id: str,
    plugin_id: str,
    artifact_type: str,
) -> Optional[ArtifactCacheEntry]:
    cache = get_default_artifact_cache()
    return await cache.get(artifact_id, plugin_id, artifact_type)


async def set_artifact_cache(
    entry: ArtifactCacheEntry,
    ttl: Optional[int] = None,
) -> bool:
    cache = get_default_artifact_cache()
    return await cache.set(entry, ttl=ttl)


async def delete_artifact_cache(
    artifact_id: str,
    plugin_id: str,
    artifact_type: str,
) -> bool:
    cache = get_default_artifact_cache()
    return await cache.delete(artifact_id, plugin_id, artifact_type)
