import hashlib
import json
import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field

from config import CONFIG
from .base import CacheConfig, CacheStatus, CacheHelper
from .key_namespace import KeyNamespace, CacheCategory, build_cache_key
from .connection import EnhancedRedisConnection

logger = logging.getLogger(__name__)

__all__ = [
    "TextEmbeddingCacheEntry",
    "TextEmbeddingCache",
    "text_embedding_cache",
    "get_embedding_cache",
    "set_embedding_cache",
]

EMBEDDING_CACHE_NAMESPACE = f"{KeyNamespace.INFERENCE}:embedding"


@dataclass
class TextEmbeddingCacheEntry:
    text: str
    embedding: List[float]
    model_schema_id: str
    provider_model_id: str
    embedding_size: int
    created_at: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "embedding": self.embedding,
            "model_schema_id": self.model_schema_id,
            "provider_model_id": self.provider_model_id,
            "embedding_size": self.embedding_size,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TextEmbeddingCacheEntry":
        return cls(**data)


def _generate_cache_key(
    text: str,
    model_schema_id: str,
    provider_model_id: str,
) -> str:
    text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
    return build_cache_key(
        KeyNamespace.INFERENCE,
        "embedding",
        CacheCategory.EMBEDDING,
        model_schema_id,
        provider_model_id,
        text_hash,
    )


def _serialize_entry(entry: TextEmbeddingCacheEntry) -> str:
    return json.dumps(entry.to_dict())


def _deserialize_entry(data: str) -> TextEmbeddingCacheEntry:
    return TextEmbeddingCacheEntry.from_dict(json.loads(data))


class TextEmbeddingCache:
    def __init__(self, redis_conn: Optional[EnhancedRedisConnection] = None):
        if redis_conn is None and hasattr(CONFIG, "REDIS_URL") and CONFIG.REDIS_URL:
            redis_conn = EnhancedRedisConnection(url=CONFIG.REDIS_URL, name="inference")
        elif redis_conn is None:
            redis_conn = EnhancedRedisConnection(url="", name="inference")

        self.redis_conn = redis_conn
        ttl = CONFIG.EMBEDDING_CACHE_TTL if hasattr(CONFIG, "EMBEDDING_CACHE_TTL") else 3600 * 24 * 7
        self._cache_helper = CacheHelper[TextEmbeddingCacheEntry](
            redis_conn=redis_conn,
            config=CacheConfig(
                ttl=ttl,
                max_retries=2,
                retry_delay=0.05,
                enable_fallback=True,
                namespace=EMBEDDING_CACHE_NAMESPACE,
            ),
            namespace=EMBEDDING_CACHE_NAMESPACE,
        )
        self._enabled = CONFIG.ENABLE_EMBEDDING_CACHE if hasattr(CONFIG, "ENABLE_EMBEDDING_CACHE") else True

    async def init(self):
        if self.redis_conn and self._enabled:
            await self.redis_conn.init()

    async def close(self):
        if self.redis_conn:
            await self.redis_conn.close()

    async def get(
        self,
        text: str,
        model_schema_id: str,
        provider_model_id: str,
    ) -> Optional[TextEmbeddingCacheEntry]:
        if not self._enabled:
            return None

        key = _generate_cache_key(text, model_schema_id, provider_model_id)
        result = await self._cache_helper.get(key, deserializer=_deserialize_entry)

        if result.hit and result.value:
            logger.debug(
                f"Embedding cache hit: model={model_schema_id}/{provider_model_id} "
                f"text_len={len(text)} latency={result.latency_ms:.2f}ms"
            )
            return result.value
        elif result.status == CacheStatus.FALLBACK and result.value:
            logger.debug(
                f"Embedding cache fallback hit: model={model_schema_id}/{provider_model_id} "
                f"fallback_reason={result.fallback_reason}"
            )
            return result.value
        else:
            logger.debug(
                f"Embedding cache miss: model={model_schema_id}/{provider_model_id} "
                f"text_len={len(text)}"
            )
            return None

    async def set(
        self,
        text: str,
        embedding: List[float],
        model_schema_id: str,
        provider_model_id: str,
        embedding_size: int,
    ) -> bool:
        if not self._enabled:
            return False

        import time

        key = _generate_cache_key(text, model_schema_id, provider_model_id)
        entry = TextEmbeddingCacheEntry(
            text=text,
            embedding=embedding,
            model_schema_id=model_schema_id,
            provider_model_id=provider_model_id,
            embedding_size=embedding_size,
            created_at=time.time(),
        )

        result = await self._cache_helper.set(key, entry, serializer=_serialize_entry)

        if result.hit:
            logger.debug(
                f"Embedding cache set: model={model_schema_id}/{provider_model_id} "
                f"text_len={len(text)} latency={result.latency_ms:.2f}ms"
            )
        elif result.status == CacheStatus.FALLBACK:
            logger.debug(
                f"Embedding cache set (fallback): model={model_schema_id}/{provider_model_id} "
                f"fallback_reason={result.fallback_reason}"
            )

        return result.hit or result.status == CacheStatus.FALLBACK

    async def delete(
        self,
        text: str,
        model_schema_id: str,
        provider_model_id: str,
    ) -> bool:
        if not self._enabled:
            return False

        key = _generate_cache_key(text, model_schema_id, provider_model_id)
        result = await self._cache_helper.delete(key)
        return result.hit or result.status == CacheStatus.FALLBACK

    def is_available(self) -> bool:
        return self._enabled and self.redis_conn.is_available()

    def is_using_fallback(self) -> bool:
        return self._enabled and not self.redis_conn.is_available()


text_embedding_cache = TextEmbeddingCache()


async def get_embedding_cache(
    text: str,
    model_schema_id: str,
    provider_model_id: str,
) -> Optional[List[float]]:
    entry = await text_embedding_cache.get(text, model_schema_id, provider_model_id)
    return entry.embedding if entry else None


async def set_embedding_cache(
    text: str,
    embedding: List[float],
    model_schema_id: str,
    provider_model_id: str,
    embedding_size: int,
) -> bool:
    return await text_embedding_cache.set(
        text, embedding, model_schema_id, provider_model_id, embedding_size
    )
