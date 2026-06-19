import json
import time
import uuid
from dataclasses import dataclass, asdict, field
from typing import Any, Optional, Dict

from .base import CacheConfig
from .key_namespace import build_cache_key, KeyNamespace, CacheCategory
from .connection import EnhancedRedisConnection
from .cache_helper import CacheHelper

DEFAULT_ARTIFACT_TTL = 3600 * 24


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
        config = CacheConfig(
            ttl=ttl,
            enable_fallback=True,
            namespace=KeyNamespace.PLUGIN,
        )
        self._cache_helper: Optional[CacheHelper] = None
        self._init_lock = None

    def _get_helper(self) -> CacheHelper:
        if self._cache_helper is None:
            self._cache_helper = CacheHelper(
                redis_conn=self.redis_conn,
                config=CacheConfig(
                    ttl=self.ttl,
                    enable_fallback=True,
                    namespace=KeyNamespace.PLUGIN,
                ),
                namespace=KeyNamespace.PLUGIN,
            )
        return self._cache_helper

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
        helper = self._get_helper()
        result = await helper.get(key, deserializer=_deserialize_artifact)
        if result.value is not None:
            entry = result.value
            entry.access_count += 1
            entry.last_accessed = time.time()
            if result.status.value != "fallback":
                await helper.set(key, entry, ttl=self.ttl, serializer=_serialize_artifact)
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
        helper = self._get_helper()
        result = await helper.set(key, entry, ttl=effective_ttl, serializer=_serialize_artifact)
        return result.value is True

    async def delete(
        self,
        artifact_id: str,
        plugin_id: str,
        artifact_type: str,
    ) -> bool:
        key = self._build_key(artifact_id, plugin_id, artifact_type)
        helper = self._get_helper()
        result = await helper.delete(key)
        return result.value is True

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
        effective_ttl = ttl if ttl is not None else self.ttl
        return await self.set(entry, ttl=effective_ttl)


def _serialize_artifact(entry: ArtifactCacheEntry) -> str:
    return json.dumps(entry.to_dict())


def _deserialize_artifact(data: str) -> ArtifactCacheEntry:
    parsed = json.loads(data)
    return ArtifactCacheEntry.from_dict(parsed)


_artifact_cache_instance: Optional[ArtifactCache] = None


def get_default_artifact_cache() -> ArtifactCache:
    global _artifact_cache_instance
    if _artifact_cache_instance is None:
        from .connection import EnhancedRedisConnection
        conn = EnhancedRedisConnection()
        _artifact_cache_instance = ArtifactCache(redis_conn=conn)
    return _artifact_cache_instance


def init_artifact_cache(redis_conn: EnhancedRedisConnection, ttl: int = DEFAULT_ARTIFACT_TTL) -> ArtifactCache:
    global _artifact_cache_instance
    _artifact_cache_instance = ArtifactCache(redis_conn=redis_conn, ttl=ttl)
    return _artifact_cache_instance


artifact_cache: Optional[ArtifactCache] = None


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
