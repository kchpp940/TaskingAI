"""
Centralized Capabilities Derivation Engine
==========================================

This module unifies how model capabilities are resolved for *every* provider
and *every* model schema, so that no YAML file needs to be manually patched
one-by-one.

Derivation order (highest priority first)
-----------------------------------------

1. **Explicit properties declared in the model YAML**
   (``properties.streaming``, ``properties.function_call``, ...)

2. **Derived from ``config_schemas``**
   e.g. a model whose YAML lists ``response_format`` in config_schemas
   implicitly supports JSON schema structured output.

3. **Provider-level defaults**
   e.g. OpenAI-compatible providers (``openai``, ``groq``, ``fireworks``, ...)
   all support streaming SSE out of the box.

4. **Safe fallback defaults**
   boolean fields default to ``False``, numeric fields to ``None``, and
   ``supported_response_formats`` to ``["text"]``.


Structured warnings
-------------------

Whenever a capability is filled in by a *heuristic* (rule 2 or 3) rather than
an explicit declaration (rule 1), a structured JSON-line warning is emitted.
You can grep the startup logs with

    grep 'capabilities_derived' <logfile>

to get a machine-readable list of model schemas that should be patched with
explicit ``properties`` fields.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from .base import ModelCapabilities, ResponseFormatType


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Rule 3 – Provider-level defaults
# ---------------------------------------------------------------------------

# All providers whose API is OpenAI-compatible support streaming SSE.
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

# Providers whose latest models are known to support tool/function calling
# out of the box (older models may still need YAML-level opt-out).
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

# Providers whose official APIs support structured output / response_format.
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


def provider_default_stream(provider_id: str) -> bool:
    return provider_id in _OPENAI_COMPATIBLE_PROVIDERS


def provider_default_tools(provider_id: str) -> bool:
    return provider_id in _TOOL_CALLING_PROVIDERS


def provider_default_json_schema(provider_id: str) -> bool:
    return provider_id in _JSON_SCHEMA_PROVIDERS


# ---------------------------------------------------------------------------
# Rule 2 – Derive from config_schemas
# ---------------------------------------------------------------------------

_RESPONSE_FORMAT_CONFIG_IDS = frozenset({"response_format"})
_VISION_CONFIG_IDS = frozenset({"vision"})  # not a real config id, but a future-proof marker


def derive_from_config_schemas(
    config_schemas: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Return a dict of capability hints extracted purely from the list of
    config schemas declared in the YAML.

    Rules:
      - Any schema with ``config_id == "response_format"`` implies
        ``json_schema=True`` and a supported response format list of
        ``["text", "json_object", "json_schema"]``.
    """

    hints: Dict[str, Any] = {}
    config_ids = {cs.get("config_id") for cs in config_schemas if isinstance(cs, dict)}

    if config_ids & _RESPONSE_FORMAT_CONFIG_IDS:
        hints["json_schema"] = True
        hints["supported_response_formats"] = [
            ResponseFormatType.TEXT,
            ResponseFormatType.JSON_OBJECT,
            ResponseFormatType.JSON_SCHEMA,
        ]

    return hints


# ---------------------------------------------------------------------------
# Rule 1-2-3 Aggregation
# ---------------------------------------------------------------------------

# Fields that are considered "fully declared" when present in explicit
# properties; missing any of these will trigger a warning.
_ALL_CAPABILITY_FIELDS = (
    "stream",
    "tools",
    "vision",
    "json_schema",
    "max_context_tokens",
    "max_output_tokens",
    "supported_response_formats",
)


def derive_capabilities(
    *,
    provider_id: str,
    model_schema_id: str,
    model_type: str,  # "chat_completion" | "text_embedding" | "rerank" | "wildcard"
    explicit_properties: Optional[Dict[str, Any]],
    config_schemas: Optional[List[Dict[str, Any]]],
    emit_warnings: bool = True,
) -> Tuple[ModelCapabilities, Dict[str, str]]:
    """
    Derive a unified ``ModelCapabilities`` object by applying the four rules
    outlined in the module docstring.

    Returns
    -------
    (capabilities, derivation_sources)
        ``derivation_sources`` is a dict mapping each capability field to one of
        ``"explicit"`` | ``"config_schemas"`` | ``"provider_default"`` |
        ``"safe_default"``, useful for emitting structured warnings and for
        tests.
    """

    props = explicit_properties or {}
    config_schemas = config_schemas or []

    # ------ normalise legacy names ------
    # properties files use the legacy names; translate them to the canonical
    # capabilities keys on the fly.
    explicit: Dict[str, Any] = {}
    if "streaming" in props:
        explicit["stream"] = bool(props["streaming"])
    if "function_call" in props:
        explicit["tools"] = bool(props["function_call"])
    if "vision" in props:
        explicit["vision"] = bool(props["vision"])
    if "json_schema" in props:
        explicit["json_schema"] = bool(props["json_schema"])
    if "input_token_limit" in props:
        explicit["max_context_tokens"] = props["input_token_limit"]
    if "output_token_limit" in props:
        explicit["max_output_tokens"] = props["output_token_limit"]
    if isinstance(props.get("supported_response_formats"), list):
        explicit["supported_response_formats"] = list(props["supported_response_formats"])

    # ------ rule 2: config schemas ------
    config_hints = derive_from_config_schemas(config_schemas)

    # ------ rule 3: provider defaults ------
    provider_hints: Dict[str, Any] = {}
    if model_type == "chat_completion" or model_type == "wildcard":
        provider_hints["stream"] = provider_default_stream(provider_id)
        provider_hints["tools"] = provider_default_tools(provider_id)
        if provider_default_json_schema(provider_id):
            provider_hints["json_schema"] = True
            provider_hints["supported_response_formats"] = [
                ResponseFormatType.TEXT,
                ResponseFormatType.JSON_OBJECT,
                ResponseFormatType.JSON_SCHEMA,
            ]

    # ------ apply priority: rule 1 > rule 2 > rule 3 > safe default ------
    sources: Dict[str, str] = {}

    def resolve(field: str, safe_default: Any) -> Tuple[Any, str]:
        if field in explicit and explicit[field] is not None:
            return explicit[field], "explicit"
        if field in config_hints and config_hints[field] is not None:
            return config_hints[field], "config_schemas"
        if field in provider_hints and provider_hints[field] is not None:
            return provider_hints[field], "provider_default"
        return safe_default, "safe_default"

    stream, sources["stream"] = resolve("stream", False)
    tools, sources["tools"] = resolve("tools", False)
    vision, sources["vision"] = resolve("vision", False)
    json_schema, sources["json_schema"] = resolve("json_schema", False)
    max_context_tokens, sources["max_context_tokens"] = resolve("max_context_tokens", None)
    max_output_tokens, sources["max_output_tokens"] = resolve("max_output_tokens", None)

    # supported_response_formats needs extra care because its values are lists
    # and we also want to keep `json_schema` consistent with the list.
    srf_value, sources["supported_response_formats"] = resolve(
        "supported_response_formats", [ResponseFormatType.TEXT]
    )
    supported_response_formats: List[str]
    if isinstance(srf_value, list):
        supported_response_formats = [str(f) for f in srf_value]
    else:
        supported_response_formats = [ResponseFormatType.TEXT]

    # Consistency: if json_schema=True but json_schema not in formats, append it.
    if json_schema and ResponseFormatType.JSON_SCHEMA not in supported_response_formats:
        supported_response_formats = [*supported_response_formats, ResponseFormatType.JSON_SCHEMA]
    # Consistency: if only text in formats, but json_object was probably wanted
    # (e.g. provider default), extend it.
    if (
        json_schema
        and supported_response_formats == [ResponseFormatType.TEXT]
    ):
        supported_response_formats = [
            ResponseFormatType.TEXT,
            ResponseFormatType.JSON_OBJECT,
            ResponseFormatType.JSON_SCHEMA,
        ]

    caps = ModelCapabilities(
        stream=stream,
        tools=tools,
        vision=vision,
        json_schema=json_schema,
        max_context_tokens=max_context_tokens,
        max_output_tokens=max_output_tokens,
        supported_response_formats=supported_response_formats,
    )

    # ------ structured warnings ------
    if emit_warnings and model_type in ("chat_completion", "wildcard"):
        heuristic_fields = [
            field for field in _ALL_CAPABILITY_FIELDS if sources[field] != "explicit"
        ]
        if heuristic_fields:
            logger.warning(
                "capabilities_derived "
                + str(
                    {
                        "event": "capabilities_derived",
                        "model_schema_id": model_schema_id,
                        "provider_id": provider_id,
                        "derived_fields": {
                            field: sources[field] for field in heuristic_fields
                        },
                        "capabilities": caps.to_dict(),
                        "action_needed": (
                            "Add explicit properties to the YAML for: "
                            + ", ".join(heuristic_fields)
                        ),
                    }
                )
            )

    return caps, sources


__all__ = [
    "derive_capabilities",
    "derive_from_config_schemas",
    "provider_default_stream",
    "provider_default_tools",
    "provider_default_json_schema",
]
