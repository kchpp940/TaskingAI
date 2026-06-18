from typing import Optional, Any, List
from pydantic import BaseModel, Field
from typing import Dict, get_type_hints
from abc import ABC, abstractmethod

__all__ = [
    "BaseSuccessEmptyResponse",
    "BaseSuccessDataResponse",
    "BaseSuccessListResponse",
    "BaseModelProperties",
    "BaseModelPricing",
    "ResponseFormatType",
    "ModelCapabilities",
]


class BaseSuccessEmptyResponse(BaseModel):
    status: str = Field("success")


class BaseSuccessDataResponse(BaseModel):
    status: str = Field("success")
    data: Optional[Any] = None


class BaseSuccessListResponse(BaseModel):
    status: str = Field("success")
    data: Any
    fetched_count: int
    total_count: Optional[int] = Field(None)
    has_more: Optional[bool] = Field(None)


class ResponseFormatType(str):
    TEXT = "text"
    JSON_OBJECT = "json_object"
    JSON_SCHEMA = "json_schema"


class ModelCapabilities(BaseModel):
    """
    Unified model capability declaration.
    All providers should expose their model capabilities through this schema.
    """

    stream: bool = Field(
        False,
        description="Whether the model supports streaming output via SSE.",
    )
    tools: bool = Field(
        False,
        description="Whether the model supports tool/function calling.",
    )
    vision: bool = Field(
        False,
        description="Whether the model accepts image input (multimodal).",
    )
    json_schema: bool = Field(
        False,
        description="Whether the model supports structured output with JSON schema.",
    )
    max_context_tokens: Optional[int] = Field(
        None,
        description="Maximum number of tokens the model accepts as context (input + output).",
    )
    max_output_tokens: Optional[int] = Field(
        None,
        description="Maximum number of tokens the model can generate in a single response.",
    )
    supported_response_formats: List[str] = Field(
        default_factory=lambda: [ResponseFormatType.TEXT],
        description="List of supported response formats: 'text', 'json_object', 'json_schema'.",
    )

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump(exclude_none=True)


class BaseModelProperties(BaseModel):

    @classmethod
    def properties_schema(cls) -> Dict[str, Any]:
        schema = cls.model_json_schema()
        properties = schema.get("properties", {})
        type_hints = get_type_hints(cls)
        required_fields = schema.get("required", [])
        simplified_schema = {}

        for attr, details in properties.items():
            # Get the type from type hints if it's more specific
            attr_type = type_hints.get(attr)
            if hasattr(attr_type, "__origin__"):
                # This handles cases like Optional[int]
                attr_type = attr_type.__args__[0]

            simplified_schema[attr] = {
                "type": attr_type.__name__ if attr_type else details.get("type"),
                "description": details.get("description"),
            }

        return {
            "type": "object",
            "properties": simplified_schema,
            "required": required_fields,
        }


class BaseModelPricing(BaseModel):

    currency: str = Field(
        ...,
        description="The currency of the price.",
    )
