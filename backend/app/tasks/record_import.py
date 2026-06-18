import asyncio
import logging
from typing import Optional, Dict
from dataclasses import dataclass

from app.models import Collection, RecordType, TextSplitter, ImportStage, ImportStatus
from app.database import redis_pool
from app.operators.retrieval import collection_ops
from app.database_ops.retrieval import record as db_record
from app.operators.retrieval.record import _process_import_stages

logger = logging.getLogger(__name__)

TASK_LOCK_KEY = "record_import:lock:{record_id}"
TASK_LOCK_TTL = 3600


@dataclass
class RecordImportTask:
    task_type: str
    collection_id: str
    record_id: str
    type: RecordType
    title: str
    text_splitter: TextSplitter
    content: Optional[str] = None
    file_id: Optional[str] = None
    url: Optional[str] = None
    start_stage: ImportStage = ImportStage.CONTENT_LOADING
    existing_record_chunks: int = 0
    is_retry: bool = False


async def _acquire_task_lock(record_id: str) -> bool:
    if redis_pool.redis is None:
        return True

    lock_key = TASK_LOCK_KEY.format(record_id=record_id)
    result = await redis_pool.redis.set(lock_key, "1", ex=TASK_LOCK_TTL, nx=True)
    return result is not None


async def _release_task_lock(record_id: str) -> None:
    if redis_pool.redis is None:
        return

    lock_key = TASK_LOCK_KEY.format(record_id=record_id)
    await redis_pool.redis.delete(lock_key)


async def _execute_import_task(task: RecordImportTask) -> None:
    """
    Execute the record import task in background
    :param task: the import task to execute
    """
    logger.info(
        f"Starting record import task: record_id={task.record_id}, "
        f"task_type={task.task_type}, start_stage={task.start_stage}"
    )

    collection: Optional[Collection] = None
    try:
        collection = await collection_ops.get(collection_id=task.collection_id)

        await _process_import_stages(
            collection=collection,
            record_id=task.record_id,
            type=task.type,
            title=task.title,
            text_splitter=task.text_splitter,
            content=task.content,
            file_id=task.file_id,
            url=task.url,
            start_stage=task.start_stage,
            existing_record_chunks=task.existing_record_chunks,
            is_retry=task.is_retry,
        )

        logger.info(f"Record import task succeeded: record_id={task.record_id}")

    except Exception as e:
        error_msg = str(e) if str(e) else "Unknown error occurred during import"
        logger.error(
            f"Record import task failed: record_id={task.record_id}, "
            f"error={error_msg}"
        )
        import_params = {
            "type": task.type.value,
            "title": task.title,
            "content": task.content,
            "file_id": task.file_id,
            "url": task.url,
            "text_splitter": task.text_splitter.model_dump(),
        }
        try:
            await db_record.update_import_status(
                record_id=task.record_id,
                import_status=ImportStatus.FAILED,
                error_message=error_msg,
                import_params=import_params,
            )
        except Exception as update_err:
            logger.error(
                f"Failed to update import status for record_id={task.record_id}: {update_err}"
            )
    finally:
        await _release_task_lock(task.record_id)


async def submit_record_import_task(
    collection_id: str,
    record_id: str,
    type: RecordType,
    title: str,
    text_splitter: TextSplitter,
    content: Optional[str] = None,
    file_id: Optional[str] = None,
    url: Optional[str] = None,
) -> bool:
    """
    Submit a record import task to background
    :return: True if task was submitted, False if task already running
    """
    lock_acquired = await _acquire_task_lock(record_id)
    if not lock_acquired:
        logger.warning(
            f"Record import task already running for record_id={record_id}, skipping"
        )
        return False

    task = RecordImportTask(
        task_type="create",
        collection_id=collection_id,
        record_id=record_id,
        type=type,
        title=title,
        text_splitter=text_splitter,
        content=content,
        file_id=file_id,
        url=url,
        start_stage=ImportStage.CONTENT_LOADING,
        existing_record_chunks=0,
        is_retry=False,
    )

    asyncio.create_task(_execute_import_task(task))
    logger.info(f"Submitted record import task: record_id={record_id}")
    return True


async def submit_record_update_task(
    collection_id: str,
    record_id: str,
    type: RecordType,
    title: str,
    text_splitter: TextSplitter,
    content: Optional[str] = None,
    file_id: Optional[str] = None,
    url: Optional[str] = None,
    existing_record_chunks: int = 0,
) -> bool:
    """
    Submit a record update task to background
    :return: True if task was submitted, False if task already running
    """
    lock_acquired = await _acquire_task_lock(record_id)
    if not lock_acquired:
        logger.warning(
            f"Record update task already running for record_id={record_id}, skipping"
        )
        return False

    task = RecordImportTask(
        task_type="update",
        collection_id=collection_id,
        record_id=record_id,
        type=type,
        title=title,
        text_splitter=text_splitter,
        content=content,
        file_id=file_id,
        url=url,
        start_stage=ImportStage.CONTENT_LOADING,
        existing_record_chunks=existing_record_chunks,
        is_retry=False,
    )

    asyncio.create_task(_execute_import_task(task))
    logger.info(f"Submitted record update task: record_id={record_id}")
    return True


async def submit_record_retry_task(
    collection_id: str,
    record_id: str,
    type: RecordType,
    title: str,
    text_splitter: TextSplitter,
    start_stage: ImportStage,
    content: Optional[str] = None,
    file_id: Optional[str] = None,
    url: Optional[str] = None,
    existing_record_chunks: int = 0,
) -> bool:
    """
    Submit a record retry task to background
    :return: True if task was submitted, False if task already running
    """
    lock_acquired = await _acquire_task_lock(record_id)
    if not lock_acquired:
        logger.warning(
            f"Record retry task already running for record_id={record_id}, skipping"
        )
        return False

    task = RecordImportTask(
        task_type="retry",
        collection_id=collection_id,
        record_id=record_id,
        type=type,
        title=title,
        text_splitter=text_splitter,
        content=content,
        file_id=file_id,
        url=url,
        start_stage=start_stage,
        existing_record_chunks=existing_record_chunks,
        is_retry=True,
    )

    asyncio.create_task(_execute_import_task(task))
    logger.info(f"Submitted record retry task: record_id={record_id}, start_stage={start_stage}")
    return True
