from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Optional, Dict, TypeVar, Generic
from datetime import datetime

T = TypeVar("T")

DEFAULT_TTL = 3600 * 4
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAY = 0.1
DEFAULT_HEALTH_CHECK_THRESHOLD = 10


class CacheStatus(str, Enum):
    HIT = "hit"
    MISS = "miss"
    ERROR = "error"
    FALLBACK = "fallback"
    STALE = "stale"


class FallbackReason(str, Enum):
    REDIS_UNAVAILABLE = "redis_unavailable"
    CONNECTION_ERROR = "connection_error"
    TIMEOUT = "timeout"
    SERIALIZATION_ERROR = "serialization_error"
    KEY_NOT_FOUND = "key_not_found"
    EXPLICIT_FALLBACK = "explicit_fallback"


class OperationType(str, Enum):
    GET = "get"
    SET = "set"
    DELETE = "delete"
    PUSH = "push"
    POP = "pop"
    LEN = "len"


@dataclass
class CacheConfig:
    ttl: int = DEFAULT_TTL
    max_retries: int = DEFAULT_MAX_RETRIES
    retry_delay: float = DEFAULT_RETRY_DELAY
    enable_fallback: bool = True
    namespace: str = "default"
    stale_while_revalidate: bool = False
    stale_ttl: int = 0


@dataclass
class QueueConfig:
    max_retries: int = DEFAULT_MAX_RETRIES
    retry_delay: float = DEFAULT_RETRY_DELAY
    enable_fallback: bool = True
    namespace: str = "default"
    max_size: int = 10000


@dataclass
class CacheResult(Generic[T]):
    value: Optional[T] = None
    status: CacheStatus = CacheStatus.MISS
    fallback_reason: Optional[FallbackReason] = None
    latency_ms: float = 0.0
    retry_count: int = 0
    ttl_remaining: Optional[int] = None

    @property
    def hit(self) -> bool:
        return self.status == CacheStatus.HIT

    @property
    def failed(self) -> bool:
        return self.status in (CacheStatus.ERROR,)


@dataclass
class QueueResult(Generic[T]):
    items: list = field(default_factory=list)
    status: CacheStatus = CacheStatus.MISS
    fallback_reason: Optional[FallbackReason] = None
    latency_ms: float = 0.0
    retry_count: int = 0
    queue_length: int = 0


@dataclass
class CacheLogContext:
    cache_key: str
    operation: OperationType
    status: CacheStatus
    namespace: str
    latency_ms: float = 0.0
    fallback_reason: Optional[FallbackReason] = None
    retry_count: int = 0
    ttl: Optional[int] = None
    value_size: Optional[int] = None
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "cache_key": self.cache_key,
            "operation": self.operation.value,
            "status": self.status.value,
            "namespace": self.namespace,
            "latency_ms": round(self.latency_ms, 3),
            "retry_count": self.retry_count,
        }
        if self.fallback_reason:
            result["fallback_reason"] = self.fallback_reason.value
        if self.ttl is not None:
            result["ttl"] = self.ttl
        if self.value_size is not None:
            result["value_size"] = self.value_size
        if self.error_message:
            result["error_message"] = self.error_message
        return result
