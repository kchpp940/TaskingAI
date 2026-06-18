import json
import logging
from typing import List, Any, Optional, Dict

from app.models.tool.tool import Artifact, ArtifactType

logger = logging.getLogger(__name__)


# Same limits as plugin side for consistency
MAX_ARTIFACTS_COUNT = 10
MAX_TEXT_INLINE_CHARS = 2000
MAX_JSON_INLINE_CHARS = 3000
MAX_TABLE_INLINE_ROWS = 20
MAX_TABLE_INLINE_COLUMNS = 15
MAX_METADATA_INLINE_CHARS = 500

# Data payload limits for LLM function messages
MAX_DATA_TOTAL_CHARS = 3000
MAX_DATA_VALUE_CHARS = 500
MAX_DATA_LIST_ITEMS = 10


def _truncate_text(text: str, max_chars: int) -> str:
    if text is None:
        return ""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "... (truncated)"


def sanitize_artifacts_backend(
    artifacts: List[Artifact],
) -> List[Artifact]:
    """
    Lightweight backend-side sanitizer as an extra safety layer.
    The plugin-side sanitizer already handles offloading; this just trims any
    large content that might have slipped through, to keep message payloads small.
    """
    if not artifacts:
        return []

    # 1) Cap artifact count
    if len(artifacts) > MAX_ARTIFACTS_COUNT:
        logger.info(f"Backend: truncating artifacts from {len(artifacts)} to {MAX_ARTIFACTS_COUNT}")
        artifacts = artifacts[:MAX_ARTIFACTS_COUNT]

    sanitized: List[Artifact] = []
    for art in artifacts:
        try:
            sanitized.append(_sanitize_single(art))
        except Exception as e:
            logger.warning(f"Backend: failed to sanitize artifact: {e}")

    return sanitized


def _sanitize_single(artifact: Artifact) -> Artifact:
    art = artifact.model_copy()

    # Truncate metadata
    if art.metadata:
        try:
            meta_str = json.dumps(art.metadata, ensure_ascii=False)
            if len(meta_str) > MAX_METADATA_INLINE_CHARS:
                art.metadata = {"_truncated": True, "summary": meta_str[:MAX_METADATA_INLINE_CHARS] + "..."}
        except Exception:
            art.metadata = None

    # Truncate content per type
    if art.type == ArtifactType.TEXT and art.content:
        content_str = art.content if isinstance(art.content, str) else str(art.content)
        art.content = _truncate_text(content_str, MAX_TEXT_INLINE_CHARS)

    elif art.type == ArtifactType.JSON and art.content:
        try:
            if isinstance(art.content, str):
                art.content = _truncate_text(art.content, MAX_JSON_INLINE_CHARS)
            else:
                content_str = json.dumps(art.content, ensure_ascii=False)
                art.content = _truncate_text(content_str, MAX_JSON_INLINE_CHARS)
        except Exception:
            art.content = _truncate_text(str(art.content), MAX_JSON_INLINE_CHARS)

    elif art.type == ArtifactType.TABLE and isinstance(art.content, dict):
        columns = art.content.get("columns", []) or []
        rows = art.content.get("rows", []) or []
        truncated_columns = columns[:MAX_TABLE_INLINE_COLUMNS]
        truncated_rows = [row[:MAX_TABLE_INLINE_COLUMNS] for row in rows[:MAX_TABLE_INLINE_ROWS]]

        existing_truncated = art.content.get("truncated", {}) or {}
        truncated_content = {
            "columns": truncated_columns,
            "rows": truncated_rows,
            "truncated": {
                "total_columns": existing_truncated.get("total_columns", len(columns)),
                "total_rows": existing_truncated.get("total_rows", len(rows)),
                "shown_columns": len(truncated_columns),
                "shown_rows": len(truncated_rows),
            },
        }
        art.content = truncated_content

    return art


# ============================================================
# Data payload sanitization for LLM function messages
# ============================================================

def _trim_data_value(value: Any, max_chars: int = MAX_DATA_VALUE_CHARS, max_list_items: int = MAX_DATA_LIST_ITEMS, depth: int = 0) -> Any:
    """Recursively trim large values in a data structure."""
    if depth > 5:
        return "... (nested too deep)"

    if isinstance(value, str):
        if len(value) > max_chars:
            return value[:max_chars] + "... (truncated)"
        return value

    elif isinstance(value, list):
        if len(value) > max_list_items:
            trimmed = [_trim_data_value(item, max_chars, max_list_items, depth + 1) for item in value[:max_list_items]]
            trimmed.append(f"... ({len(value) - max_list_items} more items)")
            return trimmed
        return [_trim_data_value(item, max_chars, max_list_items, depth + 1) for item in value]

    elif isinstance(value, dict):
        if depth == 0:
            return {k: _trim_data_value(v, max_chars, max_list_items, depth + 1) for k, v in value.items()}
        else:
            items = list(value.items())
            if len(items) > 20:
                result = {k: _trim_data_value(v, max_chars, max_list_items, depth + 1) for k, v in items[:20]}
                result["..."] = f"({len(value) - 20} more keys)"
                return result
            return {k: _trim_data_value(v, max_chars, max_list_items, depth + 1) for k, v in value.items()}

    else:
        return value


def _build_artifact_summary(artifacts: List[Artifact]) -> str:
    """Build a human-readable summary of artifacts for inclusion in data/function messages."""
    if not artifacts:
        return ""

    type_counts: Dict[str, int] = {}
    for art in artifacts:
        t = art.type.value if hasattr(art.type, 'value') else str(art.type)
        type_counts[t] = type_counts.get(t, 0) + 1

    parts = []
    for t, count in sorted(type_counts.items()):
        parts.append(f"{count} {t}(s)")

    return ", ".join(parts)


def sanitize_tool_output_data(
    data: Any,
    artifacts: List[Artifact],
) -> Any:
    """
    Backend-side data sanitization to keep LLM function messages small.
    Applies recursive trimming and adds artifact summary when available.
    This is a safety net — plugin-side sanitization should already have done most of the work.
    """
    if not data:
        return data

    try:
        data_str = json.dumps(data, ensure_ascii=False)
        if len(data_str) <= MAX_DATA_TOTAL_CHARS and not artifacts:
            return data

        # Trim large values
        sanitized = _trim_data_value(data)

        # Add artifact summary
        if artifacts:
            summary = _build_artifact_summary(artifacts)
            if isinstance(sanitized, dict):
                sanitized["_artifacts_summary"] = summary
                sanitized["_note"] = "Full structured content available in message artifacts; data field is truncated for efficiency."

        # Final size check — if still too large, use minimal form
        sanitized_str = json.dumps(sanitized, ensure_ascii=False)
        if len(sanitized_str) > MAX_DATA_TOTAL_CHARS * 2:
            summary = _build_artifact_summary(artifacts)
            sanitized = {
                "_truncated": True,
                "_artifacts_summary": summary,
                "_note": "Tool output data is large. See message artifacts for structured content.",
            }

        return sanitized

    except Exception as e:
        logger.warning(f"Failed to sanitize tool output data: {e}")
        return data
