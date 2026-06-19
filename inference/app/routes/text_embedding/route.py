from fastapi import APIRouter
from app.models import (
    ProviderCredentials,
    validate_credentials,
    validate_model_info,
    ModelType,
)
from app.cache import get_text_embedding_model, get_embedding_cache, set_embedding_cache
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


async def _get_cached_embeddings(
    texts: List[str],
    model_schema_id: str,
    provider_model_id: str,
) -> Dict[int, List[float]]:
    cached = {}
    for i, text in enumerate(texts):
        embedding = await get_embedding_cache(text, model_schema_id, provider_model_id)
        if embedding is not None:
            cached[i] = embedding
    return cached


async def _set_cached_embeddings(
    texts: List[str],
    embeddings: List[List[float]],
    model_schema_id: str,
    provider_model_id: str,
    embedding_size: int,
):
    for text, embedding in zip(texts, embeddings):
        await set_embedding_cache(
            text=text,
            embedding=embedding,
            model_schema_id=model_schema_id,
            provider_model_id=provider_model_id,
            embedding_size=embedding_size,
        )


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
    model_schema_id: Optional[str] = None,
) -> TextEmbeddingResult:
    model = get_text_embedding_model(provider_id=provider_id)
    batch_size = properties.max_batch_size if properties else 512
    embedding_size = properties.embedding_size if properties else 0

    if not model:
        raise_http_error(
            ErrorCode.REQUEST_VALIDATION_ERROR,
            f"Provider {provider_id} is not " f"supported through the text_embedding API.",
        )

    if model_schema_id and CONFIG.ENABLE_EMBEDDING_CACHE:
        cached_embeddings = await _get_cached_embeddings(input, model_schema_id, provider_model_id)
        if cached_embeddings:
            uncached_indices = [i for i in range(len(input)) if i not in cached_embeddings]
            if uncached_indices:
                uncached_texts = [input[i] for i in uncached_indices]
                uncached_result = await _embed_text_internal(
                    model=model,
                    provider_model_id=provider_model_id,
                    texts=uncached_texts,
                    credentials=credentials,
                    properties=properties,
                    configs=configs,
                    input_type=input_type,
                    proxy=proxy,
                    custom_headers=custom_headers,
                    batch_size=batch_size,
                )
                new_embeddings = [output.embedding for output in uncached_result.data]
                await _set_cached_embeddings(
                    texts=uncached_texts,
                    embeddings=new_embeddings,
                    model_schema_id=model_schema_id,
                    provider_model_id=provider_model_id,
                    embedding_size=embedding_size,
                )
                for idx, pos in enumerate(uncached_indices):
                    cached_embeddings[pos] = new_embeddings[idx]

            all_embeddings = [cached_embeddings[i] for i in range(len(input))]
            from app.models.base import TextEmbeddingOutput

            outputs = [
                TextEmbeddingOutput(index=i, embedding=embedding)
                for i, embedding in enumerate(all_embeddings)
            ]
            usage = TextEmbeddingUsage(input_tokens=sum(string_tokens(i) for i in input))
            return TextEmbeddingResult(data=outputs, usage=usage)

    return await _embed_text_internal(
        model=model,
        provider_model_id=provider_model_id,
        texts=input,
        credentials=credentials,
        properties=properties,
        configs=configs,
        input_type=input_type,
        proxy=proxy,
        custom_headers=custom_headers,
        batch_size=batch_size,
    )


async def _embed_text_internal(
    model,
    provider_model_id: str,
    texts: List[str],
    credentials: ProviderCredentials,
    properties: TextEmbeddingModelProperties,
    configs: TextEmbeddingModelConfiguration,
    input_type: Optional[TextEmbeddingInputType],
    proxy: Optional[str],
    custom_headers: Optional[Dict[str, str]],
    batch_size: int,
) -> TextEmbeddingResult:
    batches = [texts[i : i + batch_size] for i in range(0, len(texts), batch_size)]

    merged_results = []

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

        batch_results = await asyncio.gather(*tasks)

        for batch_result in batch_results:
            merged_results.extend(batch_result.data)

    usage = TextEmbeddingUsage(input_tokens=sum(string_tokens(t) for t in texts))
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
                model_schema_id=data.model_schema_id if i == 0 else model_infos[i][0].model_schema_id,
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
