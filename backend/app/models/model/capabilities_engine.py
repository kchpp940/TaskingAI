"""
Backend-side Capabilities Derivation Engine
===========================================

This module mirrors the logic of ``inference/app/models/capabilities_engine.py``
so that the backend can derive consistent capabilities even if the inference
service hasn't yet been upgraded (backward compatibility during rolling deploys).

When inference exposes ``capabilities`` on a ModelSchema, that value is used
**first**.  This engine only kicks in as a fallback (or to cross-check).

Derivation priority (same as inference side, highest first):

1. ``capabilities`` object already on the ModelSchema (from inference response)
2. Explicit ``properties`` declared for the specific Model instance (wildcard)
3. Explicit ``properties`` on the ModelSchema (legacy field set)
4. Derived from ``config_schemas`` (e.g. response_format → json_schema)
5. Provider-level defaults
6. Safe fallback defaults

Please keep the provider lists below in SYNC with the inference-side copy
in ``inference/app/models/capabilities_engine.py``.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple


logger = logging.getLogger(__name__)


# --- keep in sync with inference side ---
_OPENAI_COMPATIBLE_PROVIDERS = frozenset(
    {
        "openai",
        "azure_openai",
        "groq",
        "fireworks",
        "leptonai",
        "togetherai",
        "mistralai",
        "siliconcloud",
        "hugging_face",
        "hugging_face_inference_endpoint",
        "ollama",
        "lm_studio",
        "localai",
        "openrouter",
        "deepseek",
        "moonshot",
        "replicate",
        "llama_api",
        "custom_host",
    }
)

_TOOL_CALLING_PROVIDERS = frozenset(
    {
        "openai",
        "azure_openai",
        "anthropic",
        "google_gemini",
        "mistralai",
        "groq",
        "fireworks",
        "togetherai",
        "deepseek",
        "moonshot",
        "custom_host",
        "sensetime",
    }
)

_JSON_SCHEMA_PROVIDERS = frozenset(
    {
        "openai",
        "azure_openai",
        "anthropic",
        "google_gemini",
        "mistralai",
        "groq",
        "fireworks",
        "togetherai",
        "deepseek",
        "moonshot",
        "custom_host",
    }
)

_TEXT = "text"
_JSON_OBJECT = "json_object"
_JSON_SCHEMA = "json_schema"


def _merge_dicts(*dicts: Optional[Dict]) -> Dict:
    """Merge dicts left-to-right, later values override earlier ones."""
    result: Dict[str, Any] = {}
    for d in dicts:
        if not d:
            continue
        for k, v in d.items():
            if v is None:
                continue
            if isinstance(v, dict) and isinstance(result.get(k), dict):
                result[k] = _merge_dicts(result[k], v)
            else:
                result[k] = v
    return result


def _normalise_legacy_properties(props: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Translate legacy property names (streaming → stream, etc.)"""
    if not props:
        return {}
    out: Dict[str, Any] = {}
    if isinstance(props.get("streaming"), bool):
        out["stream"] = props["streaming"]
    if isinstance(props.get("function_call"), bool):
        out["tools"] = props["function_call"]
    if isinstance(props.get("vision"), bool):
        out["vision"] = props["vision"]
    if isinstance(props.get("json_schema"), bool):
        out["json_schema"] = props["json_schema"]
    if isinstance(props.get("input_token_limit"), int):
        out["max_context_tokens"] = props["input_token_limit"]
    if isinstance(props.get("output_token_limit"), int):
        out["max_output_tokens"] = props["output_token_limit"]
    if isinstance(props.get("supported_response_formats"), list):
        out["supported_response_formats"] = list(props["supported_response_formats"])
    return out


def _derive_from_config_schemas(config_schemas: Any) -> Dict[str, Any]:
    """Mirror of inference-side derivation."""
    hints: Dict[str, Any] = {}
    if not isinstance(config_schemas, list):
        return hints
    config_ids: set = set()
    for cs in config_schemas:
        if isinstance(cs, dict) and isinstance(cs.get("config_id"), str):
            config_ids.add(cs["config_id"])
    if "response_format" in config_ids:
        hints["json_schema"] = True
        hints["supported_response_formats"] = [_TEXT, _JSON_OBJECT, _JSON_SCHEMA]
    return hints


def _provider_hints(provider_id: str, model_type: str) -> Dict[str, Any]:
    hints: Dict[str, Any] = {}
    if model_type not in ("chat_completion", "wildcard"):
        return hints
    if provider_id in _OPENAI_COMPATIBLE_PROVIDERS:
        hints["stream"] = True
    if provider_id in _TOOL_CALLING_PROVIDERS:
        hints["tools"] = True
    if provider_id in _JSON_SCHEMA_PROVIDERS:
        hints["json_schema"] = True
        hints["supported_response_formats"] = [_TEXT, _JSON_OBJECT, _JSON_SCHEMA]
    return hints


def derive_model_capabilities(
    *,
    provider_id: str,
    model_schema_id: Optional[str] = None,
    model_type: str = "chat_completion",
    schema_capabilities: Optional[Dict] = None,
    model_properties: Optional[Dict] = None,
    schema_properties: Optional[Dict] = None,
    config_schemas: Optional[List] = None,
    emit_warnings: bool = False,
) -> Dict[str, Any]:
    """
    Unified entry point for the backend.

    Parameters
    ----------
    schema_capabilities:
        The ``capabilities`` dict already exposed by inference, if any.
        This is the highest-priority source.
    model_properties:
        Model-instance level ``properties`` (e.g. user-filled when creating
        a wildcard model).  Overrides schema-level declarations.
    schema_properties:
        Schema-level legacy ``properties`` dict.
    config_schemas:
        Schema-level ``config_schemas`` list for heuristic rule #2.
    """

    # Rule 1: capabilities object from inference wins
    result: Dict[str, Any] = {k: v for k, v in (schema_capabilities or {}).items() if v is not None}

    # Rule 2: user-supplied model properties (wildcard override)
    result = _merge_dicts(result, _normalise_legacy_properties(model_properties))

    # Rule 3: schema legacy properties
    result = _merge_dicts(result, _normalise_legacy_properties(schema_properties))

    # Rule 4: config_schemas derivation
    result = _merge_dicts(result, _derive_from_config_schemas(config_schemas))

    # Rule 5: provider defaults
    result = _merge_dicts(result, _provider_hints(provider_id, model_type or "chat_completion"))

    # Rule 6: safe fallback defaults + consistency
    out: Dict[str, Any] = {
        "stream": bool(result.get("stream", False)),
        "tools": bool(result.get("tools", False)),
        "vision": bool(result.get("vision", False)),
        "json_schema": bool(result.get("json_schema", False)),
        "max_context_tokens": (
            int(result["max_context_tokens"])
            if isinstance(result.get("max_context_tokens"), int)
            else None
        ),
        "max_output_tokens": (
            int(result["max_output_tokens"])
            if isinstance(result.get("max_output_tokens"), int)
            else None
        ),
    }

    srf = result.get("supported_response_formats")
    if isinstance(srf, list) and srf:
        out["supported_response_formats"] = [str(f) for f in srf]
    else:
        out["supported_response_formats"] = [_TEXT]

    if out["json_schema"] and _JSON_SCHEMA not in out["supported_response_formats"]:
        out["supported_response_formats"] = [*out["supported_response_formats"], _JSON_SCHEMA]
    if out["json_schema"] and out["supported_response_formats"] == [_TEXT]:
        out["supported_response_formats"] = [_TEXT, _JSON_OBJECT, _JSON_SCHEMA]

    if emit_warnings and schema_capabilities is None and model_type in (
        "chat_completion",
        "wildcard",
    ):
        logger.debug(
            "backend capabilities derived without inference schema_capabilities: "
            + str({"model_schema_id": model_schema_id, "provider_id": provider_id, "capabilities": out})
        )

    return out


def allow_stream(caps: Dict) -> bool:
    return bool(caps.get("stream", False))


def allow_tools(caps: Dict) -> bool:
    return bool(caps.get("tools", False))


def allow_vision(caps: Dict) -> bool:
    return bool(caps.get("vision", False))


def allow_json_schema(caps: Dict) -> bool:
    return bool(caps.get("json_schema", False))


def supports_response_format(caps: Dict, fmt: str) -> bool:
    formats = caps.get("supported_response_formats") or [_TEXT]
    return fmt in formats


__all__ = [
    "derive_model_capabilities",
    "allow_stream",
    "allow_tools",
    "allow_vision",
    "allow_json_schema",
    "supports_response_format",
]
