from typing import Dict, Optional, Tuple, List
import json

from tkhelper.models.operator.postgres_operator import PostgresModelOperator, ModelEntity
from tkhelper.error import raise_http_error, ErrorCode, raise_request_validation_error

from app.database import postgres_pool
from app.models import Record, RecordType, TextSplitter, Collection, ImportStage, ImportStatus
from app.database_ops.retrieval import record as db_record
from app.services.retrieval.content_loader import load_db_content, load_content_to_split
from app.tasks.record_import import (
    submit_record_import_task,
    submit_record_update_task,
    submit_record_retry_task,
)

from .collection import collection_ops
from ..model import model_ops

__all__ = ["record_ops"]


async def _load_content_stage(
    type: RecordType,
    content: Optional[str] = None,
    file_id: Optional[str] = None,
    url: Optional[str] = None,
) -> Tuple[str, str]:
    """
    Stage 1: Load content from source
    :param type: record type
    :param content: text content
    :param file_id: file id
    :param url: web url
    :return: tuple of (db_content, content_to_split)
    """
    db_content = await load_db_content(
        record_type=type,
        content=content,
        file_id=file_id,
        url=url,
    )

    content_to_split = await load_content_to_split(
        record_type=type,
        content=content,
        file_id=file_id,
        url=url,
    )

    return db_content, content_to_split


async def _chunking_stage(
    title: str,
    content_to_split: str,
    text_splitter: TextSplitter,
) -> Tuple[List[str], List[int]]:
    """
    Stage 2: Split content into chunks
    :param title: record title
    :param content_to_split: content to split
    :param text_splitter: text splitter configuration
    :return: tuple of (chunk_text_list, num_tokens_list)
    """
    chunk_text_list, num_tokens_list = text_splitter.split_text(text=content_to_split, title=title)
    return chunk_text_list, num_tokens_list


async def _embedding_stage(
    collection: Collection,
    chunk_text_list: List[str],
) -> List[List[float]]:
    """
    Stage 3: Generate embeddings for chunks
    :param collection: collection object
    :param chunk_text_list: list of chunk texts
    :return: list of embeddings
    """
    from app.services.retrieval.embedding import embed_documents

    embedding_model = await model_ops.get(model_id=collection.embedding_model_id)

    embeddings = await embed_documents(
        documents=chunk_text_list,
        embedding_model=embedding_model,
        embedding_size=collection.embedding_size,
    )

    return embeddings


async def _writing_chunks_stage(
    collection: Collection,
    record_id: str,
    chunk_text_list: List[str],
    num_tokens_list: List[int],
    embeddings: List[List[float]],
    db_content: str,
    is_retry: bool = False,
) -> None:
    """
    Stage 4: Write chunks to database
    :param collection: collection object
    :param record_id: record id
    :param chunk_text_list: list of chunk texts
    :param num_tokens_list: list of token counts
    :param embeddings: list of embeddings
    :param db_content: db content to update
    :param is_retry: whether this is a retry operation
    :return: None
    """
    await db_record.update_record_chunks_and_status(
        collection=collection,
        record_id=record_id,
        chunk_text_list=chunk_text_list,
        chunk_embedding_list=embeddings,
        chunk_num_tokens_list=num_tokens_list,
        db_content=db_content,
        is_retry=is_retry,
    )


async def _validate_chunk_capacity(
    collection: Collection,
    num_chunks: int,
    existing_record_chunks: int = 0,
) -> None:
    """
    Validate if collection has enough capacity for new chunks
    :param collection: collection object
    :param num_chunks: number of new chunks
    :param existing_record_chunks: existing chunks for this record
    :return: None
    """
    available_capacity = existing_record_chunks + collection.rest_capacity()
    if num_chunks > available_capacity:
        raise_http_error(
            ErrorCode.RESOURCE_LIMIT_REACHED,
            "The collection has no enough capacity to store the new chunks created from the record content.",
        )


async def _process_import_stages(
    collection: Collection,
    record_id: str,
    type: RecordType,
    title: str,
    text_splitter: TextSplitter,
    content: Optional[str] = None,
    file_id: Optional[str] = None,
    url: Optional[str] = None,
    start_stage: ImportStage = ImportStage.CONTENT_LOADING,
    existing_record_chunks: int = 0,
    cached_results: Optional[Dict] = None,
    is_retry: bool = False,
) -> None:
    """
    Process import stages with tracking. Can start from any stage for retry.
    :param collection: collection object
    :param record_id: record id
    :param type: record type
    :param title: record title
    :param text_splitter: text splitter
    :param content: text content
    :param file_id: file id
    :param url: web url
    :param start_stage: stage to start from
    :param existing_record_chunks: existing chunks count for this record
    :param cached_results: cached results from previous failed run
    :param is_retry: whether this is a retry operation
    :return: None
    """
    cached_results = cached_results or {}
    db_content = cached_results.get("db_content")
    content_to_split = cached_results.get("content_to_split")
    chunk_text_list = cached_results.get("chunk_text_list")
    num_tokens_list = cached_results.get("num_tokens_list")
    embeddings = cached_results.get("embeddings")

    try:
        if start_stage.order <= ImportStage.CONTENT_LOADING.order:
            await db_record.update_import_status(
                record_id=record_id,
                import_status=ImportStatus.PROCESSING,
                processing_stage=ImportStage.CONTENT_LOADING,
            )
            db_content, content_to_split = await _load_content_stage(
                type=type, content=content, file_id=file_id, url=url
            )

        if start_stage.order <= ImportStage.CHUNKING.order:
            await db_record.update_import_status(
                record_id=record_id,
                import_status=ImportStatus.PROCESSING,
                processing_stage=ImportStage.CHUNKING,
            )
            chunk_text_list, num_tokens_list = await _chunking_stage(
                title=title, content_to_split=content_to_split, text_splitter=text_splitter
            )
            _validate_chunk_capacity(
                collection=collection,
                num_chunks=len(chunk_text_list),
                existing_record_chunks=existing_record_chunks,
            )

        if start_stage.order <= ImportStage.EMBEDDING.order:
            await db_record.update_import_status(
                record_id=record_id,
                import_status=ImportStatus.PROCESSING,
                processing_stage=ImportStage.EMBEDDING,
            )
            embeddings = await _embedding_stage(collection=collection, chunk_text_list=chunk_text_list)

        if start_stage.order <= ImportStage.WRITING_CHUNKS.order:
            await db_record.update_import_status(
                record_id=record_id,
                import_status=ImportStatus.PROCESSING,
                processing_stage=ImportStage.WRITING_CHUNKS,
            )
            await _writing_chunks_stage(
                collection=collection,
                record_id=record_id,
                chunk_text_list=chunk_text_list,
                num_tokens_list=num_tokens_list,
                embeddings=embeddings,
                db_content=db_content,
                is_retry=is_retry,
            )

    except Exception as e:
        import_params = {
            "type": type.value,
            "title": title,
            "content": content,
            "file_id": file_id,
            "url": url,
            "text_splitter": text_splitter.model_dump(),
        }
        error_message = str(e) if str(e) else "Unknown error occurred during import"
        await db_record.update_import_status(
            record_id=record_id,
            import_status=ImportStatus.FAILED,
            error_message=error_message,
            import_params=import_params,
        )
        raise


class RecordModelOperator(PostgresModelOperator):
    async def create(
        self,
        create_dict: Dict,
        **kwargs,
    ) -> ModelEntity:
        self._check_kwargs(object_id_required=None, **kwargs)
        collection_id = kwargs["collection_id"]

        type = RecordType(create_dict["type"])
        title = create_dict["title"]
        content = create_dict.get("content")
        file_id = create_dict.get("file_id")
        url = create_dict.get("url")
        text_splitter = TextSplitter(**create_dict["text_splitter"])
        metadata = create_dict["metadata"]

        collection = await collection_ops.get(collection_id=collection_id)

        new_record_id = Record.generate_random_id()

        import_params = {
            "type": type.value,
            "title": title,
            "content": content,
            "file_id": file_id,
            "url": url,
            "text_splitter": text_splitter.model_dump(),
        }

        pending_content = content or json.dumps({"file_id": file_id} if file_id else {"url": url} if url else {})
        await db_record.create_record_pending(
            record_id=new_record_id,
            collection=collection,
            title=title,
            type=type,
            content=pending_content,
            metadata=metadata,
            import_params=import_params,
        )

        await submit_record_import_task(
            collection_id=collection_id,
            record_id=new_record_id,
            type=type,
            title=title,
            text_splitter=text_splitter,
            content=content,
            file_id=file_id,
            url=url,
        )

        record = await self.get(collection_id=collection_id, record_id=new_record_id)
        return record

    async def update(
        self,
        update_dict: Dict,
        **kwargs,
    ) -> ModelEntity:
        self._check_kwargs(object_id_required=None, **kwargs)
        collection_id = kwargs["collection_id"]
        record_id = kwargs["record_id"]
        new_metadata = update_dict.get("metadata")

        collection = await collection_ops.get(collection_id=collection_id)
        record: Record = await self.get(collection_id=collection_id, record_id=record_id)

        if record.type == RecordType.FILE:
            raise_request_validation_error("Cannot update a file record. Please delete and create a new record.")

        new_type, new_title = None, None

        if (
            (update_dict.get("type") is not None)
            or (update_dict.get("content") is not None)
            or (update_dict.get("title") is not None)
        ):
            new_type = RecordType(update_dict.get("type", record.type))
            new_title = update_dict.get("title", record.title)
            new_content = update_dict.get("content", record.content) if new_type == RecordType.TEXT else None
            new_url = update_dict.get("url")
            text_splitter = TextSplitter(**update_dict["text_splitter"])

            import_params = {
                "type": new_type.value,
                "title": new_title,
                "content": new_content,
                "file_id": None,
                "url": new_url,
                "text_splitter": text_splitter.model_dump(),
            }

            await db_record.update_import_status(
                record_id=record_id,
                import_status=ImportStatus.PENDING,
                processing_stage=ImportStage.PENDING,
                error_message=None,
                import_params=import_params,
            )

            await submit_record_update_task(
                collection_id=collection_id,
                record_id=record_id,
                type=new_type,
                title=new_title,
                text_splitter=text_splitter,
                content=new_content,
                file_id=None,
                url=new_url,
                existing_record_chunks=record.num_chunks,
            )

            record = await self.get(collection_id=collection_id, record_id=record_id)

        if new_metadata is not None:
            await db_record.update_record(
                collection=collection,
                record=record,
                title=None,
                type=None,
                content=None,
                chunk_text_list=None,
                chunk_num_tokens_list=None,
                chunk_embedding_list=None,
                metadata=new_metadata,
            )
            record = await self.get(collection_id=collection_id, record_id=record_id)

        return record

    async def retry(
        self,
        **kwargs,
    ) -> ModelEntity:
        self._check_kwargs(object_id_required=None, **kwargs)
        collection_id = kwargs["collection_id"]
        record_id = kwargs["record_id"]

        collection = await collection_ops.get(collection_id=collection_id)
        record: Record = await self.get(collection_id=collection_id, record_id=record_id)

        if record.import_status != ImportStatus.FAILED:
            raise_request_validation_error("Only records with failed import status can be retried")

        if not record.import_params:
            raise_request_validation_error("No import parameters found for retry")

        import_params = record.import_params
        type = RecordType(import_params["type"])
        title = import_params["title"]
        content = import_params.get("content")
        file_id = import_params.get("file_id")
        url = import_params.get("url")
        text_splitter = TextSplitter(**import_params["text_splitter"])

        start_stage = record.processing_stage or ImportStage.CONTENT_LOADING

        await db_record.update_import_status(
            record_id=record_id,
            import_status=ImportStatus.PROCESSING,
            processing_stage=start_stage,
            error_message=None,
        )

        await submit_record_retry_task(
            collection_id=collection_id,
            record_id=record_id,
            type=type,
            title=title,
            text_splitter=text_splitter,
            start_stage=start_stage,
            content=content,
            file_id=file_id,
            url=url,
            existing_record_chunks=record.num_chunks,
        )

        record = await self.get(collection_id=collection_id, record_id=record_id)
        return record

    async def delete(self, **kwargs) -> None:
        self._check_kwargs(object_id_required=None, **kwargs)
        collection_id = kwargs["collection_id"]
        record_id = kwargs["record_id"]

        collection = await collection_ops.get(collection_id=collection_id)
        record = await self.get(collection_id=collection_id, record_id=record_id)
        await db_record.delete_record(record)
        await collection_ops.redis.pop(collection)


record_ops = RecordModelOperator(
    postgres_pool=postgres_pool,
    entity_class=Record,
    redis=None,
)
