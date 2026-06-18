from typing import Dict, Optional, Type, Set, List, Any, Union
from pydantic import BaseModel, ValidationError, Field
from app.models.base import BaseModelProperties, BaseModelPricing
from app.error import raise_http_error, ErrorCode
import logging

logger = logging.getLogger(__name__)

__all__ = [
    "ModelTypeRegistry",
    "get_registry",
    "register_model_type",
    "ModelCapabilities",
    "ModelSchemaWarning",
    "ModelSchemaWarningCode",
    "normalize_model_schema_capabilities",
    "NormalizationResult",
]


class ModelSchemaWarningCode(str):
    PROPERTIES_UNREGISTERED_TYPE = "properties_unregistered_type"
    PRICING_UNREGISTERED_TYPE = "pricing_unregistered_type"
    PROPERTIES_DEFAULTS_USED = "properties_defaults_used"
    CAPABILITY_FROM_TYPE_DEFAULT = "capability_from_type_default"
    PROPERTIES_FIELD_MISSING = "properties_field_missing"


class ModelSchemaWarning(BaseModel):
    code: str
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)


class ModelCapabilities(BaseModel):
    streaming: bool = False
    function_call: bool = False
    vision: bool = False
    context_window: Optional[int] = None
    max_output_tokens: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump(exclude_none=True)


class NormalizationResult(BaseModel):
    capabilities: ModelCapabilities
    warnings: List[ModelSchemaWarning] = Field(default_factory=list)


_CAPABILITY_FIELD_MAP: Dict[str, str] = {
    "streaming": "streaming",
    "function_call": "function_call",
    "vision": "vision",
}

_CONTEXT_WINDOW_FIELD = "input_token_limit"
_MAX_OUTPUT_FIELD = "output_token_limit"


class _ModelTypeEntry:
    __slots__ = ("properties_cls", "pricing_cls", "capabilities")

    def __init__(
        self,
        properties_cls: Optional[Type[BaseModelProperties]],
        pricing_cls: Optional[Type[BaseModelPricing]],
        capabilities: Set[str],
    ):
        self.properties_cls = properties_cls
        self.pricing_cls = pricing_cls
        self.capabilities = capabilities


class ModelTypeRegistry:
    def __init__(self):
        self._entries: Dict[str, _ModelTypeEntry] = {}
        self._bootstrapped = False

    def _ensure_bootstrapped(self):
        if self._bootstrapped:
            return
        self._bootstrapped = True
        self._bootstrap()

    def _bootstrap(self):
        from app.models.chat_completion import ChatCompletionModelProperties, ChatCompletionModelPricing
        from app.models.text_embedding import TextEmbeddingModelProperties, TextEmbeddingModelPricing

        self.register(
            "chat_completion",
            properties_cls=ChatCompletionModelProperties,
            pricing_cls=ChatCompletionModelPricing,
            capabilities={"streaming", "function_call", "vision"},
        )
        self.register(
            "text_embedding",
            properties_cls=TextEmbeddingModelProperties,
            pricing_cls=TextEmbeddingModelPricing,
            capabilities=set(),
        )
        self.register(
            "rerank",
            properties_cls=None,
            pricing_cls=None,
            capabilities=set(),
        )
        self.register(
            "wildcard",
            properties_cls=None,
            pricing_cls=None,
            capabilities={"streaming", "function_call", "vision"},
        )

    def register(
        self,
        model_type: str,
        properties_cls: Optional[Type[BaseModelProperties]] = None,
        pricing_cls: Optional[Type[BaseModelPricing]] = None,
        capabilities: Optional[Set[str]] = None,
    ):
        self._entries[model_type] = _ModelTypeEntry(
            properties_cls=properties_cls,
            pricing_cls=pricing_cls,
            capabilities=capabilities or set(),
        )

    def get_properties_cls(self, model_type: str) -> Optional[Type[BaseModelProperties]]:
        self._ensure_bootstrapped()
        entry = self._entries.get(model_type)
        return entry.properties_cls if entry else None

    def get_pricing_cls(self, model_type: str) -> Optional[Type[BaseModelPricing]]:
        self._ensure_bootstrapped()
        entry = self._entries.get(model_type)
        return entry.pricing_cls if entry else None

    def get_capabilities(self, model_type: str) -> Set[str]:
        self._ensure_bootstrapped()
        entry = self._entries.get(model_type)
        return entry.capabilities if entry else set()

    def build_properties(
        self,
        model_type: str,
        properties_dict: Optional[Dict],
    ) -> Optional[BaseModelProperties]:
        self._ensure_bootstrapped()
        if not properties_dict:
            return None
        properties_cls = self.get_properties_cls(model_type)
        if properties_cls is None:
            logger.warning(
                "No properties class registered for model_type=%s, skipping properties parsing",
                model_type,
            )
            return None
        try:
            return properties_cls(**properties_dict)
        except ValidationError as e:
            raise_http_error(
                ErrorCode.REQUEST_VALIDATION_ERROR,
                f"properties is invalid for a {model_type} model. {e}",
            )

    def build_pricing(
        self,
        model_type: str,
        pricing_dict: Optional[Dict],
    ) -> Optional[BaseModelPricing]:
        self._ensure_bootstrapped()
        if not pricing_dict:
            return None
        pricing_cls = self.get_pricing_cls(model_type)
        if pricing_cls is None:
            logger.warning(
                "No pricing class registered for model_type=%s, skipping pricing parsing",
                model_type,
            )
            return None
        return pricing_cls(**pricing_dict)

    def has_capability(self, model_type: str, capability: str) -> bool:
        return capability in self.get_capabilities(model_type)

    def normalize_capabilities(
        self,
        model_type: str,
        properties: Optional[BaseModelProperties],
        properties_raw: Optional[Dict],
        model_schema_id: str,
    ) -> NormalizationResult:
        self._ensure_bootstrapped()
        warnings: List[ModelSchemaWarning] = []
        caps = ModelCapabilities()

        type_default_caps = self.get_capabilities(model_type)

        for reg_capability, prop_name in _CAPABILITY_FIELD_MAP.items():
            if properties is not None and hasattr(properties, prop_name):
                value = getattr(properties, prop_name)
                setattr(caps, reg_capability, bool(value))
            elif reg_capability in type_default_caps:
                setattr(caps, reg_capability, True)
                warnings.append(
                    ModelSchemaWarning(
                        code=ModelSchemaWarningCode.CAPABILITY_FROM_TYPE_DEFAULT,
                        message=(
                            f"Capability '{reg_capability}' inferred from model_type default "
                            f"(properties field '{prop_name}' not present)."
                        ),
                        details={
                            "capability": reg_capability,
                            "property_field": prop_name,
                            "model_schema_id": model_schema_id,
                            "model_type": model_type,
                        },
                    )
                )

        if properties is not None:
            props_dict = properties.model_dump(exclude_none=True)
            if hasattr(properties, _CONTEXT_WINDOW_FIELD):
                caps.context_window = getattr(properties, _CONTEXT_WINDOW_FIELD)
            elif _CONTEXT_WINDOW_FIELD in props_dict:
                caps.context_window = props_dict.get(_CONTEXT_WINDOW_FIELD)
            elif properties_raw and _CONTEXT_WINDOW_FIELD in properties_raw:
                caps.context_window = properties_raw[_CONTEXT_WINDOW_FIELD]

            if hasattr(properties, _MAX_OUTPUT_FIELD):
                caps.max_output_tokens = getattr(properties, _MAX_OUTPUT_FIELD)
            elif _MAX_OUTPUT_FIELD in props_dict:
                caps.max_output_tokens = props_dict.get(_MAX_OUTPUT_FIELD)
            elif properties_raw and _MAX_OUTPUT_FIELD in properties_raw:
                caps.max_output_tokens = properties_raw[_MAX_OUTPUT_FIELD]

        properties_cls = self.get_properties_cls(model_type)
        if properties_cls is not None:
            schema_fields = set(properties_cls.model_fields.keys())
            if properties_raw:
                provided_fields = set(properties_raw.keys())
                unsupported = provided_fields - schema_fields
                if unsupported:
                    for field in sorted(unsupported):
                        warnings.append(
                            ModelSchemaWarning(
                                code=ModelSchemaWarningCode.PROPERTIES_FIELD_MISSING,
                                message=(
                                    f"Properties field '{field}' is not declared in "
                                    f"{properties_cls.__name__} — will be ignored by capability normalization."
                                ),
                                details={
                                    "field": field,
                                    "properties_cls": properties_cls.__name__,
                                    "model_schema_id": model_schema_id,
                                },
                            )
                        )
            declared_cap_fields = {
                name: fld for name, fld in _CAPABILITY_FIELD_MAP.items() if fld in schema_fields
            }
            if properties is None:
                for cap, fld in declared_cap_fields.items():
                    if cap in type_default_caps:
                        continue
                    warnings.append(
                        ModelSchemaWarning(
                            code=ModelSchemaWarningCode.PROPERTIES_DEFAULTS_USED,
                            message=(
                                f"No properties instance for model_type '{model_type}', "
                                f"using False for capability '{cap}' (field '{fld}')."
                            ),
                            details={
                                "capability": cap,
                                "property_field": fld,
                                "model_schema_id": model_schema_id,
                            },
                        )
                    )

        return NormalizationResult(capabilities=caps, warnings=warnings)


_registry = ModelTypeRegistry()


def register_model_type(
    model_type: str,
    properties_cls: Optional[Type[BaseModelProperties]] = None,
    pricing_cls: Optional[Type[BaseModelPricing]] = None,
    capabilities: Optional[Set[str]] = None,
):
    _registry.register(model_type, properties_cls, pricing_cls, capabilities)


def get_registry() -> ModelTypeRegistry:
    return _registry


def normalize_model_schema_capabilities(
    model_type: str,
    properties: Optional[BaseModelProperties],
    properties_raw: Optional[Dict],
    model_schema_id: str,
) -> NormalizationResult:
    return _registry.normalize_capabilities(
        model_type=model_type,
        properties=properties,
        properties_raw=properties_raw,
        model_schema_id=model_schema_id,
    )
