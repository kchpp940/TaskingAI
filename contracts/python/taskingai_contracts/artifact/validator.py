import json
import importlib.resources
from typing import List, Dict, Any, Tuple, Optional

try:
    import jsonschema
    from jsonschema import Draft7Validator, RefResolver
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False


SCHEMA_FILENAME = "v1.0.json"
_SCHEMA_CACHE: Optional[Dict] = None
_SCHEMA_ARTIFACT: Optional[Dict] = None
_SCHEMA_ARTIFACT_LIST: Optional[Dict] = None
_ARTIFACT_VALIDATOR: Optional[Draft7Validator] = None
_ARTIFACT_LIST_VALIDATOR: Optional[Draft7Validator] = None


def _load_schema_from_package() -> Dict:
    ref = importlib.resources.files("taskingai_contracts.artifact.schemas").joinpath(SCHEMA_FILENAME)
    with importlib.resources.as_file(ref) as path:
        with open(path, "r") as f:
            return json.load(f)


def load_schema() -> Dict:
    global _SCHEMA_CACHE, _SCHEMA_ARTIFACT, _SCHEMA_ARTIFACT_LIST

    if _SCHEMA_CACHE is not None:
        return _SCHEMA_CACHE

    _SCHEMA_CACHE = _load_schema_from_package()

    _SCHEMA_ARTIFACT = _SCHEMA_CACHE["definitions"]["Artifact"]
    _SCHEMA_ARTIFACT_LIST = _SCHEMA_CACHE["definitions"]["ArtifactList"]

    return _SCHEMA_CACHE


def _get_artifact_validator() -> Draft7Validator:
    global _ARTIFACT_VALIDATOR
    if _ARTIFACT_VALIDATOR is not None:
        return _ARTIFACT_VALIDATOR

    full_schema = load_schema()
    artifact_schema = full_schema["definitions"]["Artifact"]
    resolver = RefResolver.from_schema(full_schema)
    _ARTIFACT_VALIDATOR = Draft7Validator(artifact_schema, resolver=resolver)
    return _ARTIFACT_VALIDATOR


def _get_artifact_list_validator() -> Draft7Validator:
    global _ARTIFACT_LIST_VALIDATOR
    if _ARTIFACT_LIST_VALIDATOR is not None:
        return _ARTIFACT_LIST_VALIDATOR

    full_schema = load_schema()
    list_schema = full_schema["definitions"]["ArtifactList"]
    resolver = RefResolver.from_schema(full_schema)
    _ARTIFACT_LIST_VALIDATOR = Draft7Validator(list_schema, resolver=resolver)
    return _ARTIFACT_LIST_VALIDATOR


def get_schema_version() -> str:
    schema = load_schema()
    return schema.get("version", "unknown")


def validate_artifact(artifact: Dict[str, Any]) -> Tuple[bool, List[str]]:
    if not HAS_JSONSCHEMA:
        return True, []

    try:
        validator = _get_artifact_validator()
        errors = sorted(validator.iter_errors(artifact), key=lambda e: e.path)
        if not errors:
            return True, []
        return False, [e.message for e in errors]
    except Exception as e:
        return False, [str(e)]


def validate_artifact_list(artifacts: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
    if not HAS_JSONSCHEMA:
        return True, []

    all_errors = []

    try:
        list_validator = _get_artifact_list_validator()
        list_errors = sorted(list_validator.iter_errors(artifacts), key=lambda e: e.path)
        for e in list_errors:
            all_errors.append(e.message)
    except Exception as e:
        all_errors.append(str(e))

    for i, artifact in enumerate(artifacts):
        is_valid, errors = validate_artifact(artifact)
        if not is_valid:
            for error in errors:
                all_errors.append(f"Artifact[{i}]: {error}")

    return len(all_errors) == 0, all_errors


def validate_artifact_model(artifact) -> Tuple[bool, List[str]]:
    artifact_dict = artifact.model_dump()
    return validate_artifact(artifact_dict)


def get_constants() -> Dict[str, int]:
    schema = load_schema()
    constants = schema["properties"]["constants"]["properties"]
    return {
        "MAX_ARTIFACT_CONTENT_LENGTH": constants["MAX_ARTIFACT_CONTENT_LENGTH"]["const"],
        "MAX_ARTIFACT_TITLE_LENGTH": constants["MAX_ARTIFACT_TITLE_LENGTH"]["const"],
        "MAX_ARTIFACTS_PER_TOOL": constants["MAX_ARTIFACTS_PER_TOOL"]["const"],
    }


def get_default_mime_types() -> Dict[str, str]:
    schema = load_schema()
    return {
        k: v["const"] for k, v in schema["properties"]["defaultMimeTypes"]["properties"].items()
    }


def get_mime_type_map() -> Dict[str, str]:
    schema = load_schema()
    return schema["properties"]["mimeTypeMap"]["properties"]
