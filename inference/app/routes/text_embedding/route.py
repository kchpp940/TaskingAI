from fastapi import APIRouter
from app.models import (
    ProviderCredentials,
    validate_credentials,
    validate_model_info,
    ModelType,
)
from app.cache import get_text_embedding_model
from app.error import raise_http_error, ErrorCode, TKHttpException, error_messages
from app.models.tokenizer import string_tokens
import asyncio
from .schema import *
import logging
from typing import List, Optional, Dict
import numpy as np
from config import CONFIG

logger = logging.getLogger(__name__)

router = APIRouter()


async def embed_batch(
    model: BaseTextEmbeddingModel,
    provider_model_id: str,
    batch_input: List[str],
    batch_start_offset: int,
    expected_embedding_size: int,
    credentials: ProviderCredentials,
    configs: TextEmbeddingModelConfiguration,
    input_type: Optional[TextEmbeddingInputType] = None,
    proxy: Optional[str] = None,
    custom_headers: Optional[Dict[str, str]] = None,
):
    res = await model.embed_text(
        provider_model_id=provider_model_id,
        input=batch_input,
        credentials=credentials,
        configs=configs,
        input_type=input_type,
        proxy=proxy,
        custom_headers=custom_headers,
    )
    expected_count = len(batch_input)
    actual_count = len(res.data)
    if actual_count != expected_count:
        raise_http_error(
            ErrorCode.INTERNAL_SERVER_ERROR,
            "Provider returned {} embeddings for a batch of {} inputs (batch offset {}).".format(
                actual_count, expected_count, batch_start_offset
            ),
        )
    for idx, output in enumerate(res.data):
        if len(output.embedding) != expected_embedding_size:
            raise_http_error(
                ErrorCode.INTERNAL_SERVER_ERROR,
                "Embedding dimension mismatch at batch offset {} local index {}: expected {}, got {}.".format(
                    batch_start_offset, idx, expected_embedding_size, len(output.embedding)
                ),
            )
    embeddings_array = np.array([output.embedding for output in res.data])

    try:
        norms = np.linalg.norm(embeddings_array, axis=1, keepdims=True)
        not_unit_vectors = (norms > 0).flatten()
        embeddings_array[not_unit_vectors] = embeddings_array[not_unit_vectors] / norms.flatten()[
            not_unit_vectors
        ].reshape(-1, 1)
    except Exception as e:
        logging.exception("Failed to normalize embeddings: %s", e)
        raise

    for i, output in enumerate(res.data):
        output.embedding = embeddings_array[i].tolist()
        output.index = batch_start_offset + i

    return res


async def embed_text(
    provider_id: str,
    provider_model_id: str,
    input: List[str],
    credentials: ProviderCredentials,
    properties: TextEmbeddingModelProperties,
    configs: TextEmbeddingModelConfiguration,
    input_type: Optional[TextEmbeddingInputType] = None,
    proxy: Optional[str] = None,
    custom_headers: Optional[Dict[str, str]] = None,
) -> TextEmbeddingResult:
    model = get_text_embedding_model(provider_id=provider_id)

    if not model:
        raise_http_error(
            ErrorCode.REQUEST_VALIDATION_ERROR,
            f"Provider {provider_id} is not " f"supported through the text_embedding API.",
        )

    if not properties:
        raise_http_error(
            ErrorCode.REQUEST_VALIDATION_ERROR,
            "Model properties are required for text embedding.",
        )

    batch_size = properties.max_batch_size
    if not batch_size or batch_size <= 0:
        raise_http_error(
            ErrorCode.REQUEST_VALIDATION_ERROR,
            f"Invalid max_batch_size: {batch_size}. Must be a positive integer.",
        )

    expected_embedding_size = properties.embedding_size
    if not expected_embedding_size or expected_embedding_size <= 0:
        raise_http_error(
            ErrorCode.REQUEST_VALIDATION_ERROR,
            f"Invalid embedding_size: {expected_embedding_size}. Must be a positive integer.",
        )

    if not input:
        raise_http_error(
            ErrorCode.REQUEST_VALIDATION_ERROR,
            "Input list cannot be empty.",
        )

    batches = []
    batch_offsets = []
    for i in range(0, len(input), batch_size):
        batches.append(input[i : i + batch_size])
        batch_offsets.append(i)

    merged_results = []

    max_parallel_tasks = 20
    for chunk_start in range(0, len(batches), max_parallel_tasks):
        chunk_end = min(chunk_start + max_parallel_tasks, len(batches))
        tasks = []
        for batch_idx in range(chunk_start, chunk_end):
            task = embed_batch(
                model=model,
                provider_model_id=provider_model_id,
                batch_input=batches[batch_idx],
                batch_start_offset=batch_offsets[batch_idx],
                expected_embedding_size=expected_embedding_size,
                credentials=credentials,
                configs=configs,
                input_type=input_type,
                proxy=proxy,
                custom_headers=custom_headers,
            )
            tasks.append(task)

        batch_results = await asyncio.gather(*tasks)

        for batch_result in batch_results:
            merged_results.extend(batch_result.data)

    if len(merged_results) != len(input):
        raise_http_error(
            ErrorCode.INTERNAL_SERVER_ERROR,
            f"Embedding result count mismatch: expected {len(input)}, got {len(merged_results)}.",
        )

    merged_results.sort(key=lambda o: o.index)
    for idx, output in enumerate(merged_results):
        if output.index != idx:
            raise_http_error(
                ErrorCode.INTERNAL_SERVER_ERROR,
                f"Embedding index mismatch: expected index {idx}, got {output.index}.",
            )
        if len(output.embedding) != expected_embedding_size:
            raise_http_error(
                ErrorCode.INTERNAL_SERVER_ERROR,
                f"Embedding dimension mismatch at index {idx}: expected {expected_embedding_size}, got {len(output.embedding)}.",
            )

    usage = TextEmbeddingUsage(input_tokens=sum(string_tokens(i) for i in input))
    return TextEmbeddingResult(data=merged_results, usage=usage)


# Note: TextEmbeddingResult should be structured to accumulate and return results from multiple batches.


# add new add_api_key
@router.post(
    "/text_embedding",
    operation_id="text_embedding",
    summary="Text Embedding",
    tags=["Inference"],
    responses={422: {"description": "Unprocessable Entity"}},
    response_model=TextEmbeddingResponse,
)
async def api_text_embedding(
    data: TextEmbeddingRequest,
):
    # validate model info
    model_infos = [
        validate_model_info(
            model_schema_id=data.model_schema_id,
            provider_model_id=data.provider_model_id,
            properties_dict=data.properties,
            model_type=ModelType.TEXT_EMBEDDING,
        )
    ]
    # validate fallback model info
    if data.fallbacks:
        for fallback in data.fallbacks:
            model_infos.append(
                validate_model_info(
                    model_schema_id=fallback.model_schema_id,
                    provider_model_id=fallback.provider_model_id,
                    properties_dict=None,
                    model_type=ModelType.TEXT_EMBEDDING,
                )
            )

    # validate credentials
    provider_credentials = validate_credentials(
        model_infos=model_infos,
        credentials_dict=data.credentials,
        encrypted_credentials_dict=data.encrypted_credentials,
    )

    for model_info in model_infos:
        model_type = model_info[3]
        if model_type != ModelType.TEXT_EMBEDDING and model_type != ModelType.WILDCARD:
            raise_http_error(
                ErrorCode.REQUEST_VALIDATION_ERROR, "Model type should be text_embedding, but got " + model_type
            )

    input = data.input
    if isinstance(data.input, str):
        input = [data.input]

    if not isinstance(input, list):
        raise_http_error(
            ErrorCode.REQUEST_VALIDATION_ERROR,
            "Input must be a string or a list of strings.",
        )

    if len(input) == 0:
        raise_http_error(
            ErrorCode.REQUEST_VALIDATION_ERROR,
            "Input list cannot be empty.",
        )

    for idx, item in enumerate(input):
        if not isinstance(item, str):
            raise_http_error(
                ErrorCode.REQUEST_VALIDATION_ERROR,
                "Input item at index {} must be a string, got {}.".format(idx, type(item).__name__),
            )
        if item.strip() == "":
            raise_http_error(
                ErrorCode.REQUEST_VALIDATION_ERROR,
                "Input string at index {} cannot be empty or whitespace-only.".format(idx),
            )

    default_embedding_size = model_infos[0][2].embedding_size
    last_exception = None

    # check if proxy is blacklisted
    if data.proxy:
        for url in CONFIG.PROVIDER_URL_BLACK_LIST:
            if url in data.proxy:
                raise_http_error(ErrorCode.REQUEST_VALIDATION_ERROR, f"Invalid provider url: {url}")

    for i, (model_schema, provider_model_id, properties, _) in enumerate(model_infos):
        properties: TextEmbeddingModelProperties
        if default_embedding_size != properties.embedding_size:
            raise_http_error(
                ErrorCode.REQUEST_VALIDATION_ERROR,
                "The embedding size of the fallback model '{}': {} is different from the primary model '{}': {}.".format(
                    provider_model_id, properties.embedding_size, model_infos[0][1], default_embedding_size
                ),
            )
        try:
            response = await embed_text(
                provider_id=model_schema.provider_id,
                provider_model_id=provider_model_id,
                input=input,
                credentials=provider_credentials,
                properties=properties,
                configs=data.configs,
                input_type=data.input_type,
                proxy=data.proxy,
                custom_headers=data.custom_headers,
            )
            fallback_index = None
            if i:
                fallback_index = i - 1
            return TextEmbeddingResponse(data=response.data, usage=response.usage, fallback_index=fallback_index)
        except TKHttpException as e:
            logger.error(f"text_embedding: provider {model_schema.provider_id} error = {e}")
            last_exception = e
        except Exception as e:
            logger.error(f"Unhandled exception for provider {model_schema.provider_id}: {str(e)}")
            last_exception = TKHttpException(
                status_code=error_messages[ErrorCode.INTERNAL_SERVER_ERROR]["status_code"],
                detail={"error_code": ErrorCode.INTERNAL_SERVER_ERROR, "message": str(e)},
            )
    if last_exception:
        raise last_exception  # Raise the last caught exception if all models fail

    # TODO: raise_http_error(ErrorCode.PROVIDER_SERVICE_UNAVAILABLE, "All providers' service are unavailable")
