import logging
import os
from typing import List, Dict
from app.models import ModelSchema
from app.models.yaml_loader import load_yaml_files_from_dir, PROVIDERS_ROOT
from config import CONFIG
from app.utils import checksum

logger = logging.getLogger(__name__)

_model_schemas, _model_schema_dict, _provider_model_schema_dict = ([], {}, {})
__model_schema_cache: List[Dict] = []
__model_schema_checksum: str = ""

__all__ = [
    "load_model_schema_data",
    "list_model_schemas",
    "get_model_schema",
    "get_model_schema_by_provider",
    "get_model_schema_cache",
    "get_model_schema_checksum",
]


def _read_model_schema_yamls(provider_id: str) -> List[Dict]:
    model_schema_dir = os.path.join(PROVIDERS_ROOT, provider_id, "resources/models")
    raw_entries = load_yaml_files_from_dir(model_schema_dir)
    results = []
    for file_path, data in raw_entries:
        data["provider_id"] = provider_id
        results.append(data)
    return results


def _parse_model_schemas(raw_entries: List[Dict]) -> List[ModelSchema]:
    model_schema_ids = {}
    model_schemas = []
    for data in raw_entries:
        model_schema_id = data.get("model_schema_id")
        provider_id = data.get("provider_id", "unknown")
        if model_schema_id in model_schema_ids:
            raise ValueError(f"Duplicate model_schema_id {model_schema_id} found in provider {provider_id}")
        model_schema_ids[model_schema_id] = True
        try:
            model_schema = ModelSchema.build(data)
            model_schemas.append(model_schema)
        except Exception as e:
            logger.error("Error building ModelSchema from %s: %s", data.get("model_schema_id", "unknown"), e)
    return model_schemas


def _filter_and_sort(model_schemas: List[ModelSchema], allowed_providers: List[str]) -> List[ModelSchema]:
    if allowed_providers:
        model_schemas = [
            model_schema
            for model_schema in model_schemas
            if model_schema.provider_id in allowed_providers
        ]
    model_schemas.sort(key=lambda x: x.model_schema_id)
    return model_schemas


def _build_indices(model_schemas: List[ModelSchema]):
    model_schema_dict = {model_schema.model_schema_id: model_schema for model_schema in model_schemas}
    provider_model_schema_dict = {
        f"{model_schema.provider_id}:{model_schema.provider_model_id}": model_schema for model_schema in model_schemas
    }
    return model_schema_dict, provider_model_schema_dict


def _write_cache(model_schemas: List[ModelSchema]):
    cache = [model_schema.to_dict(lang=None) for model_schema in model_schemas]
    return cache, checksum(cache)


def load_model_schema_data(provider_ids: List[str]) -> None:
    all_raw_entries = []
    for provider_id in provider_ids:
        all_raw_entries.extend(_read_model_schema_yamls(provider_id))

    model_schemas = _parse_model_schemas(all_raw_entries)

    model_schemas = _filter_and_sort(model_schemas, CONFIG.ALLOWED_PROVIDERS)

    model_schema_dict, provider_model_schema_dict = _build_indices(model_schemas)

    cache, schema_checksum = _write_cache(model_schemas)

    global _model_schemas, _model_schema_dict, _provider_model_schema_dict, __model_schema_cache, __model_schema_checksum
    _model_schemas, _model_schema_dict, _provider_model_schema_dict = (
        model_schemas,
        model_schema_dict,
        provider_model_schema_dict,
    )
    __model_schema_cache = cache
    __model_schema_checksum = schema_checksum
    logger.info("Loaded model schemas for providers: %s", provider_ids)


def list_model_schemas(provider_id: str, type: str) -> List[ModelSchema]:
    filtered_schemas = [
        schema
        for schema in _model_schemas
        if (provider_id is None or schema.provider_id == provider_id) and (type is None or schema.type == type)
    ]
    return filtered_schemas


def get_model_schema(model_schema_id: str) -> ModelSchema:
    return _model_schema_dict.get(model_schema_id)


def get_model_schema_by_provider(provider_id: str, provider_model_id: str) -> ModelSchema:
    return _provider_model_schema_dict.get(f"{provider_id}:{provider_model_id}")


def get_model_schema_cache() -> List[Dict]:
    return __model_schema_cache


def get_model_schema_checksum() -> str:
    return __model_schema_checksum
