from typing import List, Optional, Dict
from pydantic import BaseModel, Field

__all__ = [
    "ModelCapabilityEvaluateRequest",
]


class CapabilityRequirement(BaseModel):
    streaming: bool = Field(False, description="Whether the request requires streaming.")
    function_call: bool = Field(False, description="Whether the request requires function/tool call.")
    vision: bool = Field(False, description="Whether the request requires vision/image input.")
    response_format: Optional[str] = Field(
        None,
        description="Required response_format: None, 'json_object', or 'json_schema'.",
    )


class ModelCapabilityEvaluateRequest(BaseModel):
    model_ids: Optional[List[str]] = Field(
        None,
        description="Optional list of specific model IDs to evaluate. If not provided, all chat_completion models are evaluated.",
    )
    model_type: Optional[str] = Field(
        None,
        description="Optional model type filter. Defaults to 'chat_completion' when model_ids is not specified.",
    )
    requirement: CapabilityRequirement = Field(
        ...,
        description="The capability requirements to evaluate against each model.",
    )
