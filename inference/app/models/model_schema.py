from enum import Enum
from pydantic import BaseModel, ValidationError
from typing import Dict, Optional, List, Tuple
from .utils import i18n_text
from .base import BaseModelProperties, BaseModelPricing, ModelCapabilities
from app.error import raise_http_error, ErrorCode
from .model_config import load_config
import warnings

warnings.filterwarnings("ignore", module="pydantic")

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

    def get_capabilities(self) -> ModelCapabilities:
        """
        Get the unified capabilities declaration for this model schema.
        Works for all model types — chat_completion, text_embedding, rerank, wildcard.
        """
        from .chat_completion import ChatCompletionModelProperties

        if self.type in (ModelType.CHAT_COMPLETION, ModelType.WILDCARD) and self.properties is not None:
            if isinstance(self.properties, ChatCompletionModelProperties):
                return self.properties.to_capabilities()

        # Default capabilities for non-chat models or when properties not set
        caps = ModelCapabilities()
        if self.properties is not None:
            props_dict = self.properties.model_dump(exclude_none=True)
            if "input_token_limit" in props_dict:
                caps.max_context_tokens = props_dict["input_token_limit"]
            if "output_token_limit" in props_dict:
                caps.max_output_tokens = props_dict["output_token_limit"]
        return caps

    def allow_stream(self):
        return self.get_capabilities().stream

    def allow_function_call(self):
        return self.get_capabilities().tools

    def allow_vision_input(self):
        return self.get_capabilities().vision

    def allow_json_schema(self):
        return self.get_capabilities().json_schema

    def supports_response_format(self, fmt: str) -> bool:
        return fmt in self.get_capabilities().supported_response_formats

    @staticmethod
    def object_name():
        return "ModelSchema"

    @classmethod
    def build(cls, row: Dict):

        # todo: support more model types

        from .chat_completion import ChatCompletionModelProperties
        from .text_embedding import TextEmbeddingModelProperties

        model_type = ModelType(row["type"]) or None

        properties_dict = row.get("properties", {})
        properties = None
        if properties_dict:
            if model_type == ModelType.CHAT_COMPLETION:
                properties = ChatCompletionModelProperties(**properties_dict)
            elif model_type == ModelType.TEXT_EMBEDDING:
                properties = TextEmbeddingModelProperties(**properties_dict)

        pricing_dict = row.get("pricing", {})
        pricing = None
        if pricing_dict:
            if model_type == ModelType.CHAT_COMPLETION:
                from .chat_completion import ChatCompletionModelPricing

                pricing = ChatCompletionModelPricing(**pricing_dict)
            elif model_type == ModelType.TEXT_EMBEDDING:
                from .text_embedding import TextEmbeddingModelPricing

                pricing = TextEmbeddingModelPricing(**pricing_dict)

        # pricing check
        # if not pricing:
        #     raise ValueError(f"pricing is required for model {row['model_schema_id']}")

        # config_schemas = [load_config(config_schema) for config_schema in row.get("config_schemas", [])]
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
            "capabilities": self.get_capabilities().to_dict(),
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

    from .chat_completion import ChatCompletionModelProperties
    from .text_embedding import TextEmbeddingModelProperties
    from app.cache import get_model_schema

    # check model_schema_id validity
    model_schema = get_model_schema(model_schema_id)
    if not model_schema:
        raise_http_error(ErrorCode.OBJECT_NOT_FOUND, f"model schema {model_schema_id} not found.")

    # check provider_model_id validity
    provider_model_id = model_schema.provider_model_id or provider_model_id
    if not provider_model_id:
        raise_http_error(ErrorCode.REQUEST_VALIDATION_ERROR, "provider_model_id is required.")

    # check properties validity
    properties = model_schema.properties
    _model_type = model_schema.type
    if _model_type == ModelType.WILDCARD:
        _model_type = model_type or _model_type

    if _model_type == ModelType.WILDCARD:
        raise_http_error(ErrorCode.REQUEST_VALIDATION_ERROR, "model_type is required.")

    if model_type is not None and model_type != _model_type:
        raise_http_error(ErrorCode.REQUEST_VALIDATION_ERROR, f"model_type {_model_type} is invalid")

    if not properties:
        if _model_type == ModelType.TEXT_EMBEDDING:
            if properties_dict:
                try:
                    properties = TextEmbeddingModelProperties(**properties_dict)
                except ValidationError as e:
                    raise_http_error(
                        ErrorCode.REQUEST_VALIDATION_ERROR,
                        f"properties is invalid for a text_embedding model. {e}",
                    )
            else:
                raise_http_error(
                    ErrorCode.REQUEST_VALIDATION_ERROR,
                    "property embedding_size is required for a text_embedding model.",
                )
        elif _model_type == ModelType.CHAT_COMPLETION:
            properties_dict = properties_dict or {}
            try:
                properties = ChatCompletionModelProperties(**properties_dict)
            except ValidationError as e:
                raise_http_error(
                    ErrorCode.REQUEST_VALIDATION_ERROR,
                    f"properties is invalid for a chat_completion model.",
                )
        elif _model_type == ModelType.RERANK:
            pass
        else:
            raise_http_error(ErrorCode.REQUEST_VALIDATION_ERROR, f"model type {model_schema.type} is not supported.")

    return model_schema, provider_model_id, properties, _model_type
