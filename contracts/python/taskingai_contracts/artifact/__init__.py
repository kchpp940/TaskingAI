"""
Artifact Contract Package
=========================

This is the single source of truth for the Artifact Protocol.
All layers (plugin, backend, frontend) MUST reference this package
for schema definitions, validation rules, and constants.

The JSON Schema is EMBEDDED in this package (v1.0.json), so the package
is self-contained and does not depend on the contracts/ directory at runtime.
"""

import json
import os
from enum import Enum
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional, Union

import jsonschema
from pydantic import BaseModel, Field, field_validator


# ──────────────────────────────────────────────────────────────────────
# Schema loading (embedded, not from contracts/ directory)
# ──────────────────────────────────────────────────────────────────────

_SCHEMA_DIR = Path(__file__).parent / "schemas"
_SCHEMA_PATH = _SCHEMA_DIR / "v1.0.json"
_SCHEMA_CACHE: Optional[Dict] = None


def load_schema() -> Dict:
    """Load the embedded artifact JSON Schema."""
    global _SCHEMA_CACHE
    if _SCHEMA_CACHE is not None:
        return _SCHEMA_CACHE
    with open(_SCHEMA_PATH, "r") as f:
        _SCHEMA_CACHE = json.load(f)
    return _SCHEMA_CACHE


def get_schema_version() -> str:
    """Get the schema version string."""
    schema = load_schema()
    return schema.get("version", "unknown")


__schema_version__ = get_schema_version()


# ──────────────────────────────────────────────────────────────────────
# Constants from schema
# ──────────────────────────────────────────────────────────────────────

_SCHEMA_CONSTANTS = load_schema()["properties"]["constants"]["properties"]
MAX_ARTIFACT_CONTENT_LENGTH = _SCHEMA_CONSTANTS["MAX_ARTIFACT_CONTENT_LENGTH"]["const"]
MAX_ARTIFACT_TITLE_LENGTH = _SCHEMA_CONSTANTS["MAX_ARTIFACT_TITLE_LENGTH"]["const"]
MAX_ARTIFACTS_PER_TOOL = _SCHEMA_CONSTANTS["MAX_ARTIFACTS_PER_TOOL"]["const"]


def get_constants() -> Dict[str, int]:
    """Return artifact protocol constants."""
    return {
        "MAX_ARTIFACT_CONTENT_LENGTH": MAX_ARTIFACT_CONTENT_LENGTH,
        "MAX_ARTIFACT_TITLE_LENGTH": MAX_ARTIFACT_TITLE_LENGTH,
        "MAX_ARTIFACTS_PER_TOOL": MAX_ARTIFACTS_PER_TOOL,
    }


def get_default_mime_types() -> Dict[str, str]:
    """Return default MIME types for each artifact type."""
    schema = load_schema()
    return {
        k: v["const"] for k, v in schema["properties"]["defaultMimeTypes"]["properties"].items()
    }


def get_mime_type_map() -> Dict[str, str]:
    """Return file extension to MIME type mapping."""
    schema = load_schema()
    return schema["properties"]["mimeTypeMap"]["properties"]


# ──────────────────────────────────────────────────────────────────────
# ArtifactType enum (from schema enum)
# ──────────────────────────────────────────────────────────────────────

_ARTIFACT_TYPES_FROM_SCHEMA = load_schema()["definitions"]["ArtifactType"]["enum"]
ARTIFACT_TYPES = tuple(_ARTIFACT_TYPES_FROM_SCHEMA)


class ArtifactType(str, Enum):
    """
    Artifact type enumeration.
    Source: contracts/artifact/v1.0.json#/definitions/ArtifactType
    """
    TEXT = "text"
    IMAGE = "image"
    FILE = "file"
    JSON = "json"
    TABLE = "table"

    @classmethod
    def has_value(cls, value: str) -> bool:
        return value in cls._value2member_map_

    @classmethod
    def all_values(cls) -> Tuple[str, ...]:
        return ARTIFACT_TYPES


# ──────────────────────────────────────────────────────────────────────
# Artifact Pydantic model (for plugin/backend to import directly)
# ──────────────────────────────────────────────────────────────────────

class Artifact(BaseModel):
    """
    Standard Artifact DTO model.
    Source: contracts/artifact/v1.0.json#/definitions/Artifact

    Both plugin and backend can use this model directly instead of
    defining their own. If customizations are needed, subclass it.
    """

    type: ArtifactType = Field(
        ...,
        description="The type of the artifact.",
    )
    mime_type: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="The MIME type of the artifact. Must be in 'type/subtype' format, lowercase.",
    )
    title: Optional[str] = Field(
        None,
        description="The display title of the artifact. Will be truncated if exceeds max length.",
    )
    content: Optional[str] = Field(
        None,
        description="The text content of the artifact (for text, json, table, etc.). Will be truncated if exceeds max content length.",
    )
    preview_url: Optional[str] = Field(
        None,
        description="The preview image URL of the artifact.",
    )
    download_url: Optional[str] = Field(
        None,
        description="The download URL of the artifact.",
    )
    size: Optional[int] = Field(
        None,
        ge=0,
        description="The size of the artifact in bytes.",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata for the artifact.",
    )

    @field_validator("mime_type")
    @classmethod
    def validate_mime_type(cls, v: str) -> str:
        if "/" not in v:
            raise ValueError("Invalid MIME type format")
        return v.lower()

    @field_validator("title")
    @classmethod
    def trim_title(cls, v: Optional[str]) -> Optional[str]:
        if v and len(v) > MAX_ARTIFACT_TITLE_LENGTH:
            return v[: MAX_ARTIFACT_TITLE_LENGTH - 3] + "..."
        return v

    class Config:
        json_schema_extra = {
            "$schema_ref": "contracts/artifact/v1.0.json#/definitions/Artifact"
        }


# ──────────────────────────────────────────────────────────────────────
# JSON Schema validators
# ──────────────────────────────────────────────────────────────────────

def validate_artifact(artifact: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validate a single artifact dict against the embedded JSON Schema.

    Returns:
        (is_valid, list_of_error_messages)
    """
    try:
        schema = load_schema()
        # Use the full schema as resolution scope so $ref can find definitions
        resolver = jsonschema.RefResolver.from_schema(schema)
        artifact_schema = schema["definitions"]["Artifact"]
        validator = jsonschema.Draft7Validator(artifact_schema, resolver=resolver)
        errors = list(validator.iter_errors(artifact))
        if errors:
            return False, [e.message for e in errors]
        return True, []
    except Exception as e:
        return False, [str(e)]


def validate_artifact_list(artifacts: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
    """
    Validate a list of artifact dicts against the embedded JSON Schema.
    Also checks the max items constraint.

    Returns:
        (is_valid, list_of_error_messages)
    """
    all_errors = []
    for i, artifact in enumerate(artifacts):
        is_valid, errors = validate_artifact(artifact)
        if not is_valid:
            for error in errors:
                all_errors.append(f"Artifact[{i}]: {error}")

    if len(artifacts) > MAX_ARTIFACTS_PER_TOOL:
        all_errors.append(
            f"Too many artifacts: {len(artifacts)} > {MAX_ARTIFACTS_PER_TOOL}. "
            f"Only first {MAX_ARTIFACTS_PER_TOOL} will be kept."
        )

    return len(all_errors) == 0, all_errors


def validate_artifact_model(artifact: Union[Artifact, BaseModel]) -> Tuple[bool, List[str]]:
    """
    Validate a Pydantic Artifact model instance against the JSON Schema.
    """
    artifact_dict = artifact.model_dump()
    return validate_artifact(artifact_dict)
