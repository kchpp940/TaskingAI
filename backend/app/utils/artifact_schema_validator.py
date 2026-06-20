"""
Shared Artifact Schema Validator (Backend Compatibility Layer)
===============================================================

This module is a backward-compatibility wrapper around the shared
taskingai_contracts package. All new code should import directly from
taskingai_contracts.artifact instead.

The single source of truth is: contracts/python/taskingai_contracts/

Usage:
    from app.utils.artifact_schema_validator import validate_artifact, validate_artifact_list

    # For new code, prefer:
    from taskingai_contracts import validate_artifact, validate_artifact_list
"""

from taskingai_contracts.artifact import (
    validate_artifact,
    validate_artifact_list,
    validate_artifact_model,
    load_schema,
    get_schema_version,
    get_constants,
    get_default_mime_types,
    get_mime_type_map,
    ArtifactType,
    ARTIFACT_TYPES,
    LATEST_ARTIFACT_SCHEMA_VERSION,
    MAX_ARTIFACT_CONTENT_LENGTH,
    MAX_ARTIFACT_TITLE_LENGTH,
    MAX_ARTIFACTS_PER_TOOL,
)

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
