from typing import List, Optional, Union

from pydantic import BaseModel, Field
from app.models import BaseModelProperties, BaseModelPricing, ModelSchema, ModelCapabilities, ResponseFormatType
from app.models.model_config import validate_config_value
from app.error import raise_http_error, ErrorCode

__all__ = [
    "ChatCompletionModelConfiguration",
    "ChatCompletionModelProperties",
    "ChatCompletionModelPricing",
    "validate_chat_completion_model",
]


class ChatCompletionModelConfiguration(BaseModel):
    temperature: Optional[float] = Field(None)
    top_p: Optional[float] = Field(None)
    top_k: Optional[int] = Field(None)
    max_tokens: Optional[int] = Field(None)
    stop: Optional[Union[str, List[str]]] = Field(None)
    presence_penalty: Optional[float] = Field(None)
    frequency_penalty: Optional[float] = Field(None)
    seed: Optional[int] = Field(None)
    response_format: Optional[str] = Field(None)


class ChatCompletionModelProperties(BaseModelProperties):

    function_call: bool = Field(
        False,
        description="Indicates if the model supports function call.",
    )
    streaming: bool = Field(
        False,
        description="Indicates if the model supports streaming of text chunks.",
    )
    vision: bool = Field(
        False,
        description="Indicates if the model accepts image as input.",
    )
    json_schema: bool = Field(
        False,
        description="Indicates if the model supports structured output with JSON schema.",
    )
    supported_response_formats: Optional[List[str]] = Field(
        None,
        description="List of supported response formats. Defaults to ['text'] if not specified.",
    )
    input_token_limit: Optional[int] = Field(
        None,
        description="The maximum number of tokens that can be included in the model's input.",
    )
    output_token_limit: Optional[int] = Field(
        None,
        description="The maximum number of tokens that the model can generate as output.",
    )

    def to_capabilities(self) -> ModelCapabilities:
        """
        Convert legacy properties to the unified ModelCapabilities schema.
        """
        formats = self.supported_response_formats or [ResponseFormatType.TEXT]
        if self.json_schema and ResponseFormatType.JSON_SCHEMA not in formats:
            formats = [*formats, ResponseFormatType.JSON_SCHEMA]

        return ModelCapabilities(
            stream=self.streaming,
            tools=self.function_call,
            vision=self.vision,
            json_schema=self.json_schema,
            max_context_tokens=self.input_token_limit,
            max_output_tokens=self.output_token_limit,
            supported_response_formats=formats,
        )


class ChatCompletionModelPricing(BaseModelPricing):

    input_token: float = Field(
        ...,
        description="The input token price.",
    )

    output_token: float = Field(
        ...,
        description="The output token price.",
    )

    unit: int = Field(
        ...,
        description="The unit of the price.",
    )


def validate_chat_completion_model(
    model_schema: ModelSchema,
    stream: bool,
    function_call: bool,
    vision_input: bool,
    configs: ChatCompletionModelConfiguration,
    verify: bool = False,
):
    """
    Validate chat completion model's properties and configurations
    :param model_schema: the model schema
    :param stream: whether the request requires streaming
    :param function_call: whether the request requires function call
    :param vision_input: whether the request requires vision input
    :param configs: the model configurations
    :param verify: whether to verify the model
    """
    model_schema_id = model_schema.model_schema_id
    capabilities = model_schema.get_capabilities()

    if stream and not capabilities.stream:
        raise_http_error(ErrorCode.REQUEST_VALIDATION_ERROR, f"model {model_schema_id} does not support streaming.")

    if function_call and not capabilities.tools:
        raise_http_error(
            ErrorCode.REQUEST_VALIDATION_ERROR, f"model {model_schema_id} does not support function/tool call."
        )

    if vision_input and not capabilities.vision:
        raise_http_error(
            ErrorCode.REQUEST_VALIDATION_ERROR, f"model {model_schema_id} does not support vision message."
        )

    # validate response_format / json_schema capability
    response_format = configs.response_format
    if response_format:
        fmt = response_format.lower() if isinstance(response_format, str) else None
        if fmt in ("json_object", "json", "json_schema"):
            normalized = "json_schema" if fmt == "json_schema" else "json_object"
            if not capabilities.json_schema and normalized == "json_schema":
                raise_http_error(
                    ErrorCode.REQUEST_VALIDATION_ERROR,
                    f"model {model_schema_id} does not support structured output with JSON schema. "
                    "Use a model that declares the `json_schema` capability.",
                )
            if normalized not in capabilities.supported_response_formats:
                raise_http_error(
                    ErrorCode.REQUEST_VALIDATION_ERROR,
                    f"model {model_schema_id} does not support response_format='{normalized}'. "
                    f"Supported formats: {capabilities.supported_response_formats}.",
                )

    c_dict = configs.model_dump()
    constraints_dict = {config_schema["config_id"]: config_schema for config_schema in model_schema.config_schemas}
    for key, value in c_dict.items():
        if value is not None:
            if key not in constraints_dict.keys():
                if verify:
                    raise_http_error(
                        ErrorCode.REQUEST_VALIDATION_ERROR, f"{key} is not allowed for the model {model_schema_id}."
                    )
                else:
                    setattr(configs, key, None)
            elif not validate_config_value(value, constraints_dict[key]["schema"]):
                raise_http_error(
                    ErrorCode.REQUEST_VALIDATION_ERROR,
                    f"{key} does not conform to the required constraints: {constraints_dict[key]['schema']}.",
                )
