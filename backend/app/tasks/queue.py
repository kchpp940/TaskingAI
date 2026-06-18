import asyncio
import json
import logging
import time
from typing import Optional, Dict, List
from dataclasses import dataclass, asdict

from app.database import redis_conn
from app.models import Record, ImportStatus, ImportStage, RecordType, TextSplitter, Collection
from app.database_ops.retrieval import record as db_record

logger = logging.getLogger(__name__)

QUEUE_KEY = "record_import:queue"
PROCESSING_KEY_PREFIX = "record_import:processing:"
PROCESSING_TTL = 600
TIMEOUT_SCAN_INTERVAL = 300
STALE_THRESHOLD_SECONDS = 600


@dataclass
class ImportTaskPayload:
    import_attempt_id: str
    task_type: str
    collection_id: str
    record_id: str
    type: str
    title: str
    text_splitter: Dict
    content: Optional[str] = None
    file_id: Optional[str] = None
    url: Optional[str] = None
    start_stage: str = ImportStage.CONTENT_LOADING.value
    existing_record_chunks: int = 0
    is_retry: bool = False

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> "ImportTaskPayload":
        return cls(**data)


class RecordImportQueue:
    _instance = None
    _lock = asyncio.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "initialized"):
            self.initialized = False
            self._worker_task: Optional[asyncio.Task] = None
            self._scan_task: Optional[asyncio.Task] = None
            self._running = False

    async def enqueue(self, payload: ImportTaskPayload) -> bool:
        if redis_conn.redis is None:
            logger.error("Redis not initialized, cannot enqueue task")
            return False

        task_key = PROCESSING_KEY_PREFIX + payload.record_id

        try:
            pipeline = redis_conn.redis.pipeline()
            pipeline.set(task_key, json.dumps(payload.to_dict()), ex=PROCESSING_TTL, nx=True)
            pipeline.lpush(QUEUE_KEY, json.dumps(payload.to_dict()))
            results = await pipeline.execute()

            if results[0] is None:
                logger.warning(f"Task already in progress for record_id={payload.record_id}")
                return False

            logger.info(
                f"Enqueued import task: record_id={payload.record_id}, "
                f"task_type={payload.task_type}, queue_length={results[1]}"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to enqueue task for record_id={payload.record_id}: {e}")
            return False

    async def dequeue(self) -> Optional[ImportTaskPayload]:
        if redis_conn.redis is None:
            return None

        try:
            result = await redis_conn.redis.brpop(QUEUE_KEY, timeout=5)
            if result is None:
                return None

            _, payload_json = result
            payload = ImportTaskPayload.from_dict(json.loads(payload_json))
            logger.info(f"Dequeued import task: record_id={payload.record_id}")
            return payload
        except Exception as e:
            logger.error(f"Failed to dequeue task: {e}")
            await asyncio.sleep(1)
            return None

    async def complete(self, record_id: str) -> None:
        if redis_conn.redis is None:
            return

        task_key = PROCESSING_KEY_PREFIX + record_id
        try:
            await redis_conn.redis.delete(task_key)
            logger.info(f"Completed task for record_id={record_id}")
        except Exception as e:
            logger.error(f"Failed to complete task for record_id={record_id}: {e}")

    async def fail(self, record_id: str, error_message: str) -> None:
        if redis_conn.redis is None:
            return

        task_key = PROCESSING_KEY_PREFIX + record_id
        try:
            await redis_conn.redis.delete(task_key)
            logger.warning(f"Task failed for record_id={record_id}: {error_message}")
        except Exception as e:
            logger.error(f"Failed to mark task as failed for record_id={record_id}: {e}")

    async def _verify_attempt(self, payload: ImportTaskPayload) -> bool:
        """
        Verify that the task's import_attempt_id matches the record's current import_attempt_id.
        If they don't match, the task is stale and should be discarded.
        """
        try:
            from app.database import postgres_pool

            async with postgres_pool.get_db_connection() as conn:
                row = await conn.fetchrow(
                    "SELECT import_attempt_id FROM record WHERE record_id = $1",
                    payload.record_id,
                )

            if row is None:
                logger.warning(f"Record not found for attempt verification: record_id={payload.record_id}")
                return False

            current_attempt_id = row.get("import_attempt_id")
            if current_attempt_id != payload.import_attempt_id:
                logger.info(
                    f"Attempt mismatch for record_id={payload.record_id}: "
                    f"task_attempt={payload.import_attempt_id}, db_attempt={current_attempt_id}"
                )
                return False

            return True
        except Exception as e:
            logger.error(f"Failed to verify attempt for record_id={payload.record_id}: {e}")
            return False

    async def _requeue_stale_tasks(self) -> None:
        if redis_conn.redis is None:
            return

        try:
            from app.database import postgres_pool

            async with postgres_pool.get_db_connection() as conn:
                rows = await conn.fetch(
                    """
                    SELECT record_id, collection_id, import_status, processing_stage, 
                           import_params, import_attempt_id, updated_timestamp
                    FROM record
                    WHERE import_status IN ($1, $2)
                    AND updated_timestamp < $3
                    """,
                    ImportStatus.PENDING.value,
                    ImportStatus.PROCESSING.value,
                    int(time.time()) - STALE_THRESHOLD_SECONDS,
                )

            requeued_count = 0
            for row in rows:
                record_id = row["record_id"]
                task_key = PROCESSING_KEY_PREFIX + record_id

                is_processing = await redis_conn.redis.exists(task_key)
                if is_processing:
                    continue

                import_params = row.get("import_params")
                if not import_params:
                    logger.warning(f"No import_params for stale record_id={record_id}, skipping")
                    continue

                try:
                    import_params_dict = json.loads(import_params) if isinstance(import_params, str) else import_params
                except Exception:
                    logger.warning(f"Invalid import_params for stale record_id={record_id}, skipping")
                    continue

                payload = ImportTaskPayload(
                    import_attempt_id=row.get("import_attempt_id") or "",
                    task_type="recovery",
                    collection_id=row["collection_id"],
                    record_id=record_id,
                    type=import_params_dict.get("type"),
                    title=import_params_dict.get("title"),
                    text_splitter=import_params_dict.get("text_splitter"),
                    content=import_params_dict.get("content"),
                    file_id=import_params_dict.get("file_id"),
                    url=import_params_dict.get("url"),
                    start_stage=row.get("processing_stage") or ImportStage.CONTENT_LOADING.value,
                    existing_record_chunks=0,
                    is_retry=True,
                )

                await db_record.update_import_status(
                    record_id=record_id,
                    import_status=ImportStatus.PENDING,
                    processing_stage=ImportStage.PENDING,
                    error_message=None,
                )

                success = await self.enqueue(payload)
                if success:
                    requeued_count += 1
                    logger.info(f"Requeued stale task: record_id={record_id}")

            if requeued_count > 0:
                logger.info(f"Requeued {requeued_count} stale import tasks")

        except Exception as e:
            logger.error(f"Failed to scan and requeue stale tasks: {e}")

    async def _worker_loop(self) -> None:
        logger.info("Starting record import worker loop...")
        from app.tasks.record_import import _execute_import_task

        while self._running:
            try:
                payload = await self.dequeue()
                if payload is None:
                    continue

                try:
                    if not await self._verify_attempt(payload):
                        logger.warning(
                            f"Discarding stale task: record_id={payload.record_id}, "
                            f"attempt_id={payload.import_attempt_id}"
                        )
                        await self.complete(payload.record_id)
                        continue

                    await _execute_import_task(payload)
                    await self.complete(payload.record_id)
                except Exception as e:
                    error_msg = str(e) if str(e) else "Unknown error"
                    await self.fail(payload.record_id, error_msg)

            except asyncio.CancelledError:
                logger.info("Worker loop cancelled")
                break
            except Exception as e:
                logger.error(f"Worker loop error: {e}")
                await asyncio.sleep(1)

        logger.info("Record import worker loop stopped")

    async def _scan_loop(self) -> None:
        logger.info("Starting stale task scanner...")

        while self._running:
            try:
                await self._requeue_stale_tasks()
            except asyncio.CancelledError:
                logger.info("Scanner loop cancelled")
                break
            except Exception as e:
                logger.error(f"Scanner loop error: {e}")

            try:
                await asyncio.sleep(TIMEOUT_SCAN_INTERVAL)
            except asyncio.CancelledError:
                break

        logger.info("Stale task scanner stopped")

    async def start(self) -> None:
        async with self._lock:
            if self._running:
                return

            self._running = True
            self.initialized = True

            await self._requeue_stale_tasks()

            self._worker_task = asyncio.create_task(self._worker_loop())
            self._scan_task = asyncio.create_task(self._scan_loop())

            logger.info("Record import queue started")

    async def stop(self) -> None:
        async with self._lock:
            if not self._running:
                return

            self._running = False

            if self._worker_task and not self._worker_task.done():
                self._worker_task.cancel()
                try:
                    await self._worker_task
                except asyncio.CancelledError:
                    pass

            if self._scan_task and not self._scan_task.done():
                self._scan_task.cancel()
                try:
                    await self._scan_task
                except asyncio.CancelledError:
                    pass

            logger.info("Record import queue stopped")


record_import_queue = RecordImportQueue()

__all__ = [
    "RecordImportQueue",
    "ImportTaskPayload",
    "record_import_queue",
    "QUEUE_KEY",
    "PROCESSING_KEY_PREFIX",
]
