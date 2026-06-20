"""
Shared Artifact Schema Validator
================================

This module provides runtime validation of artifacts against the shared JSON Schema.
Both plugin and backend layers should use this to validate artifacts at runtime.

The schema is loaded from contracts/artifact/v1.0.json (the single source of truth).

Usage:
    from app.utils.artifact_schema_validator import validate_artifact, validate_artifact_list

    # Validate a single artifact dict
    is_valid, errors = validate_artifact(artifact_dict)

    # Validate a list of artifacts
    is_valid, errors = validate_artifact_list(artifact_list)
"""

import json
import os
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional

try:
    import jsonschema
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False


# Find the project root and schema path
def _find_schema_path() -> Optional[Path]:
    """Find the artifact schema JSON file relative to the project root."""
    current = Path(__file__).resolve()

    # Search up the directory tree for the contracts folder
    for parent in current.parents:
        schema_path = parent / "contracts" / "artifact" / "v1.0.json"
        if schema_path.exists():
            return schema_path

    # Also check relative to the current working directory
    cwd_schema = Path.cwd() / "contracts" / "artifact" / "v1.0.json"
    if cwd_schema.exists():
        return cwd_schema

    return None


SCHEMA_PATH = _find_schema_path()
_SCHEMA_CACHE: Optional[Dict] = None
_SCHEMA_ARTIFACT: Optional[Dict] = None
_SCHEMA_ARTIFACT_LIST: Optional[Dict] = None


def load_schema() -> Dict:
    """Load and cache the shared artifact JSON Schema."""
    global _SCHEMA_CACHE, _SCHEMA_ARTIFACT, _SCHEMA_ARTIFACT_LIST

    if _SCHEMA_CACHE is not None:
        return _SCHEMA_CACHE

    if SCHEMA_PATH is None:
        raise FileNotFoundError(
            "Artifact schema not found. Expected at contracts/artifact/v1.0.json. "
            "Make sure you're running from the project root."
        )

    with open(SCHEMA_PATH, "r") as f:
        _SCHEMA_CACHE = json.load(f)

    # Extract sub-schemas for convenience
    _SCHEMA_ARTIFACT = _SCHEMA_CACHE["definitions"]["Artifact"]
    _SCHEMA_ARTIFACT_LIST = _SCHEMA_CACHE["definitions"]["ArtifactList"]

    return _SCHEMA_CACHE


def get_schema_version() -> str:
    """Get the version of the loaded schema."""
    schema = load_schema()
    return schema.get("version", "unknown")


def validate_artifact(artifact: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validate a single artifact dict against the shared JSON Schema.

    Args:
        artifact: The artifact dictionary to validate.

    Returns:
        Tuple of (is_valid, list_of_errors). If jsonschema is not installed,
        returns (True, []) to avoid breaking functionality.
    """
    if not HAS_JSONSCHEMA:
        return True, []

    try:
        schema = load_schema()
        artifact_schema = schema["definitions"]["Artifact"]
        jsonschema.validate(instance=artifact, schema=artifact_schema)
        return True, []
    except jsonschema.ValidationError as e:
        return False, [e.message]
    except Exception as e:
        return False, [str(e)]


def validate_artifact_list(artifacts: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
    """
    Validate a list of artifact dicts against the shared JSON Schema.

    Args:
        artifacts: The list of artifact dictionaries to validate.

    Returns:
        Tuple of (is_valid, list_of_errors). If jsonschema is not installed,
        returns (True, []) to avoid breaking functionality.
    """
    if not HAS_JSONSCHEMA:
        return True, []

    all_errors = []
    for i, artifact in enumerate(artifacts):
        is_valid, errors = validate_artifact(artifact)
        if not is_valid:
            for error in errors:
                all_errors.append(f"Artifact[{i}]: {error}")

    # Check max items constraint
    schema = load_schema()
    max_items = schema["definitions"]["ArtifactList"].get("maxItems", 10)
    if len(artifacts) > max_items:
        all_errors.append(
            f"Too many artifacts: {len(artifacts)} > {max_items}. "
            f"Only first {max_items} will be kept."
        )

    return len(all_errors) == 0, all_errors


def validate_artifact_model(artifact) -> Tuple[bool, List[str]]:
    """
    Validate a Pydantic Artifact model instance against the shared JSON Schema.

    Args:
        artifact: Pydantic Artifact model instance (from plugin or backend).

    Returns:
        Tuple of (is_valid, list_of_errors).
    """
    artifact_dict = artifact.model_dump()
    return validate_artifact(artifact_dict)


# Constants from schema (for convenience)
def get_constants() -> Dict[str, int]:
    """Get the constants defined in the shared schema."""
    schema = load_schema()
    constants = schema["properties"]["constants"]["properties"]
    return {
        "MAX_ARTIFACT_CONTENT_LENGTH": constants["MAX_ARTIFACT_CONTENT_LENGTH"]["const"],
        "MAX_ARTIFACT_TITLE_LENGTH": constants["MAX_ARTIFACT_TITLE_LENGTH"]["const"],
        "MAX_ARTIFACTS_PER_TOOL": constants["MAX_ARTIFACTS_PER_TOOL"]["const"],
    }


def get_default_mime_types() -> Dict[str, str]:
    """Get the default MIME types defined in the shared schema."""
    schema = load_schema()
    return {
        k: v["const"] for k, v in schema["properties"]["defaultMimeTypes"]["properties"].items()
    }


def get_mime_type_map() -> Dict[str, str]:
    """Get the MIME type map defined in the shared schema."""
    schema = load_schema()
    return schema["properties"]["mimeTypeMap"]["properties"]
