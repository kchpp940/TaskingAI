from typing import Any, List, Optional
from dataclasses import dataclass


class KeyNamespace:
    BACKEND = "backend"
    INFERENCE = "inference"
    PLUGIN = "plugin"


class CacheCategory:
    ENTITY = "entity"
    EMBEDDING = "embedding"
    ARTIFACT = "artifact"
    SESSION = "session"
    RATE_LIMIT = "rate_limit"
    LOCK = "lock"
    META = "meta"


class QueueCategory:
    RECORD_IMPORT = "record_import"
    TASK = "task"
    EVENT = "event"
    DEAD_LETTER = "dead_letter"


@dataclass
class CacheKeyBuilder:
    service: str
    module: str
    category: str
    separator: str = ":"

    def build(self, *parts: Any, postfix: Optional[str] = None) -> str:
        key_parts: List[str] = [self.service, self.module, self.category]
        key_parts.extend(str(p) for p in parts if p is not None)
        if postfix:
            key_parts.append(postfix)
        return self.separator.join(key_parts)

    def pattern(self, *parts: Any) -> str:
        key_parts: List[str] = [self.service, self.module, self.category]
        key_parts.extend(str(p) for p in parts if p is not None)
        key_parts.append("*")
        return self.separator.join(key_parts)


def build_cache_key(
    service: str,
    module: str,
    category: str,
    *parts: Any,
    postfix: Optional[str] = None,
    separator: str = ":",
) -> str:
    key_parts: List[str] = [service, module, category]
    key_parts.extend(str(p) for p in parts if p is not None)
    if postfix:
        key_parts.append(postfix)
    return separator.join(key_parts)
