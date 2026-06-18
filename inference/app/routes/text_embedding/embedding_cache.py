import hashlib
import json
import asyncio
import time
import logging
from typing import Any, Dict, List, Optional, Tuple
from config import CONFIG

logger = logging.getLogger(__name__)

_cache: Dict[str, Tuple[List[float], float]] = {}
_lock = asyncio.Lock()

_NON_SEMANTIC_PROPERTIES = {"input_token_limit", "max_batch_size"}


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
    return hashlib.sha256(raw.encode()).hexdigest()


async def get_cached(key: str, ttl: Optional[int] = None) -> Optional[List[float]]:
    if ttl is None:
        ttl = CONFIG.EMBEDDING_CACHE_TTL
    async with _lock:
        entry = _cache.get(key)
        if entry is None:
            return None
        embedding, ts = entry
        if time.time() - ts > ttl:
            del _cache[key]
            return None
        return embedding


async def set_cached(key: str, embedding: List[float], max_size: Optional[int] = None) -> None:
    if max_size is None:
        max_size = CONFIG.EMBEDDING_CACHE_MAX_SIZE
    async with _lock:
        if len(_cache) >= max_size:
            _evict_oldest(max_size // 2)
        _cache[key] = (embedding, time.time())


def _evict_oldest(remove_count: int) -> None:
    sorted_items = sorted(_cache.items(), key=lambda item: item[1][1])
    for key, _ in sorted_items[:remove_count]:
        del _cache[key]


async def evict_expired(ttl: Optional[int] = None) -> int:
    if ttl is None:
        ttl = CONFIG.EMBEDDING_CACHE_TTL
    async with _lock:
        now = time.time()
        expired_keys = [k for k, (_, ts) in _cache.items() if now - ts > ttl]
        for k in expired_keys:
            del _cache[k]
        if expired_keys:
            logger.info(f"embedding_cache: evicted {len(expired_keys)} expired entries")
        return len(expired_keys)


def cache_stats() -> Dict[str, int]:
    return {"size": len(_cache)}
