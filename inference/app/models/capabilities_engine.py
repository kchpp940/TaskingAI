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


def provider_suggests_stream(provider_id: str) -> bool:
    return provider_id in _OPENAI_COMPATIBLE_PROVIDERS


def provider_suggests_tools(provider_id: str) -> bool:
    return provider_id in _TOOL_CALLING_PROVIDERS


def provider_suggests_json_schema(provider_id: str) -> bool:
    return provider_id in _JSON_SCHEMA_PROVIDERS


# ---------------------------------------------------------------------------
# Rule 2 – Derive from config_schemas
# ---------------------------------------------------------------------------

_RESPONSE_FORMAT_CONFIG_IDS = frozenset({"response_format"})


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

    This is considered a **reliable** derivation because the provider code
    explicitly implements response_format handling, so it is safe to enable
    json_schema capability based on it.
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

    **Conservative strategy**: ``tools``, ``vision``, ``json_schema`` can only
    be ``True`` when explicitly declared in YAML properties or derived from
    ``config_schemas``.  Provider-level knowledge is used solely for structured
    warning / suggestion output — it never auto-enables a high-risk capability.

    ``stream`` is low-risk and *is* auto-enabled for OpenAI-compatible providers
    when no explicit declaration exists.

    Returns
    -------
    (capabilities, derivation_sources)
        ``derivation_sources`` maps each field to one of
        ``"explicit"`` | ``"config_schemas"`` | ``"provider_suggestion"`` |
        ``"safe_default"``.  ``"provider_suggestion"`` means the provider
        *could* support it but the field was left at its safe default.
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

    # ------ rule 2: config schemas (reliable derivation) ------
    config_hints = derive_from_config_schemas(config_schemas)

    # ------ rule 3: provider suggestions (NOT auto-enabled for high-risk) ------
    provider_suggestions: Dict[str, Any] = {}
    if model_type == "chat_completion" or model_type == "wildcard":
        provider_suggestions["stream"] = provider_suggests_stream(provider_id)
        provider_suggestions["tools"] = provider_suggests_tools(provider_id)
        if provider_suggests_json_schema(provider_id):
            provider_suggestions["json_schema"] = True
            provider_suggestions["supported_response_formats"] = [
                ResponseFormatType.TEXT,
                ResponseFormatType.JSON_OBJECT,
                ResponseFormatType.JSON_SCHEMA,
            ]

    # ------ resolve with conservative strategy ------
    # stream: low-risk → provider suggestion IS used as a fallback
    # tools/vision/json_schema: high-risk → provider suggestion NOT used as fallback
    sources: Dict[str, str] = {}

    def resolve(
        field: str,
        safe_default: Any,
        allow_provider_fallback: bool = True,
    ) -> Tuple[Any, str]:
        if field in explicit and explicit[field] is not None:
            return explicit[field], "explicit"
        if field in config_hints and config_hints[field] is not None:
            return config_hints[field], "config_schemas"
        if (
            allow_provider_fallback
            and field in provider_suggestions
            and provider_suggestions[field] is not None
        ):
            return provider_suggestions[field], "provider_suggestion"
        if (
            not allow_provider_fallback
            and field in provider_suggestions
            and provider_suggestions[field] is not None
        ):
            # Record that the provider *suggests* it but do NOT use the value
            # — fall through to safe_default instead.
            _ = provider_suggestions[field]  # acknowledged but ignored
            # We still track that a suggestion existed for warning output.
            return safe_default, "provider_suggestion"
        return safe_default, "safe_default"

    stream, sources["stream"] = resolve("stream", False, allow_provider_fallback=True)
    tools, sources["tools"] = resolve("tools", False, allow_provider_fallback=False)
    vision, sources["vision"] = resolve("vision", False, allow_provider_fallback=False)
    json_schema, sources["json_schema"] = resolve("json_schema", False, allow_provider_fallback=False)
    max_context_tokens, sources["max_context_tokens"] = resolve("max_context_tokens", None, allow_provider_fallback=False)
    max_output_tokens, sources["max_output_tokens"] = resolve("max_output_tokens", None, allow_provider_fallback=False)

    srf_value, sources["supported_response_formats"] = resolve(
        "supported_response_formats", [ResponseFormatType.TEXT], allow_provider_fallback=False,
    )
    supported_response_formats: List[str]
    if isinstance(srf_value, list):
        supported_response_formats = [str(f) for f in srf_value]
    else:
        supported_response_formats = [ResponseFormatType.TEXT]

    # Consistency: if json_schema=True but json_schema not in formats, append it.
    if json_schema and ResponseFormatType.JSON_SCHEMA not in supported_response_formats:
        supported_response_formats = [*supported_response_formats, ResponseFormatType.JSON_SCHEMA]
    if json_schema and supported_response_formats == [ResponseFormatType.TEXT]:
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
        # Capabilities that were derived from heuristics (not explicit)
        derived_fields = {
            field: sources[field]
            for field in _ALL_CAPABILITY_FIELDS
            if sources[field] != "explicit"
        }

        # High-risk capabilities where the provider *suggests* support
        # but we held back — these are actionable suggestions
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
            if suggestions:
                payload["suggested_but_not_enabled"] = suggestions
                payload["action_needed"] = (
                    "The following capabilities are likely supported by this "
                    "provider but were not explicitly declared. Add them to the "
                    "YAML properties to enable: "
                    + ", ".join(suggestions.keys())
                )
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
    "derive_from_config_schemas",
    "provider_suggests_stream",
    "provider_suggests_tools",
    "provider_suggests_json_schema",
    "HIGH_RISK_CAPABILITIES",
]

