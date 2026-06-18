import json
import os
import logging
from typing import List, Any, Optional
from pydantic import BaseModel, Field

from app.models.plugin_handler import Artifact, ArtifactType
from config import CONFIG
from app.service.image_storage import generate_random_id, get_base62_date

logger = logging.getLogger(__name__)


# ============================================================
# Artifact Size & Count Limits
# ============================================================

# Maximum number of artifacts per plugin response
MAX_ARTIFACTS_COUNT = 10

# Text artifact: max inline chars (truncate if exceeded)
MAX_TEXT_INLINE_CHARS = 2000

# JSON artifact: max inline chars in the serialized JSON
MAX_JSON_INLINE_CHARS = 3000

# Table artifact: max rows to keep inline
MAX_TABLE_INLINE_ROWS = 20
# Table artifact: max columns to keep inline
MAX_TABLE_INLINE_COLUMNS = 15

# Metadata: max inline chars
MAX_METADATA_INLINE_CHARS = 500

# If an artifact's content exceeds these thresholds, we:
#   1. Keep a truncated preview in the artifact
#   2. Store the full content to a short-lived file / object storage
#   3. Set download_url to retrieve the full content
LARGE_CONTENT_THRESHOLD_CHARS = 1500
LARGE_TABLE_ROWS_THRESHOLD = 50


# ============================================================
# Short-lived content file storage
# ============================================================

def _generate_artifact_file_path() -> str:
    """Generate a unique file path for storing large artifact content."""
    category = "artifacts/p/" if CONFIG.INCLUDE_FILE_CATEGORY_IN_STORAGE_PATH else ""
    file_id = f"pgAF{generate_random_id(8)}"
    return f"{category}{get_base62_date()}/{file_id}.json"


def _save_text_content_to_local(content: str, relative_path: str) -> str:
    """Save large text/JSON content to local volume."""
    full_path = f"{CONFIG.PATH_TO_VOLUME}/{relative_path}"
    directory = os.path.dirname(full_path)
    if not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(content)
    return f"{CONFIG.HOST_URL}/{relative_path}"


async def _save_artifact_content_to_storage(
    content: str,
    mime_type: str,
    project_id: Optional[str] = None,
) -> Optional[str]:
    """
    Save large artifact content to storage (local or S3).
    Returns the public URL to retrieve it, or None if storage is unavailable.
    """
    try:
        relative_path = _generate_artifact_file_path()
        if CONFIG.OBJECT_STORAGE_TYPE == 'local':
            return _save_text_content_to_local(content, relative_path)
        elif CONFIG.OBJECT_STORAGE_TYPE == 's3':
            try:
                import aioboto3
                session = aioboto3.Session(
                    aws_access_key_id=CONFIG.S3_ACCESS_KEY_ID,
                    aws_secret_access_key=CONFIG.S3_ACCESS_KEY_SECRET,
                )
                public_domain = (
                    CONFIG.S3_BUCKET_PUBLIC_DOMAIN
                    if CONFIG.S3_BUCKET_PUBLIC_DOMAIN
                    else f"{CONFIG.S3_ENDPOINT}/{CONFIG.S3_IMAGE_BUCKET_NAME}"
                )
                async with session.client("s3", endpoint_url=CONFIG.S3_ENDPOINT) as s3:
                    await s3.put_object(
                        Bucket=CONFIG.S3_IMAGE_BUCKET_NAME,
                        Key=relative_path,
                        Body=content.encode("utf-8"),
                        ContentType=mime_type,
                        Metadata={
                            "project_id": project_id or "unknown",
                            "artifact_type": "large_content",
                        },
                    )
                return f"{public_domain}/{relative_path}"
            except Exception as e:
                logger.warning(f"Failed to save artifact to S3, falling back to local: {e}")
                return _save_text_content_to_local(content, relative_path)
        else:
            logger.warning("No artifact storage service available, keeping truncated content inline")
            return None
    except Exception as e:
        logger.warning(f"Failed to save artifact content to storage: {e}")
        return None


# ============================================================
# Truncation helpers
# ============================================================

def _truncate_text(text: str, max_chars: int) -> str:
    if text is None:
        return ""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "... (truncated)"


def _estimate_size(obj: Any) -> int:
    """Roughly estimate the size of a JSON-serializable object in characters."""
    try:
        return len(json.dumps(obj, ensure_ascii=False))
    except Exception:
        return len(str(obj))


# ============================================================
# Artifact sanitization and truncation
# ============================================================

async def sanitize_artifacts(
    artifacts: List[Artifact],
    project_id: Optional[str] = None,
) -> List[Artifact]:
    """
    Enforce size & count limits on a list of artifacts.
    - Caps the total number of artifacts
    - Truncates large text/json/table content inline
    - Stores large content to object storage and sets download_url
    - Truncates large metadata
    """
    if not artifacts:
        return []

    # 1) Cap the number of artifacts
    if len(artifacts) > MAX_ARTIFACTS_COUNT:
        logger.info(
            f"Truncating artifacts list from {len(artifacts)} to {MAX_ARTIFACTS_COUNT}"
        )
        artifacts = artifacts[:MAX_ARTIFACTS_COUNT]

    sanitized: List[Artifact] = []
    for art in artifacts:
        try:
            sanitized_art = await _sanitize_single_artifact(art, project_id)
            sanitized.append(sanitized_art)
        except Exception as e:
            logger.warning(f"Failed to sanitize artifact, dropping it: {e}")

    return sanitized


async def _sanitize_single_artifact(
    artifact: Artifact,
    project_id: Optional[str],
) -> Artifact:
    """Sanitize a single artifact: truncate + offload large content."""

    art = artifact.model_copy()

    # Truncate metadata
    if art.metadata:
        meta_str = json.dumps(art.metadata, ensure_ascii=False)
        if len(meta_str) > MAX_METADATA_INLINE_CHARS:
            art.metadata = {"_truncated": True, "summary": meta_str[:MAX_METADATA_INLINE_CHARS] + "..."}

    # Handle per-type truncation and offloading
    if art.type == ArtifactType.TEXT:
        art = await _sanitize_text_artifact(art, project_id)
    elif art.type == ArtifactType.JSON:
        art = await _sanitize_json_artifact(art, project_id)
    elif art.type == ArtifactType.TABLE:
        art = await _sanitize_table_artifact(art, project_id)
    # IMAGE and FILE types: we assume they use URLs already, no inline content overflow.
    # But we still sanity-check the size field.

    return art


async def _sanitize_text_artifact(art: Artifact, project_id: Optional[str]) -> Artifact:
    content = art.content or ""
    if not isinstance(content, str):
        content = str(content)

    needs_offload = len(content) > LARGE_CONTENT_THRESHOLD_CHARS

    if needs_offload and not art.download_url:
        full_url = await _save_artifact_content_to_storage(content, art.mime_type or "text/plain", project_id)
        if full_url:
            art.download_url = full_url
            art.preview_url = art.preview_url or full_url

    # Always truncate inline content for message size safety
    art.content = _truncate_text(content, MAX_TEXT_INLINE_CHARS)

    return art


async def _sanitize_json_artifact(art: Artifact, project_id: Optional[str]) -> Artifact:
    content = art.content
    try:
        content_str = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
    except Exception:
        content_str = str(content)

    needs_offload = len(content_str) > LARGE_CONTENT_THRESHOLD_CHARS

    if needs_offload and not art.download_url:
        full_url = await _save_artifact_content_to_storage(content_str, "application/json", project_id)
        if full_url:
            art.download_url = full_url
            art.preview_url = art.preview_url or full_url

    # For inline, keep truncated JSON
    try:
        if isinstance(content, str):
            art.content = _truncate_text(content, MAX_JSON_INLINE_CHARS)
        else:
            # Re-serialize and truncate
            truncated_str = _truncate_text(content_str, MAX_JSON_INLINE_CHARS)
            art.content = truncated_str
    except Exception:
        art.content = _truncate_text(str(content), MAX_JSON_INLINE_CHARS)

    return art


async def _sanitize_table_artifact(art: Artifact, project_id: Optional[str]) -> Artifact:
    content = art.content or {}

    if not isinstance(content, dict):
        return art

    columns = content.get("columns", []) if isinstance(content, dict) else []
    rows = content.get("rows", []) if isinstance(content, dict) else []

    total_cells = len(columns) * len(rows)
    needs_offload = len(rows) > LARGE_TABLE_ROWS_THRESHOLD or total_cells > 500

    if needs_offload and not art.download_url:
        try:
            full_table_json = json.dumps({"columns": columns, "rows": rows}, ensure_ascii=False)
            full_url = await _save_artifact_content_to_storage(full_table_json, "application/json", project_id)
            if full_url:
                art.download_url = full_url
                art.preview_url = art.preview_url or full_url
        except Exception as e:
            logger.warning(f"Failed to offload table content: {e}")

    # Truncate inline preview
    truncated_columns = columns[:MAX_TABLE_INLINE_COLUMNS]
    truncated_rows = [row[:MAX_TABLE_INLINE_COLUMNS] for row in rows[:MAX_TABLE_INLINE_ROWS]]

    truncated_content = {
        "columns": truncated_columns,
        "rows": truncated_rows,
        "truncated": {
            "total_columns": len(columns),
            "total_rows": len(rows),
            "shown_columns": len(truncated_columns),
            "shown_rows": len(truncated_rows),
        },
    }
    art.content = truncated_content

    return art
