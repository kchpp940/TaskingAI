from app.database.connection import postgres_pool
from app.models import Record, Collection, RecordType, ImportStage, ImportStatus
from tkhelper.models import Status
from typing import Dict, Optional, List
from app.database_ops.utils import update_object
from .utils import insert_record_chunks, delete_record_chunks
import json


async def update_import_status(
    record_id: str,
    import_status: ImportStatus,
    processing_stage: Optional[ImportStage] = None,
    error_message: Optional[str] = None,
    import_params: Optional[Dict] = None,
) -> None:
    """
    Update record import status
    :param record_id: the record id
    :param import_status: the new import status
    :param processing_stage: the current processing stage
    :param error_message: the error message if failed
    :param import_params: the import params for retry
    :return: None
    """
    update_dict = {
        "import_status": import_status.value,
    }
    if processing_stage is not None:
        update_dict["processing_stage"] = processing_stage.value
    if error_message is not None:
        update_dict["error_message"] = error_message
    if import_params is not None:
        update_dict["import_params"] = json.dumps(import_params)

    async with postgres_pool.get_db_connection() as conn:
        await update_object(
            conn,
            update_dict=update_dict,
            update_time=True,
            table_name="record",
            equal_filters={"record_id": record_id},
        )


async def update_record(
    collection: Collection,
    record: Record,
    title: Optional[str],
    type: Optional[RecordType],
    content: Optional[str],
    chunk_text_list: Optional[List[str]],
    chunk_embedding_list: Optional[List[List[float]]],
    chunk_num_tokens_list: Optional[List[int]],
    metadata: Optional[Dict],
) -> None:
    """
    Update record (metadata or full content update)
    :param collection: the collection where the record belongs to
    :param record: the record to be updated
    :param title: the record title
    :param type: the record type
    :param content: the record content
    :param chunk_text_list: the text list of the chunks to be updated
    :param chunk_embedding_list: the embedding list of the chunks to be updated
    :param chunk_num_tokens_list: the num_tokens list of the chunks to be updated
    :param metadata: the record metadata
    :return: None
    """
    collection_id = collection.collection_id

    update_dict = {}
    if title is not None:
        update_dict["title"] = title
    if type is not None:
        update_dict["type"] = type.value
    if metadata is not None:
        update_dict["metadata"] = metadata
    if content is not None:
        update_dict["content"] = content

    async with postgres_pool.get_db_connection() as conn:
        async with conn.transaction():
            if chunk_text_list is not None and chunk_embedding_list is not None and chunk_num_tokens_list is not None:
                old_num_chunks = await delete_record_chunks(
                    conn=conn,
                    collection_id=collection_id,
                    record_id=record.record_id,
                )

                await insert_record_chunks(
                    conn=conn,
                    collection_id=collection_id,
                    record_id=record.record_id,
                    chunk_text_list=chunk_text_list,
                    chunk_embedding_list=chunk_embedding_list,
                    chunk_num_tokens_list=chunk_num_tokens_list,
                )

                update_dict["num_chunks"] = len(chunk_text_list)

                await conn.execute(
                    "UPDATE collection SET num_chunks = num_chunks - $1 + $2 WHERE collection_id=$3;",
                    old_num_chunks,
                    len(chunk_text_list),
                    collection_id,
                )

                collection.num_chunks = collection.num_chunks - old_num_chunks + len(chunk_text_list)

            if len(update_dict) > 0:
                await update_object(
                    conn,
                    update_dict=update_dict,
                    update_time=True,
                    table_name="record",
                    equal_filters={"record_id": record.record_id},
                )


async def update_record_chunks_and_status(
    collection: Collection,
    record_id: str,
    chunk_text_list: List[str],
    chunk_embedding_list: List[List[float]],
    chunk_num_tokens_list: List[int],
    db_content: str,
    is_retry: bool = False,
) -> None:
    """
    Update record chunks and mark import as succeeded
    :param collection: the collection
    :param record_id: the record id
    :param chunk_text_list: the text list of the chunks
    :param chunk_embedding_list: the embedding list of the chunks
    :param chunk_num_tokens_list: the num_tokens list of the chunks
    :param db_content: the db content
    :param is_retry: whether this is a retry operation
    :return: None
    """
    collection_id = collection.collection_id

    async with postgres_pool.get_db_connection() as conn:
        async with conn.transaction():
            old_num_chunks = await delete_record_chunks(
                conn=conn,
                collection_id=collection_id,
                record_id=record_id,
            )

            await insert_record_chunks(
                conn=conn,
                collection_id=collection_id,
                record_id=record_id,
                chunk_text_list=chunk_text_list,
                chunk_embedding_list=chunk_embedding_list,
                chunk_num_tokens_list=chunk_num_tokens_list,
            )

            update_dict = {
                "import_status": ImportStatus.SUCCEEDED.value,
                "processing_stage": ImportStage.COMPLETED.value,
                "error_message": None,
                "import_params": None,
                "content": db_content,
                "num_chunks": len(chunk_text_list),
            }

            await update_object(
                conn,
                update_dict=update_dict,
                update_time=True,
                table_name="record",
                equal_filters={"record_id": record_id},
            )

            chunk_diff = len(chunk_text_list) - old_num_chunks
            if chunk_diff != 0:
                await conn.execute(
                    "UPDATE collection SET num_chunks = num_chunks + $1 WHERE collection_id=$2;",
                    chunk_diff,
                    collection_id,
                )

            if not is_retry:
                await conn.execute(
                    "UPDATE collection SET num_records = num_records + 1 WHERE collection_id=$1;",
                    collection_id,
                )
