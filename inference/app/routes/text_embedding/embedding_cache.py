import hashlib
import json
import logging
from typing import Any, Dict, List, Optional

from config import CONFIG
from .cache_backends import EmbeddingCacheBackend, get_current_cache_backend

logger = logging.getLogger(__name__)

_NON_SEMANTIC_PROPERTIES = {"input_token_limit", "max_batch_size"}
_CACHE_KEY_PREFIX = "embedding_cache:"


def _canonicalize_properties(properties: Optional[Dict]) -> Dict:
    if not properties:
        return {}
    return {k: v for k, v in sorted(properties.items())}


def generate_cache_key(
    model_schema_id: str,
    provider_model_id: Optional[str],
    text: str,
    input_type: Optional[str],
    properties: Optional[Any],
) -> str:
    properties_dict = properties.model_dump(exclude_none=True) if properties else {}
    semantic_props = {k: v for k, v in properties_dict.items() if k not in _NON_SEMANTIC_PROPERTIES}
    canonical_props = _canonicalize_properties(semantic_props)
    key_parts = {
        "model_schema_id": model_schema_id,
        "provider_model_id": provider_model_id or "",
        "text": text,
        "input_type": input_type or "",
        "properties": canonical_props,
    }
    raw = json.dumps(key_parts, sort_keys=True)
    return _CACHE_KEY_PREFIX + hashlib.sha256(raw.encode()).hexdigest()


def get_cache_backend() -> EmbeddingCacheBackend:
    return get_current_cache_backend()


def get_cache_backend_name() -> str:
    return get_current_cache_backend().name


async def get_cached(key: str, ttl: Optional[int] = None) -> Optional[List[float]]:
    if ttl is None:
        ttl = CONFIG.EMBEDDING_CACHE_TTL
    backend = get_cache_backend()
    return await backend.get(key, ttl=ttl)


async def set_cached(key: str, embedding: List[float], max_size: Optional[int] = None) -> None:
    if max_size is None:
        max_size = CONFIG.EMBEDDING_CACHE_MAX_SIZE
    backend = get_cache_backend()
    await backend.set(key, embedding, ttl=CONFIG.EMBEDDING_CACHE_TTL, max_size=max_size)


async def evict_expired(ttl: Optional[int] = None) -> int:
    if ttl is None:
        ttl = CONFIG.EMBEDDING_CACHE_TTL
    backend = get_cache_backend()
    return await backend.evict_expired(ttl=ttl)


def cache_stats() -> Dict[str, Any]:
    backend = get_cache_backend()
    stats = backend.stats()
    stats["backend"] = backend.name
    return stats
