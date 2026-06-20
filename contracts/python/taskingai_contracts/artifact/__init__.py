from taskingai_contracts.artifact.validator import (
    validate_artifact,
    validate_artifact_list,
    validate_artifact_model,
    load_schema,
    get_schema_version,
    get_constants,
    get_default_mime_types,
    get_mime_type_map,
)

from enum import Enum


class ArtifactType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    FILE = "file"
    JSON = "json"
    TABLE = "table"


ARTIFACT_TYPES = [t.value for t in ArtifactType]


def _load_constants():
    schema = load_schema()
    constants = schema["properties"]["constants"]["properties"]
    return {
        "MAX_ARTIFACT_CONTENT_LENGTH": constants["MAX_ARTIFACT_CONTENT_LENGTH"]["const"],
        "MAX_ARTIFACT_TITLE_LENGTH": constants["MAX_ARTIFACT_TITLE_LENGTH"]["const"],
        "MAX_ARTIFACTS_PER_TOOL": constants["MAX_ARTIFACTS_PER_TOOL"]["const"],
    }


_constants_cache = None


def _get_constant(name: str) -> int:
    global _constants_cache
    if _constants_cache is None:
        _constants_cache = _load_constants()
    return _constants_cache[name]


@property
def _max_content_length():
    return _get_constant("MAX_ARTIFACT_CONTENT_LENGTH")


@property
def _max_title_length():
    return _get_constant("MAX_ARTIFACT_TITLE_LENGTH")


@property
def _max_artifacts_per_tool():
    return _get_constant("MAX_ARTIFACTS_PER_TOOL")


LATEST_ARTIFACT_SCHEMA_VERSION = "v1.0"

MAX_ARTIFACT_CONTENT_LENGTH = 4096
MAX_ARTIFACT_TITLE_LENGTH = 128
MAX_ARTIFACTS_PER_TOOL = 10

__all__ = [
    "validate_artifact",
    "validate_artifact_list",
    "validate_artifact_model",
    "load_schema",
    "get_schema_version",
    "get_constants",
    "get_default_mime_types",
    "get_mime_type_map",
    "ArtifactType",
    "ARTIFACT_TYPES",
    "LATEST_ARTIFACT_SCHEMA_VERSION",
    "MAX_ARTIFACT_CONTENT_LENGTH",
    "MAX_ARTIFACT_TITLE_LENGTH",
    "MAX_ARTIFACTS_PER_TOOL",
]
