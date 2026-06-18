from typing import Dict, Optional, Type, Set
from pydantic import BaseModel, ValidationError
from app.models.base import BaseModelProperties, BaseModelPricing
from app.error import raise_http_error, ErrorCode
import logging

logger = logging.getLogger(__name__)

__all__ = [
    "ModelTypeRegistry",
    "get_registry",
    "register_model_type",
]


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
