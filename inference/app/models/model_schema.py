from enum import Enum
from pydantic import BaseModel, ValidationError
from typing import Dict, Optional, List, Tuple
from .utils import i18n_text
from .base import BaseModelProperties, BaseModelPricing
from .model_type_registry import get_registry
from app.error import raise_http_error, ErrorCode
from .model_config import load_config
import logging
import warnings

warnings.filterwarnings("ignore", module="pydantic")

logger = logging.getLogger(__name__)

__all__ = ["ModelType", "ModelSchema", "validate_model_info"]


class ModelType(str, Enum):
    CHAT_COMPLETION = "chat_completion"
    TEXT_EMBEDDING = "text_embedding"
    RERANK = "rerank"
    WILDCARD = "wildcard"


class ModelSchema(BaseModel):
    model_schema_id: str
    name: str
    description: str
    deprecated: bool

    provider_id: str
    provider_model_id: Optional[str]

    type: ModelType
    properties: Optional[BaseModelProperties]
    config_schemas: List[Dict]
    pricing: Optional[BaseModelPricing]

    def allow_stream(self):
        registry = get_registry()
        if registry.has_capability(self.type.value, "streaming"):
            if self.properties is None:
                return True
            return getattr(self.properties, "streaming", False)
        return False

    def allow_function_call(self):
        registry = get_registry()
        if registry.has_capability(self.type.value, "function_call"):
            if self.properties is None:
                return True
            return getattr(self.properties, "function_call", False)
        return False

    def allow_vision_input(self):
        registry = get_registry()
        if registry.has_capability(self.type.value, "vision"):
            if self.properties is None:
                return True
            return getattr(self.properties, "vision", False)
        return False

    @staticmethod
    def object_name():
        return "ModelSchema"

    @classmethod
    def build(cls, row: Dict):
        registry = get_registry()

        model_type = ModelType(row["type"])
        model_type_value = model_type.value

        properties = registry.build_properties(model_type_value, row.get("properties", {}))

        pricing = registry.build_pricing(model_type_value, row.get("pricing", {}))

        if properties is None and row.get("properties"):
            logger.warning(
                "Properties dict provided but no properties class registered for model_type=%s, model_schema_id=%s",
                model_type_value,
                row.get("model_schema_id"),
            )

        if pricing is None and row.get("pricing"):
            logger.warning(
                "Pricing dict provided but no pricing class registered for model_type=%s, model_schema_id=%s",
                model_type_value,
                row.get("model_schema_id"),
            )

        return cls(
            model_schema_id=row["model_schema_id"],
            name=row["name"] or "",
            description=row["description"],
            deprecated=row.get("deprecated", False),
            provider_id=row["provider_id"],
            provider_model_id=row["provider_model_id"],
            type=model_type,
            properties=properties,
            config_schemas=[load_config(config_schema) for config_schema in row.get("config_schemas") or []],
            pricing=pricing,
        )

    def to_dict(self, lang: str):
        return {
            "object": self.object_name(),
            "model_schema_id": self.model_schema_id,
            "name": i18n_text(self.provider_id, self.name, lang),
            "description": i18n_text(self.provider_id, self.description, lang),
            "deprecated": self.deprecated,
            "provider_id": self.provider_id,
            "provider_model_id": self.provider_model_id,
            "type": self.type.value,
            "properties": self.properties.model_dump(exclude_none=True) if self.properties else None,
            "config_schemas": self.config_schemas,
            "allowed_configs": [config["config_id"] for config in self.config_schemas],
            "pricing": self.pricing.model_dump(exclude_none=True) if self.pricing else None,
        }


def validate_model_info(
    model_schema_id: str,
    provider_model_id: Optional[str],
    properties_dict: Optional[Dict],
    model_type: Optional[ModelType],
) -> Tuple[ModelSchema, str, BaseModelProperties, ModelType]:

    """
    Validate the model info
    :param model_schema_id: the model schema id
    :param provider_model_id: the optional provider model id
    :param properties_dict: the optional model properties dictionary
    :param model_type: the optional model type
    :return: the model schema, provider model id, properties, and model type
    """

    from app.cache import get_model_schema

    registry = get_registry()

    model_schema = get_model_schema(model_schema_id)
    if not model_schema:
        raise_http_error(ErrorCode.OBJECT_NOT_FOUND, f"model schema {model_schema_id} not found.")

    provider_model_id = model_schema.provider_model_id or provider_model_id
    if not provider_model_id:
        raise_http_error(ErrorCode.REQUEST_VALIDATION_ERROR, "provider_model_id is required.")

    properties = model_schema.properties
    _model_type = model_schema.type
    if _model_type == ModelType.WILDCARD:
        _model_type = model_type or _model_type

    if _model_type == ModelType.WILDCARD:
        raise_http_error(ErrorCode.REQUEST_VALIDATION_ERROR, "model_type is required.")

    if model_type is not None and model_type != _model_type:
        raise_http_error(ErrorCode.REQUEST_VALIDATION_ERROR, f"model_type {_model_type} is invalid")

    if not properties:
        properties_cls = registry.get_properties_cls(_model_type.value)
        if properties_cls is not None:
            if _model_type == ModelType.TEXT_EMBEDDING:
                if not properties_dict:
                    raise_http_error(
                        ErrorCode.REQUEST_VALIDATION_ERROR,
                        "property embedding_size is required for a text_embedding model.",
                    )
                try:
                    properties = properties_cls(**properties_dict)
                except ValidationError as e:
                    raise_http_error(
                        ErrorCode.REQUEST_VALIDATION_ERROR,
                        f"properties is invalid for a text_embedding model. {e}",
                    )
            elif _model_type == ModelType.CHAT_COMPLETION:
                properties_dict = properties_dict or {}
                try:
                    properties = properties_cls(**properties_dict)
                except ValidationError:
                    raise_http_error(
                        ErrorCode.REQUEST_VALIDATION_ERROR,
                        "properties is invalid for a chat_completion model.",
                    )
            else:
                pass
        else:
            if _model_type != ModelType.RERANK:
                raise_http_error(ErrorCode.REQUEST_VALIDATION_ERROR, f"model type {model_schema.type} is not supported.")

    return model_schema, provider_model_id, properties, _model_type
