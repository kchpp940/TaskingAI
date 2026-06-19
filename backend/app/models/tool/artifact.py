from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, field_validator

__all__ = [
    "ArtifactType",
    "Artifact",
    "normalize_artifact",
    "summarize_artifact",
    "parse_and_normalize_artifacts",
    "MAX_ARTIFACT_CONTENT_LENGTH",
    "MAX_ARTIFACT_TITLE_LENGTH",
    "MAX_ARTIFACTS_PER_TOOL",
]

MAX_ARTIFACT_CONTENT_LENGTH = 4096
MAX_ARTIFACT_TITLE_LENGTH = 128
MAX_ARTIFACTS_PER_TOOL = 10


class ArtifactType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    FILE = "file"
    JSON = "json"
    TABLE = "table"


class Artifact(BaseModel):
    type: ArtifactType = Field(
        ...,
        description="The type of the artifact.",
    )
    mime_type: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="The MIME type of the artifact.",
    )
    title: Optional[str] = Field(
        None,
        max_length=MAX_ARTIFACT_TITLE_LENGTH,
        description="The display title of the artifact.",
    )
    content: Optional[str] = Field(
        None,
        description="The text content of the artifact (for text, json, table, etc.).",
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


def _default_mime_type_for_type(artifact_type: str) -> str:
    type_map = {
        "text": "text/plain",
        "image": "image/png",
        "file": "application/octet-stream",
        "json": "application/json",
        "table": "application/json",
    }
    return type_map.get(artifact_type, "application/octet-stream")


def normalize_artifact(artifact: Dict[str, Any]) -> Artifact:
    if "type" not in artifact:
        raise ValueError("Artifact type is required")
    if "mime_type" not in artifact:
        artifact["mime_type"] = _default_mime_type_for_type(artifact["type"])
    if "metadata" not in artifact:
        artifact["metadata"] = {}

    return Artifact(**artifact)


def summarize_artifact(artifact: Artifact, max_content_length: int = MAX_ARTIFACT_CONTENT_LENGTH) -> Artifact:
    if artifact.content and len(artifact.content) > max_content_length:
        truncated = artifact.content[:max_content_length]
        artifact.content = truncated + "..."
        if artifact.size is None:
            artifact.size = len(artifact.content.encode("utf-8"))

    if artifact.title and len(artifact.title) > MAX_ARTIFACT_TITLE_LENGTH:
        artifact.title = artifact.title[: MAX_ARTIFACT_TITLE_LENGTH - 3] + "..."

    return artifact


def parse_and_normalize_artifacts(
    artifacts_data: Optional[List[Dict[str, Any]]],
) -> List[Artifact]:
    result: List[Artifact] = []

    if artifacts_data:
        for artifact_dict in artifacts_data:
            try:
                artifact = normalize_artifact(artifact_dict)
                artifact = summarize_artifact(artifact)
                result.append(artifact)
            except Exception:
                continue

    if len(result) > MAX_ARTIFACTS_PER_TOOL:
        result = result[:MAX_ARTIFACTS_PER_TOOL]

    return result
