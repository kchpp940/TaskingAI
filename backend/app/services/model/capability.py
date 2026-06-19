from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from tkhelper.error import raise_request_validation_error
from enum import Enum

__all__ = [
    "NormalizedCapabilities",
    "CapabilityRequirement",
    "CapabilityEvaluationService",
    "CapabilityEvaluationResult",
]


class ResponseFormatType(str, Enum):
    TEXT = "text"
    JSON_OBJECT = "json_object"
    JSON_SCHEMA = "json_schema"


class NormalizedCapabilities(BaseModel):
    streaming: bool = Field(False, description="Whether the model supports streaming output.")
    function_call: bool = Field(False, description="Whether the model supports function/tool calls.")
    vision: bool = Field(False, description="Whether the model supports image/vision input.")
    input_token_limit: Optional[int] = Field(None, description="Maximum input token count.")
    output_token_limit: Optional[int] = Field(None, description="Maximum output token count.")
    response_format: Optional[str] = Field(
        None,
        description="The highest response_format level the model supports: None, 'json_object', or 'json_schema'.",
    )


class CapabilityRequirement(BaseModel):
    streaming: bool = Field(False, description="Whether the request requires streaming.")
    function_call: bool = Field(False, description="Whether the request requires function/tool call.")
    vision: bool = Field(False, description="Whether the request requires vision/image input.")
    response_format: Optional[str] = Field(
        None,
        description="Required response_format: None, 'json_object', or 'json_schema'.",
    )


class _IncompatibilityReason(BaseModel):
    capability: str = Field(..., description="The capability key that is incompatible.")
    required: bool = Field(..., description="Whether the capability was required.")
    reason: str = Field(..., description="Human-readable reason for the incompatibility.")


class CapabilityEvaluationResult(BaseModel):
    capabilities: NormalizedCapabilities
    incompatibility_reasons: List[_IncompatibilityReason] = Field(default_factory=list)

    @property
    def is_compatible(self) -> bool:
        return len(self.incompatibility_reasons) == 0


def _response_format_level(fmt: Optional[str]) -> int:
    if fmt == "json_schema":
        return 2
    if fmt == "json_object":
        return 1
    return 0


def _allowed_configs_to_response_format(allowed_configs: Optional[List[str]]) -> Optional[str]:
    if not allowed_configs:
        return None
    if "response_format" in allowed_configs:
        return "json_object"
    return None


def _properties_to_response_format(props: Optional[Dict]) -> Optional[str]:
    if not props:
        return None
    rf = props.get("response_format")
    if rf:
        return rf
    return None


class CapabilityEvaluationService:
    @staticmethod
    def evaluate_model_capabilities(
        model_type: str,
        model_properties: Optional[Dict],
        allowed_configs: Optional[List[str]] = None,
    ) -> NormalizedCapabilities:
        if model_type != "chat_completion":
            return NormalizedCapabilities()

        props = model_properties or {}
        rf = _properties_to_response_format(props) or _allowed_configs_to_response_format(allowed_configs)
        return NormalizedCapabilities(
            streaming=bool(props.get("streaming", False)),
            function_call=bool(props.get("function_call", False)),
            vision=bool(props.get("vision", False)),
            input_token_limit=props.get("input_token_limit"),
            output_token_limit=props.get("output_token_limit"),
            response_format=rf,
        )

    @staticmethod
    def evaluate_model_schema_capabilities(
        model_schema_type: str,
        model_schema_properties: Optional[Dict],
        allowed_configs: Optional[List[str]] = None,
    ) -> NormalizedCapabilities:
        if model_schema_type not in ("chat_completion", "wildcard"):
            return NormalizedCapabilities()

        props = model_schema_properties or {}
        is_wildcard = model_schema_type == "wildcard"
        rf = _properties_to_response_format(props) or _allowed_configs_to_response_format(allowed_configs)
        if is_wildcard and rf is None and "response_format" in (allowed_configs or []):
            rf = "json_object"

        return NormalizedCapabilities(
            streaming=bool(props.get("streaming", True)) if is_wildcard else bool(props.get("streaming", False)),
            function_call=bool(props.get("function_call", True)) if is_wildcard else bool(props.get("function_call", False)),
            vision=bool(props.get("vision", True)) if is_wildcard else bool(props.get("vision", False)),
            input_token_limit=props.get("input_token_limit"),
            output_token_limit=props.get("output_token_limit"),
            response_format=rf,
        )

    @staticmethod
    def evaluate(
        model_type: str,
        model_properties: Optional[Dict],
        model_schema_type: Optional[str] = None,
        model_schema_properties: Optional[Dict] = None,
        allowed_configs: Optional[List[str]] = None,
    ) -> NormalizedCapabilities:
        base = NormalizedCapabilities()

        if model_schema_type and model_schema_properties is not None:
            base = CapabilityEvaluationService.evaluate_model_schema_capabilities(
                model_schema_type, model_schema_properties, allowed_configs=allowed_configs,
            )

        if model_type == "chat_completion":
            override = CapabilityEvaluationService.evaluate_model_capabilities(
                model_type, model_properties, allowed_configs=allowed_configs,
            )
            base.streaming = override.streaming
            base.function_call = override.function_call
            base.vision = override.vision
            if override.input_token_limit is not None:
                base.input_token_limit = override.input_token_limit
            if override.output_token_limit is not None:
                base.output_token_limit = override.output_token_limit
            if override.response_format is not None:
                base.response_format = override.response_format

        return base

    @staticmethod
    def validate_requirements(
        capabilities: NormalizedCapabilities,
        requirement: CapabilityRequirement,
        model_id: Optional[str] = None,
    ) -> CapabilityEvaluationResult:
        reasons: List[_IncompatibilityReason] = []

        if requirement.streaming and not capabilities.streaming:
            reasons.append(
                _IncompatibilityReason(
                    capability="streaming",
                    required=True,
                    reason=f"Model {model_id or ''} does not support streaming.",
                )
            )

        if requirement.function_call and not capabilities.function_call:
            reasons.append(
                _IncompatibilityReason(
                    capability="function_call",
                    required=True,
                    reason=f"Model {model_id or ''} does not support function call.",
                )
            )

        if requirement.vision and not capabilities.vision:
            reasons.append(
                _IncompatibilityReason(
                    capability="vision",
                    required=True,
                    reason=f"Model {model_id or ''} does not support vision input.",
                )
            )

        if requirement.response_format:
            required_level = _response_format_level(requirement.response_format)
            supported_level = _response_format_level(capabilities.response_format)
            if supported_level < required_level:
                if requirement.response_format == "json_schema":
                    reasons.append(
                        _IncompatibilityReason(
                            capability="response_format",
                            required=True,
                            reason=f"Model {model_id or ''} does not support json_schema response format.",
                        )
                    )
                elif requirement.response_format == "json_object":
                    reasons.append(
                        _IncompatibilityReason(
                            capability="response_format",
                            required=True,
                            reason=f"Model {model_id or ''} does not support json_object response format.",
                        )
                    )

        return CapabilityEvaluationResult(
            capabilities=capabilities,
            incompatibility_reasons=reasons,
        )

    @staticmethod
    def check_and_raise(
        capabilities: NormalizedCapabilities,
        requirement: Optional[CapabilityRequirement] = None,
        require_streaming: bool = False,
        require_function_call: bool = False,
        require_vision: bool = False,
        require_response_format: Optional[str] = None,
        model_id: Optional[str] = None,
    ) -> NormalizedCapabilities:
        if requirement is None:
            requirement = CapabilityRequirement(
                streaming=require_streaming,
                function_call=require_function_call,
                vision=require_vision,
                response_format=require_response_format,
            )
        result = CapabilityEvaluationService.validate_requirements(
            capabilities=capabilities,
            requirement=requirement,
            model_id=model_id,
        )
        if not result.is_compatible:
            first = result.incompatibility_reasons[0]
            raise_request_validation_error(first.reason)
        return capabilities


capability_service = CapabilityEvaluationService()
