"""
taskingai-contracts
===================

Shared contracts and schemas for TaskingAI services.

This package is the single source of truth for all cross-service agreements
including artifact protocol, type definitions, and validation rules.
"""

from .artifact import (
    # Version
    __schema_version__,
    # Schema loading
    load_schema,
    get_schema_version,
    get_constants,
    get_default_mime_types,
    get_mime_type_map,
    # Artifact types
    ARTIFACT_TYPES,
    ArtifactType,
    # Constants
    MAX_ARTIFACT_CONTENT_LENGTH,
    MAX_ARTIFACT_TITLE_LENGTH,
    MAX_ARTIFACTS_PER_TOOL,
    # Runtime validators
    validate_artifact,
    validate_artifact_list,
    validate_artifact_model,
    # Pydantic model (for backward compatibility with plugin/backend)
    Artifact,
)

__version__ = "1.0.0"
__all__ = [
    "__schema_version__",
    "__version__",
    "load_schema",
    "get_schema_version",
    "get_constants",
    "get_default_mime_types",
    "get_mime_type_map",
    "ARTIFACT_TYPES",
    "ArtifactType",
    "MAX_ARTIFACT_CONTENT_LENGTH",
    "MAX_ARTIFACT_TITLE_LENGTH",
    "MAX_ARTIFACTS_PER_TOOL",
    "validate_artifact",
    "validate_artifact_list",
    "validate_artifact_model",
    "Artifact",
]
