import json
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict

from tkhelper.cache import (
    QueueHelper,
    QueueConfig,
    QueueResult,
    CacheStatus,
    FallbackReason,
    build_cache_key,
    KeyNamespace,
    QueueCategory,
)
from tkhelper.error import raise_http_error, ErrorCode

from app.database import enhanced_redis_conn
from app.models import RecordType

logger = logging.getLogger(__name__)

__all__ = [
    "RecordImportJob",
    "RecordImportQueue",
    "record_import_queue",
    "enqueue_record_import",
    "dequeue_record_import",
    "get_import_queue_length",
]

RECORD_IMPORT_QUEUE_NAME = build_cache_key(
    KeyNamespace.BACKEND,
    "retrieval",
    QueueCategory.RECORD_IMPORT,
    "default",
)

RECORD_IMPORT_JOB_TTL = 3600 * 24


@dataclass
class RecordImportJob:
    job_id: str
    collection_id: str
    type: RecordType
    title: str
    content: Optional[str] = None
    file_id: Optional[str] = None
    url: Optional[str] = None
    text_splitter: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, str]] = None
    status: str = "pending"
    created_at: float = 0.0
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result["type"] = self.type.value if isinstance(self.type, RecordType) else self.type
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RecordImportJob":
        if "type" in data and isinstance(data["type"], str):
            data["type"] = RecordType(data["type"])
        return cls(**data)


def _serialize_job(job: RecordImportJob) -> str:
    return json.dumps(job.to_dict())


def _deserialize_job(data: str) -> RecordImportJob:
    job_dict = json.loads(data)
    return RecordImportJob.from_dict(job_dict)


class RecordImportQueue:
    def __init__(self):
        self._queue_helper = QueueHelper[RecordImportJob](
            redis_conn=enhanced_redis_conn,
            queue_name=RECORD_IMPORT_QUEUE_NAME,
            config=QueueConfig(
                max_retries=3,
                retry_delay=0.1,
                enable_fallback=True,
                namespace=f"{KeyNamespace.BACKEND}:retrieval",
                max_size=10000,
            ),
            namespace=f"{KeyNamespace.BACKEND}:retrieval",
        )

    async def enqueue(self, job: RecordImportJob) -> QueueResult[int]:
        result = await self._queue_helper.push(job, serializer=_serialize_job)
        if result.status in (CacheStatus.HIT, CacheStatus.FALLBACK):
            logger.info(
                f"Record import job enqueued: job_id={job.job_id}, "
                f"collection_id={job.collection_id}, "
                f"status={result.status.value}, "
                f"queue_length={result.queue_length}"
            )
        else:
            logger.error(
                f"Failed to enqueue record import job: job_id={job.job_id}, "
                f"error={result.fallback_reason}"
            )
        return result

    async def dequeue(self, timeout: int = 0) -> Optional[RecordImportJob]:
        result = await self._queue_helper.pop(
            deserializer=_deserialize_job,
            timeout=timeout,
        )
        if result.items:
            job = result.items[0]
            logger.debug(
                f"Record import job dequeued: job_id={job.job_id}, "
                f"collection_id={job.collection_id}, "
                f"status={result.status.value}"
            )
            return job
        return None

    async def length(self) -> int:
        result = await self._queue_helper.length()
        return result.queue_length

    def is_using_fallback(self) -> bool:
        return self._queue_helper.is_using_fallback()


record_import_queue = RecordImportQueue()


async def enqueue_record_import(
    collection_id: str,
    type: RecordType,
    title: str,
    content: Optional[str] = None,
    file_id: Optional[str] = None,
    url: Optional[str] = None,
    text_splitter: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, str]] = None,
    job_id: Optional[str] = None,
) -> RecordImportJob:
    import time
    from app.models import Record

    if job_id is None:
        job_id = Record.generate_random_id()

    job = RecordImportJob(
        job_id=job_id,
        collection_id=collection_id,
        type=type,
        title=title,
        content=content,
        file_id=file_id,
        url=url,
        text_splitter=text_splitter,
        metadata=metadata,
        status="pending",
        created_at=time.time(),
    )

    result = await record_import_queue.enqueue(job)

    if result.status not in (CacheStatus.HIT, CacheStatus.FALLBACK):
        raise_http_error(
            ErrorCode.INTERNAL_SERVER_ERROR,
            message="Failed to enqueue record import job",
        )

    return job


async def dequeue_record_import(timeout: int = 0) -> Optional[RecordImportJob]:
    return await record_import_queue.dequeue(timeout=timeout)


async def get_import_queue_length() -> int:
    return await record_import_queue.length()
