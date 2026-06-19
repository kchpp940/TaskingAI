import logging
import time
import asyncio
from typing import Any, Dict, Optional

from .base import CacheLogContext, CacheStatus, OperationType, FallbackReason

logger = logging.getLogger(__name__)


class StructuredCacheLogger:
    def __init__(self, name: str = "common.cache"):
        self._logger = logging.getLogger(name)

    def _log(self, level: int, context: CacheLogContext, extra: Optional[Dict[str, Any]] = None):
        log_dict = context.to_dict()
        if extra:
            log_dict.update(extra)

        message = (
            f"cache op={context.operation.value} "
            f"status={context.status.value} "
            f"key={context.cache_key} "
            f"latency={context.latency_ms:.3f}ms"
        )

        if context.fallback_reason:
            message += f" fallback={context.fallback_reason.value}"
        if context.error_message:
            message += f" error={context.error_message}"

        self._logger.log(level, message, extra={"cache": log_dict})

    def debug(self, context: CacheLogContext, extra: Optional[Dict[str, Any]] = None):
        self._log(logging.DEBUG, context, extra)

    def info(self, context: CacheLogContext, extra: Optional[Dict[str, Any]] = None):
        self._log(logging.INFO, context, extra)

    def warning(self, context: CacheLogContext, extra: Optional[Dict[str, Any]] = None):
        self._log(logging.WARNING, context, extra)

    def error(self, context: CacheLogContext, extra: Optional[Dict[str, Any]] = None):
        self._log(logging.ERROR, context, extra)


_default_logger = StructuredCacheLogger()


def get_cache_logger() -> StructuredCacheLogger:
    return _default_logger


class CacheOperationTimer:
    def __init__(
        self,
        cache_key: str,
        operation: OperationType,
        namespace: str,
        logger: Optional[StructuredCacheLogger] = None,
    ):
        self.cache_key = cache_key
        self.operation = operation
        self.namespace = namespace
        self.logger = logger or _default_logger
        self.start_time: float = time.time()
        self.retry_count: int = 0
        self.ttl: Optional[int] = None
        self.value_size: Optional[int] = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        latency_ms = (time.time() - self.start_time) * 1000

        if exc_val is not None and not isinstance(exc_val, asyncio.CancelledError):
            context = CacheLogContext(
                cache_key=self.cache_key,
                operation=self.operation,
                status=CacheStatus.ERROR,
                namespace=self.namespace,
                latency_ms=latency_ms,
                retry_count=self.retry_count,
                ttl=self.ttl,
                value_size=self.value_size,
                error_message=str(exc_val),
            )
            self.logger.error(context)
        return False

    def record(
        self,
        status: CacheStatus,
        fallback_reason: Optional[FallbackReason] = None,
        error_message: Optional[str] = None,
    ) -> CacheLogContext:
        latency_ms = (time.time() - self.start_time) * 1000
        context = CacheLogContext(
            cache_key=self.cache_key,
            operation=self.operation,
            status=status,
            namespace=self.namespace,
            latency_ms=latency_ms,
            fallback_reason=fallback_reason,
            retry_count=self.retry_count,
            ttl=self.ttl,
            value_size=self.value_size,
            error_message=error_message,
        )

        if status == CacheStatus.ERROR:
            self.logger.error(context)
        elif status == CacheStatus.FALLBACK:
            self.logger.warning(context)
        elif status == CacheStatus.HIT:
            self.logger.debug(context)
        else:
            self.logger.debug(context)

        return context
