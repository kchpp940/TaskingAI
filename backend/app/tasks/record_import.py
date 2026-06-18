import logging
from typing import Optional

from app.models import Collection, RecordType, TextSplitter, ImportStage, ImportStatus
from app.operators.retrieval import collection_ops
from app.database_ops.retrieval import record as db_record
from app.operators.retrieval.record import _process_import_stages
from .queue import ImportTaskPayload, record_import_queue

logger = logging.getLogger(__name__)


async def _execute_import_task(payload: ImportTaskPayload) -> None:
    """
    Execute the record import task (called by worker loop)
    :param payload: the import task payload
    """
    logger.info(
        f"Executing record import task: record_id={payload.record_id}, "
        f"task_type={payload.task_type}, start_stage={payload.start_stage}, "
        f"attempt_id={payload.import_attempt_id}"
    )

    collection: Optional[Collection] = None
    try:
        collection = await collection_ops.get(collection_id=payload.collection_id)

        type = RecordType(payload.type)
        text_splitter = TextSplitter(**payload.text_splitter)
        start_stage = ImportStage(payload.start_stage)

        await _process_import_stages(
            collection=collection,
            record_id=payload.record_id,
            type=type,
            title=payload.title,
            text_splitter=text_splitter,
            content=payload.content,
            file_id=payload.file_id,
            url=payload.url,
            start_stage=start_stage,
            existing_record_chunks=payload.existing_record_chunks,
            is_retry=payload.is_retry,
        )

        logger.info(f"Record import task succeeded: record_id={payload.record_id}, attempt_id={payload.import_attempt_id}")

    except Exception as e:
        error_msg = str(e) if str(e) else "Unknown error occurred during import"
        logger.error(
            f"Record import task failed: record_id={payload.record_id}, "
            f"attempt_id={payload.import_attempt_id}, error={error_msg}"
        )
        import_params = {
            "type": payload.type,
            "title": payload.title,
            "content": payload.content,
            "file_id": payload.file_id,
            "url": payload.url,
            "text_splitter": payload.text_splitter,
        }
        try:
            await db_record.update_import_status(
                record_id=payload.record_id,
                import_status=ImportStatus.FAILED,
                error_message=error_msg,
                import_params=import_params,
            )
        except Exception as update_err:
            logger.error(
                f"Failed to update import status for record_id={payload.record_id}: {update_err}"
            )
        raise


async def submit_record_import_task(
    collection_id: str,
    record_id: str,
    type: RecordType,
    title: str,
    text_splitter: TextSplitter,
    import_attempt_id: str,
    content: Optional[str] = None,
    file_id: Optional[str] = None,
    url: Optional[str] = None,
) -> bool:
    """
    Submit a record import task to the queue
    :return: True if task was enqueued, False if task already running
    """
    payload = ImportTaskPayload(
        import_attempt_id=import_attempt_id,
        task_type="create",
        collection_id=collection_id,
        record_id=record_id,
        type=type.value,
        title=title,
        text_splitter=text_splitter.model_dump(),
        content=content,
        file_id=file_id,
        url=url,
        start_stage=ImportStage.CONTENT_LOADING.value,
        existing_record_chunks=0,
        is_retry=False,
    )

    return await record_import_queue.enqueue(payload)


async def submit_record_update_task(
    collection_id: str,
    record_id: str,
    type: RecordType,
    title: str,
    text_splitter: TextSplitter,
    import_attempt_id: str,
    content: Optional[str] = None,
    file_id: Optional[str] = None,
    url: Optional[str] = None,
    existing_record_chunks: int = 0,
) -> bool:
    """
    Submit a record update task to the queue
    :return: True if task was enqueued, False if task already running
    """
    payload = ImportTaskPayload(
        import_attempt_id=import_attempt_id,
        task_type="update",
        collection_id=collection_id,
        record_id=record_id,
        type=type.value,
        title=title,
        text_splitter=text_splitter.model_dump(),
        content=content,
        file_id=file_id,
        url=url,
        start_stage=ImportStage.CONTENT_LOADING.value,
        existing_record_chunks=existing_record_chunks,
        is_retry=False,
    )

    return await record_import_queue.enqueue(payload)


async def submit_record_retry_task(
    collection_id: str,
    record_id: str,
    type: RecordType,
    title: str,
    text_splitter: TextSplitter,
    start_stage: ImportStage,
    import_attempt_id: str,
    content: Optional[str] = None,
    file_id: Optional[str] = None,
    url: Optional[str] = None,
    existing_record_chunks: int = 0,
) -> bool:
    """
    Submit a record retry task to the queue
    :return: True if task was enqueued, False if task already running
    """
    payload = ImportTaskPayload(
        import_attempt_id=import_attempt_id,
        task_type="retry",
        collection_id=collection_id,
        record_id=record_id,
        type=type.value,
        title=title,
        text_splitter=text_splitter.model_dump(),
        content=content,
        file_id=file_id,
        url=url,
        start_stage=start_stage.value,
        existing_record_chunks=existing_record_chunks,
        is_retry=True,
    )

    return await record_import_queue.enqueue(payload)
