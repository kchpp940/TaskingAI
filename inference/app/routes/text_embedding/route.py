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
import time
from .schema import *
from .embedding_cache import generate_cache_key, get_cached, set_cached
import logging
from typing import Dict, List, Optional
import numpy as np
from config import CONFIG

logger = logging.getLogger(__name__)

router = APIRouter()


async def embed_batch(
    model: BaseTextEmbeddingModel,
    provider_model_id: str,
    batch_input: List[str],
    credentials: ProviderCredentials,
    configs: TextEmbeddingModelConfiguration,
    input_type: Optional[TextEmbeddingInputType] = None,
    proxy: Optional[str] = None,
    custom_headers: Optional[Dict[str, str]] = None,
):
    # Embed a single batch of texts
    res = await model.embed_text(
        provider_model_id=provider_model_id,
        input=batch_input,
        credentials=credentials,
        configs=configs,
        input_type=input_type,
        proxy=proxy,
        custom_headers=custom_headers,
    )
    # ensure that the embeddings are unit vectors
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

    return res


async def embed_text(
    provider_id: str,
    provider_model_id: str,
    model_schema_id: str,
    input: List[str],
    credentials: ProviderCredentials,
    properties: TextEmbeddingModelProperties,
    configs: TextEmbeddingModelConfiguration,
    input_type: Optional[TextEmbeddingInputType] = None,
    proxy: Optional[str] = None,
    custom_headers: Optional[Dict[str, str]] = None,
    cache_ttl: int = 300,
) -> tuple:
    start_time = time.time()
    model = get_text_embedding_model(provider_id=provider_id)
    batch_size = properties.max_batch_size if properties else 512

    if not model:
        raise_http_error(
            ErrorCode.REQUEST_VALIDATION_ERROR,
            f"Provider {provider_id} is not " f"supported through the text_embedding API.",
        )

    input_type_str = input_type.value if input_type else None

    cache_hits = 0
    provider_calls = 0
    batch_count = 0

    unique_cache_keys = []
    cache_key_to_text: Dict[str, str] = {}
    unique_indices_map: Dict[str, List[int]] = {}
    cached_embeddings: Dict[int, List[float]] = {}

    for idx, text in enumerate(input):
        cache_key = generate_cache_key(
            model_schema_id=model_schema_id,
            provider_model_id=provider_model_id,
            text=text,
            input_type=input_type_str,
            properties=properties,
        )
        hit = await get_cached(cache_key, ttl=cache_ttl)
        if hit is not None:
            cached_embeddings[idx] = hit
            cache_hits += 1
        else:
            if cache_key not in unique_indices_map:
                unique_indices_map[cache_key] = []
                unique_cache_keys.append(cache_key)
                cache_key_to_text[cache_key] = text
            unique_indices_map[cache_key].append(idx)

    uncached_embeddings: Dict[int, List[float]] = {}

    if unique_cache_keys:
        unique_texts_for_provider = [cache_key_to_text[k] for k in unique_cache_keys]
        batches = [unique_texts_for_provider[i : i + batch_size] for i in range(0, len(unique_texts_for_provider), batch_size)]
        batch_count = len(batches)
        batch_results_data = []

        max_parallel_tasks = 20
        for i in range(0, len(batches), max_parallel_tasks):
            tasks = []
            for batch in batches[i : i + max_parallel_tasks]:
                task = embed_batch(
                    model=model,
                    provider_model_id=provider_model_id,
                    batch_input=batch,
                    credentials=credentials,
                    configs=configs,
                    input_type=input_type,
                    proxy=proxy,
                    custom_headers=custom_headers,
                )
                tasks.append(task)
                provider_calls += 1

            batch_results = await asyncio.gather(*tasks)
            for batch_result in batch_results:
                batch_results_data.extend(batch_result.data)

        for result_idx, cache_key in enumerate(unique_cache_keys):
            embedding = batch_results_data[result_idx].embedding
            await set_cached(cache_key, embedding)
            for orig_idx in unique_indices_map[cache_key]:
                uncached_embeddings[orig_idx] = embedding

    merged_results = []
    for idx in range(len(input)):
        if idx in cached_embeddings:
            merged_results.append(TextEmbeddingOutput(index=idx, embedding=cached_embeddings[idx]))
        else:
            merged_results.append(TextEmbeddingOutput(index=idx, embedding=uncached_embeddings[idx]))

    elapsed_ms = round((time.time() - start_time) * 1000, 2)
    usage = TextEmbeddingUsage(input_tokens=sum(string_tokens(i) for i in input))

    metadata = TextEmbeddingMetadata(
        cache_hits=cache_hits,
        total_inputs=len(input),
        unique_keys=len(unique_cache_keys),
        provider_calls=provider_calls,
        batch_count=batch_count,
        elapsed_ms=elapsed_ms,
    )
    logger.info(
        f"embedding_cache: model_schema_id={model_schema_id} "
        f"total={len(input)} unique_keys={len(unique_cache_keys)} "
        f"cache_hits={cache_hits} provider_calls={provider_calls} "
        f"batches={batch_count} elapsed_ms={elapsed_ms}"
    )

    return TextEmbeddingResult(data=merged_results, usage=usage), metadata


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
                    properties_dict=data.properties,
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
            response, metadata = await embed_text(
                provider_id=model_schema.provider_id,
                provider_model_id=provider_model_id,
                model_schema_id=model_schema.model_schema_id,
                input=input,
                credentials=provider_credentials,
                properties=properties,
                configs=data.configs,
                input_type=data.input_type,
                proxy=data.proxy,
                custom_headers=data.custom_headers,
                cache_ttl=CONFIG.EMBEDDING_CACHE_TTL,
            )
            fallback_index = None
            if i:
                fallback_index = i - 1
            return TextEmbeddingResponse(data=response.data, usage=response.usage, fallback_index=fallback_index, metadata=metadata)
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
