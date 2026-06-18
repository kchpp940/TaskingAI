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

3. **Provider-level defaults (low-risk capabilities only)**
   Only ``stream`` is considered safe enough to default from provider type.
   High-risk capabilities (``tools``, ``vision``, ``json_schema``) are **never**
   auto-enabled by provider defaults because the same provider may host models
   that do *not* support them.  Enabling them without an explicit declaration
   would let requests pass validation and fail at inference time.

4. **Safe fallback defaults**
   boolean fields default to ``False``, numeric fields to ``None``, and
   ``supported_response_formats`` to ``["text"]``.


Conservative strategy for high-risk capabilities
-------------------------------------------------

``tools``, ``vision``, and ``json_schema`` can only be set to ``True`` via:

  a) An explicit declaration in the YAML ``properties`` section, **or**
  b) A user-supplied model-level properties override (wildcard/custom models), **or**
  c) The ``config_schemas`` heuristic (``response_format`` → ``json_schema``).

Provider-level knowledge of which providers *tend* to support these is still
collected in this module — but it is used **only for structured warning /
suggestion output**, never to auto-enable the capability in the returned
``ModelCapabilities`` object.


Structured warnings
-------------------

Whenever a high-risk capability could have been auto-enabled by a provider
default but was **not** (because of the conservative strategy), a structured
JSON-line warning is emitted suggesting the maintainer add an explicit
declaration.  You can grep the startup logs with

    grep 'capabilities_suggestion' <logfile>

to get a machine-readable list of model schemas that should be patched with
explicit ``properties`` fields.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from .base import ModelCapabilities, ResponseFormatType


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Provider-level knowledge (used for warnings / suggestions ONLY)
# ---------------------------------------------------------------------------
# These sets record which providers are *known* to generally support a
# capability, but they must NOT be used to auto-enable the capability in
# the returned ModelCapabilities — that would be too aggressive and could
# cause false-positives for models within the provider that lack support.

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

_HIGH_RISK_CAPABILITIES = frozenset({"tools", "vision", "json_schema"})


# ---------------------------------------------------------------------------
# Capabilities normalization — keeps json_schema bool and
# supported_response_formats list in sync
# ---------------------------------------------------------------------------


def normalize_capabilities(
    caps: ModelCapabilities,
) -> ModelCapabilities:
    """
    Enforce bidirectional consistency between ``json_schema`` (boolean
    capability) and ``supported_response_formats`` (explicit format list).

    Rules:

    1. If ``supported_response_formats`` contains ``"json_schema"`` but
       ``json_schema`` is False → set ``json_schema = True``.
       (An explicit format list is the strongest declaration.)

    2. If ``json_schema = True`` and ``"json_schema"`` is missing from
       ``supported_response_formats`` → append it.

    3. If ``json_schema = True`` and ``supported_response_formats`` is
       only ``["text"]`` → expand to ``["text", "json_object", "json_schema"]``
       since a model that supports json_schema almost always supports
       json_object too.

    This is the **single canonical normalization function** for the
    inference side.  Backend and frontend maintain copies with identical
    logic.  Call this before exposing capabilities to any consumer.
    """

    changed = False

    # Rule 1: explicit formats win over boolean
    if (
        ResponseFormatType.JSON_SCHEMA in caps.supported_response_formats
        and not caps.json_schema
    ):
        caps.json_schema = True
        changed = True

    # Rule 2: boolean triggers format list extension
    if caps.json_schema:
        if ResponseFormatType.JSON_SCHEMA not in caps.supported_response_formats:
            caps.supported_response_formats = [
                *caps.supported_response_formats,
                ResponseFormatType.JSON_SCHEMA,
            ]
            changed = True
        # Rule 3: minimal list expansion
        if caps.supported_response_formats == [ResponseFormatType.TEXT]:
            caps.supported_response_formats = [
                ResponseFormatType.TEXT,
                ResponseFormatType.JSON_OBJECT,
                ResponseFormatType.JSON_SCHEMA,
            ]
            changed = True

    if changed:
        # Re-validate to be safe (Pydantic will coerce types).
        caps = ModelCapabilities.model_validate(caps.model_dump())
    return caps


def provider_suggests_stream(provider_id: str) -> bool:
    return provider_id in _OPENAI_COMPATIBLE_PROVIDERS


def provider_suggests_tools(provider_id: str) -> bool:
    return provider_id in _TOOL_CALLING_PROVIDERS


def provider_suggests_json_schema(provider_id: str) -> bool:
    return provider_id in _JSON_SCHEMA_PROVIDERS


# ---------------------------------------------------------------------------
# config_schemas analysis
# ---------------------------------------------------------------------------
# Having ``response_format`` in config_schemas means the provider code
# implements *some* response format handling — but it does NOT guarantee
# that the model supports JSON Schema structured output.  Many models
# only support plain text or ``json_object``.  Therefore we treat
# ``response_format`` as a *suggestion* only: it is recorded for warning
# output but does NOT auto-enable ``json_schema`` or extend
# ``supported_response_formats``.
#
# The sole reliable source for json_schema is an explicit declaration:
#   - YAML ``properties.json_schema: true``, or
#   - YAML ``properties.supported_response_formats`` containing "json_schema",
#   - User model-level override with the same fields.

_RESPONSE_FORMAT_CONFIG_IDS = frozenset({"response_format"})


def _has_response_format_config(config_schemas: List[Dict[str, Any]]) -> bool:
    config_ids = {cs.get("config_id") for cs in config_schemas if isinstance(cs, dict)}
    return bool(config_ids & _RESPONSE_FORMAT_CONFIG_IDS)


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

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
    model_type: str,
    explicit_properties: Optional[Dict[str, Any]],
    config_schemas: Optional[List[Dict[str, Any]]],
    emit_warnings: bool = True,
) -> Tuple[ModelCapabilities, Dict[str, str]]:
    """
    Derive a unified ``ModelCapabilities`` object.

    **Conservative strategy**:

    ``tools``, ``vision``, and ``json_schema`` can only be ``True`` when
    explicitly declared in YAML properties (``function_call``, ``vision``,
    ``json_schema`` booleans) **or** when ``supported_response_formats``
    explicitly contains ``"json_schema"``.  No heuristic (provider default,
    config_schemas presence) auto-enables them.

    ``stream`` is low-risk and *is* auto-enabled for OpenAI-compatible
    providers when no explicit declaration exists.

    Returns
    -------
    (capabilities, derivation_sources)
        ``derivation_sources`` maps each field to one of
        ``"explicit"`` | ``"provider_suggestion"`` | ``"safe_default"``.
        ``"provider_suggestion"`` means the provider *suggests* it but the
        field was left at its safe default (not enabled).
    """

    props = explicit_properties or {}
    config_schemas = config_schemas or []

    # ------ normalise legacy names ------
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

    # If supported_response_formats explicitly contains "json_schema",
    # that IS a reliable declaration — set json_schema=True.
    if (
        not explicit.get("json_schema")
        and isinstance(explicit.get("supported_response_formats"), list)
        and ResponseFormatType.JSON_SCHEMA in explicit["supported_response_formats"]
    ):
        explicit["json_schema"] = True

    # ------ provider / config suggestions (NOT auto-enabled for high-risk) ------
    has_response_format_cfg = _has_response_format_config(config_schemas)

    provider_suggestions: Dict[str, Any] = {}
    if model_type == "chat_completion" or model_type == "wildcard":
        provider_suggestions["stream"] = provider_suggests_stream(provider_id)
        if provider_suggests_tools(provider_id):
            provider_suggestions["tools"] = True
        if provider_suggests_json_schema(provider_id) or has_response_format_cfg:
            provider_suggestions["json_schema"] = True
            provider_suggestions["supported_response_formats"] = [
                ResponseFormatType.TEXT,
                ResponseFormatType.JSON_OBJECT,
                ResponseFormatType.JSON_SCHEMA,
            ]

    # ------ resolve ------
    # stream: low-risk → provider suggestion IS used as a fallback
    # tools/vision/json_schema: high-risk → suggestions NOT used as fallback
    sources: Dict[str, str] = {}

    def resolve(
        field: str,
        safe_default: Any,
        allow_suggestion_fallback: bool = True,
    ) -> Tuple[Any, str]:
        if field in explicit and explicit[field] is not None:
            return explicit[field], "explicit"
        if (
            allow_suggestion_fallback
            and field in provider_suggestions
            and provider_suggestions[field] is not None
        ):
            return provider_suggestions[field], "provider_suggestion"
        if (
            not allow_suggestion_fallback
            and field in provider_suggestions
            and provider_suggestions[field] is not None
        ):
            return safe_default, "provider_suggestion"
        return safe_default, "safe_default"

    stream, sources["stream"] = resolve("stream", False, allow_suggestion_fallback=True)
    tools, sources["tools"] = resolve("tools", False, allow_suggestion_fallback=False)
    vision, sources["vision"] = resolve("vision", False, allow_suggestion_fallback=False)
    json_schema, sources["json_schema"] = resolve("json_schema", False, allow_suggestion_fallback=False)
    max_context_tokens, sources["max_context_tokens"] = resolve("max_context_tokens", None, allow_suggestion_fallback=False)
    max_output_tokens, sources["max_output_tokens"] = resolve("max_output_tokens", None, allow_suggestion_fallback=False)

    srf_value, sources["supported_response_formats"] = resolve(
        "supported_response_formats", [ResponseFormatType.TEXT], allow_suggestion_fallback=False,
    )
    supported_response_formats: List[str]
    if isinstance(srf_value, list):
        supported_response_formats = [str(f) for f in srf_value]
    else:
        supported_response_formats = [ResponseFormatType.TEXT]

    caps = ModelCapabilities(
        stream=stream,
        tools=tools,
        vision=vision,
        json_schema=json_schema,
        max_context_tokens=max_context_tokens,
        max_output_tokens=max_output_tokens,
        supported_response_formats=supported_response_formats,
    )

    # ------ single canonical normalization: sync json_schema ↔ formats ------
    caps = normalize_capabilities(caps)

    # ------ structured warnings ------
    if emit_warnings and model_type in ("chat_completion", "wildcard"):
        derived_fields = {
            field: sources[field]
            for field in _ALL_CAPABILITY_FIELDS
            if sources[field] != "explicit"
        }

        suggestions = {}
        for field in _HIGH_RISK_CAPABILITIES:
            if sources[field] == "provider_suggestion":
                suggestions[field] = True

        if derived_fields or suggestions:
            payload = {
                "event": "capabilities_derived",
                "model_schema_id": model_schema_id,
                "provider_id": provider_id,
                "derived_fields": derived_fields,
                "capabilities": caps.to_dict(),
            }
            if has_response_format_cfg:
                payload["has_response_format_config"] = True
            if suggestions:
                payload["suggested_but_not_enabled"] = suggestions
                action_parts = []
                if suggestions:
                    action_parts.append(
                        "The following capabilities are likely supported but "
                        "were not explicitly declared. Add them to the YAML "
                        "properties to enable: " + ", ".join(suggestions.keys())
                    )
                if has_response_format_cfg:
                    action_parts.append(
                        "This model has a `response_format` config_schema. "
                        "If it supports json_schema, add `json_schema: true` "
                        "and `supported_response_formats: [text, json_object, json_schema]` "
                        "to its properties."
                    )
                payload["action_needed"] = " ".join(action_parts)
            else:
                payload["action_needed"] = (
                    "Some capabilities were derived heuristically. "
                    "Consider adding explicit properties for: "
                    + ", ".join(derived_fields.keys())
                )
            logger.warning("capabilities_derived " + str(payload))

    return caps, sources


__all__ = [
    "derive_capabilities",
    "normalize_capabilities",
    "provider_suggests_stream",
    "provider_suggests_tools",
    "provider_suggests_json_schema",
    "HIGH_RISK_CAPABILITIES",
]

