import logging
import os
from typing import List, Dict, Tuple
from app.models import ModelSchema, apply_capability_normalization
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


def _parse_model_schemas(raw_entries: List[Dict]) -> Tuple[List[ModelSchema], List[Dict]]:
    model_schema_ids = {}
    model_schemas: List[ModelSchema] = []
    ordered_raw: List[Dict] = []
    for data in raw_entries:
        model_schema_id = data.get("model_schema_id")
        provider_id = data.get("provider_id", "unknown")
        if model_schema_id in model_schema_ids:
            raise ValueError(f"Duplicate model_schema_id {model_schema_id} found in provider {provider_id}")
        model_schema_ids[model_schema_id] = True
        try:
            model_schema = ModelSchema.build(data)
            model_schemas.append(model_schema)
            ordered_raw.append(data)
        except Exception as e:
            logger.error("Error building ModelSchema from %s: %s", data.get("model_schema_id", "unknown"), e)
    return model_schemas, ordered_raw


def _normalize_capabilities(model_schemas: List[ModelSchema], raw_entries: List[Dict]) -> None:
    for model_schema, raw in zip(model_schemas, raw_entries):
        properties_raw = raw.get("properties", {})
        apply_capability_normalization(model_schema, properties_raw)
        if model_schema.warnings:
            for warning in model_schema.warnings:
                logger.info(
                    "[%s] %s: %s",
                    warning.code,
                    model_schema.model_schema_id,
                    warning.message,
                )


def _filter_and_sort(model_schemas: List[ModelSchema], raw_entries: List[Dict], allowed_providers: List[str]):
    if allowed_providers:
        filtered_pairs = [
            (schema, raw)
            for schema, raw in zip(model_schemas, raw_entries)
            if schema.provider_id in allowed_providers
        ]
        model_schemas = [p[0] for p in filtered_pairs]
        raw_entries = [p[1] for p in filtered_pairs]
    sorted_pairs = sorted(zip(model_schemas, raw_entries), key=lambda pair: pair[0].model_schema_id)
    return [p[0] for p in sorted_pairs], [p[1] for p in sorted_pairs]


def _build_indices(model_schemas: List[ModelSchema]):
    model_schema_dict = {model_schema.model_schema_id: model_schema for model_schema in model_schemas}
    provider_model_schema_dict = {
        f"{model_schema.provider_id}:{model_schema.provider_model_id}": model_schema for model_schema in model_schemas
    }
    return model_schema_dict, provider_model_schema_dict


def _write_cache(model_schemas: List[ModelSchema]):
    cache = [model_schema.to_dict(lang=None, include_internal=True) for model_schema in model_schemas]
    return cache, checksum(cache)


def load_model_schema_data(provider_ids: List[str]) -> None:
    all_raw_entries = []
    for provider_id in provider_ids:
        all_raw_entries.extend(_read_model_schema_yamls(provider_id))

    model_schemas, ordered_raw = _parse_model_schemas(all_raw_entries)

    model_schemas, ordered_raw = _filter_and_sort(model_schemas, ordered_raw, CONFIG.ALLOWED_PROVIDERS)

    _normalize_capabilities(model_schemas, ordered_raw)

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

