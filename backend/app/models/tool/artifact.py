from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, field_validator

__all__ = [
    "ArtifactType",
    "Artifact",
    "normalize_artifact",
    "summarize_artifact",
    "convert_legacy_tool_data_to_artifacts",
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
    LINK = "link"
    CODE = "code"
    AUDIO = "audio"
    VIDEO = "video"


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
        description="The text content of the artifact.",
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


def _default_mime_type_for_type(artifact_type: str) -> str:
    type_map = {
        "text": "text/plain",
        "image": "image/png",
        "file": "application/octet-stream",
        "link": "text/html",
        "code": "text/plain",
        "audio": "audio/mpeg",
        "video": "video/mp4",
    }
    return type_map.get(artifact_type, "application/octet-stream")


_MIME_TYPE_MAP = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "webp": "image/webp",
    "svg": "image/svg+xml",
    "pdf": "application/pdf",
    "txt": "text/plain",
    "md": "text/markdown",
    "html": "text/html",
    "json": "application/json",
    "csv": "text/csv",
    "mp3": "audio/mpeg",
    "wav": "audio/wav",
    "mp4": "video/mp4",
    "webm": "video/webm",
    "zip": "application/zip",
}


def _guess_mime_type_from_url(url: str) -> str:
    lower_url = url.lower()
    for ext, mime in _MIME_TYPE_MAP.items():
        if f".{ext}" in lower_url:
            return mime
    return "application/octet-stream"


def _guess_mime_type_from_content(content: str) -> str:
    try:
        import json

        json.loads(content)
        return "application/json"
    except Exception:
        pass
    if content.strip().startswith("<!DOCTYPE") or content.strip().startswith("<html"):
        return "text/html"
    if content.strip().startswith("```"):
        return "text/markdown"
    return "text/plain"


def convert_legacy_tool_data_to_artifacts(data: Dict[str, Any]) -> List[Artifact]:
    artifacts: List[Artifact] = []

    if "url" in data and isinstance(data["url"], str):
        url = data["url"]
        mime_type = _guess_mime_type_from_url(url)
        artifact_type = ArtifactType.FILE
        if mime_type.startswith("image/"):
            artifact_type = ArtifactType.IMAGE
        elif mime_type.startswith("audio/"):
            artifact_type = ArtifactType.AUDIO
        elif mime_type.startswith("video/"):
            artifact_type = ArtifactType.VIDEO
        elif mime_type.startswith("text/"):
            artifact_type = ArtifactType.TEXT

        artifacts.append(
            Artifact(
                type=artifact_type,
                mime_type=mime_type,
                title=data.get("title") or data.get("name") or "File",
                download_url=url,
                preview_url=url if artifact_type == ArtifactType.IMAGE else None,
                size=data.get("size"),
                metadata={k: v for k, v in data.items() if k not in {"url", "title", "name", "size"}},
            )
        )

    elif "image_url" in data and isinstance(data["image_url"], str):
        url = data["image_url"]
        artifacts.append(
            Artifact(
                type=ArtifactType.IMAGE,
                mime_type=_guess_mime_type_from_url(url),
                title=data.get("title") or "Image",
                download_url=url,
                preview_url=url,
                size=data.get("size"),
                metadata={k: v for k, v in data.items() if k not in {"image_url", "title", "size"}},
            )
        )

    elif "file_url" in data and isinstance(data["file_url"], str):
        url = data["file_url"]
        artifacts.append(
            Artifact(
                type=ArtifactType.FILE,
                mime_type=_guess_mime_type_from_url(url),
                title=data.get("title") or data.get("name") or "File",
                download_url=url,
                size=data.get("size"),
                metadata={k: v for k, v in data.items() if k not in {"file_url", "title", "name", "size"}},
            )
        )

    elif "content" in data and isinstance(data["content"], str):
        content = data["content"]
        mime_type = _guess_mime_type_from_content(content)
        artifact_type = ArtifactType.TEXT
        if mime_type == "application/json":
            artifact_type = ArtifactType.CODE
        elif data.get("type") == "code":
            artifact_type = ArtifactType.CODE

        artifacts.append(
            Artifact(
                type=artifact_type,
                mime_type=mime_type,
                title=data.get("title") or "Content",
                content=content,
                size=len(content.encode("utf-8")),
                metadata={k: v for k, v in data.items() if k not in {"content", "title", "type"}},
            )
        )

    elif "text" in data and isinstance(data["text"], str):
        text = data["text"]
        artifacts.append(
            Artifact(
                type=ArtifactType.TEXT,
                mime_type="text/plain",
                title=data.get("title") or "Text",
                content=text,
                size=len(text.encode("utf-8")),
                metadata={k: v for k, v in data.items() if k not in {"text", "title"}},
            )
        )

    return artifacts


def parse_and_normalize_artifacts(
    artifacts_data: Optional[List[Dict[str, Any]]],
    legacy_data: Optional[Dict[str, Any]] = None,
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

    if not result and legacy_data:
        result = convert_legacy_tool_data_to_artifacts(legacy_data)
        for artifact in result:
            summarize_artifact(artifact)

    if len(result) > MAX_ARTIFACTS_PER_TOOL:
        result = result[:MAX_ARTIFACTS_PER_TOOL]

    return result
