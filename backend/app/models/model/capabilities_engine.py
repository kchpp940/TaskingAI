"""
Backend-side Capabilities Derivation Engine
===========================================

This module mirrors the logic of ``inference/app/models/capabilities_engine.py``
so that the backend can derive consistent capabilities even if the inference
service hasn't yet been upgraded (backward compatibility during rolling deploys).

When inference exposes ``capabilities`` on a ModelSchema, that value is used
**first**.  This engine only kicks in as a fallback (or to cross-check).

**Conservative strategy (same as inference side):**

``tools``, ``vision``, and ``json_schema`` are high-risk capabilities — they
can only be set to ``True`` via:

  1. The ``capabilities`` object from the inference service, **or**
  2. User-supplied model-level properties (wildcard/custom models), **or**
  3. Schema-level legacy properties (explicit YAML declarations), **or**
  4. The ``config_schemas`` heuristic (``response_format`` → ``json_schema``).

Provider-level knowledge of which providers *tend* to support these is collected
below, but is used **only for structured warning / suggestion output** — it
must NOT auto-enable a high-risk capability.  Doing so could let requests pass
validation for a model that doesn't actually support the feature, causing
runtime failures.

``stream`` is low-risk and *is* auto-enabled for OpenAI-compatible providers.

Please keep the provider lists below in SYNC with the inference-side copy
in ``inference/app/models/capabilities_engine.py``.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional


logger = logging.getLogger(__name__)


_HIGH_RISK_CAPABILITIES = frozenset({"tools", "vision", "json_schema"})

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


def _normalise_legacy_properties(props: Optional[Dict[str, Any]]) -> Dict[str, Any]:
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
    """
    Extract hints from config_schemas.

    Having ``response_format`` in config_schemas means the provider implements
    *some* response format handling, but does NOT guarantee json_schema support.
    Many models only support plain text or ``json_object``.  Therefore this
    function returns an **empty** hints dict — the response_format presence
    is recorded separately for warning/suggestion output instead.
    """
    return {}


def _has_response_format_config(config_schemas: Any) -> bool:
    if not isinstance(config_schemas, list):
        return False
    for cs in config_schemas:
        if isinstance(cs, dict) and cs.get("config_id") == "response_format":
            return True
    return False


def _provider_suggestions(provider_id: str, model_type: str) -> Dict[str, Any]:
    """
    Return provider-level *suggestions* (NOT auto-enabled defaults).

    Only ``stream`` is safe to auto-enable (low-risk).  High-risk capabilities
    (tools, vision, json_schema) are returned here solely so that warning
    logic can tell the maintainer "this provider likely supports X, consider
    adding an explicit declaration".
    """
    suggestions: Dict[str, Any] = {}
    if model_type not in ("chat_completion", "wildcard"):
        return suggestions
    if provider_id in _OPENAI_COMPATIBLE_PROVIDERS:
        suggestions["stream"] = True
    if provider_id in _TOOL_CALLING_PROVIDERS:
        suggestions["tools"] = True
    if provider_id in _JSON_SCHEMA_PROVIDERS:
        suggestions["json_schema"] = True
        suggestions["supported_response_formats"] = [_TEXT, _JSON_OBJECT, _JSON_SCHEMA]
    return suggestions


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
    Unified entry point for the backend.  Conservative strategy:

    Priority (highest first):
      1. schema_capabilities from inference (already resolved authoritatively)
      2. User-supplied model-level properties (wildcard override)
      3. Schema-level legacy properties
      4. If supported_response_formats contains "json_schema" → json_schema=True
      5. Provider suggestions — **only ``stream`` is auto-enabled**;
         high-risk fields (tools, vision, json_schema) from provider
         suggestions are recorded for warning output but NOT used.
         Having ``response_format`` in config_schemas is also a suggestion
         for json_schema, not a reliable source.
      6. Safe fallback defaults
    """

    # --- Collect all explicit/reliable sources (rules 1-3) ---
    reliable: Dict[str, Any] = {}
    for k, v in (schema_capabilities or {}).items():
        if v is not None:
            reliable[k] = v
    for k, v in _normalise_legacy_properties(model_properties).items():
        if v is not None:
            reliable[k] = v
    for k, v in _normalise_legacy_properties(schema_properties).items():
        if v is not None:
            reliable[k] = v

    # Rule 4: supported_response_formats containing "json_schema" IS reliable
    if (
        not reliable.get("json_schema")
        and isinstance(reliable.get("supported_response_formats"), list)
        and _JSON_SCHEMA in reliable["supported_response_formats"]
    ):
        reliable["json_schema"] = True

    # --- Provider / config suggestions (rule 5) ---
    has_rf_cfg = _has_response_format_config(config_schemas)
    suggestions = _provider_suggestions(provider_id, model_type or "chat_completion")

    # Merge response_format config hint into suggestions
    if has_rf_cfg and not suggestions.get("json_schema"):
        suggestions["json_schema"] = True
        suggestions["supported_response_formats"] = [_TEXT, _JSON_OBJECT, _JSON_SCHEMA]

    # --- Build final capabilities ---
    out: Dict[str, Any] = {}

    out["stream"] = bool(reliable.get("stream", suggestions.get("stream", False)))
    out["tools"] = bool(reliable.get("tools", False))
    out["vision"] = bool(reliable.get("vision", False))
    out["json_schema"] = bool(reliable.get("json_schema", False))
    out["max_context_tokens"] = (
        int(reliable["max_context_tokens"])
        if isinstance(reliable.get("max_context_tokens"), int)
        else None
    )
    out["max_output_tokens"] = (
        int(reliable["max_output_tokens"])
        if isinstance(reliable.get("max_output_tokens"), int)
        else None
    )

    srf = reliable.get("supported_response_formats")
    if isinstance(srf, list) and srf:
        out["supported_response_formats"] = [str(f) for f in srf]
    else:
        out["supported_response_formats"] = [_TEXT]

    if out["json_schema"] and _JSON_SCHEMA not in out["supported_response_formats"]:
        out["supported_response_formats"] = [*out["supported_response_formats"], _JSON_SCHEMA]
    if out["json_schema"] and out["supported_response_formats"] == [_TEXT]:
        out["supported_response_formats"] = [_TEXT, _JSON_OBJECT, _JSON_SCHEMA]

    # --- Warnings ---
    if emit_warnings and model_type in ("chat_completion", "wildcard"):
        suggested_not_enabled = {
            field: True
            for field in _HIGH_RISK_CAPABILITIES
            if suggestions.get(field) and not out.get(field)
        }
        if suggested_not_enabled or schema_capabilities is None:
            payload = {
                "model_schema_id": model_schema_id,
                "provider_id": provider_id,
                "capabilities": out,
            }
            if has_rf_cfg:
                payload["has_response_format_config"] = True
            if suggested_not_enabled:
                payload["suggested_but_not_enabled"] = suggested_not_enabled
                action_parts = []
                action_parts.append(
                    "The following capabilities are likely supported but "
                    "were not explicitly declared. Add them to the YAML "
                    "properties to enable: " + ", ".join(suggested_not_enabled.keys())
                )
                if has_rf_cfg:
                    action_parts.append(
                        "This model has a `response_format` config_schema. "
                        "If it supports json_schema, add `json_schema: true` "
                        "and `supported_response_formats: [text, json_object, json_schema]` "
                        "to its properties."
                    )
                payload["action_needed"] = " ".join(action_parts)
            logger.debug(
                "backend capabilities derived: " + str(payload)
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
