from typing import Any, Dict, List, Optional
from fastapi import HTTPException
from pydantic import BaseModel, Field
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
        description="The highest response_format level the model supports: None, 'json_object', or 'json_schema'. Set explicitly via schema capabilities or model properties override only.",
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
    reason: str = Field(..., description="Human-readable reason for the incompatibility, specific to the current requirement context.")


class CapabilityEvaluationResult(BaseModel):
    capabilities: NormalizedCapabilities
    requirement: CapabilityRequirement
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


def _properties_to_response_format(props: Optional[Dict]) -> Optional[str]:
    if not props:
        return None
    rf = props.get("response_format")
    if rf:
        return rf
    return None


def _build_reason(capability: str, requirement_context: str, model_id: str, detail: Optional[str] = None) -> str:
    base = f"Model {model_id or ''} does not support {capability}"
    if requirement_context:
        base += f" {requirement_context}"
    if detail:
        base += f". {detail}"
    base += "."
    return base


class CapabilityEvaluationService:
    @staticmethod
    def evaluate_model_capabilities(
        model_type: str,
        model_properties: Optional[Dict],
    ) -> NormalizedCapabilities:
        if model_type != "chat_completion":
            return NormalizedCapabilities()

        props = model_properties or {}
        rf = _properties_to_response_format(props)
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
    ) -> NormalizedCapabilities:
        if model_schema_type not in ("chat_completion", "wildcard"):
            return NormalizedCapabilities()

        props = model_schema_properties or {}
        is_wildcard = model_schema_type == "wildcard"
        rf = _properties_to_response_format(props)

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
    ) -> NormalizedCapabilities:
        base = NormalizedCapabilities()

        if model_schema_type and model_schema_properties is not None:
            base = CapabilityEvaluationService.evaluate_model_schema_capabilities(
                model_schema_type, model_schema_properties
            )

        if model_type == "chat_completion":
            override = CapabilityEvaluationService.evaluate_model_capabilities(
                model_type, model_properties
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
                    reason=_build_reason(
                        "streaming",
                        "to stream the response",
                        model_id,
                        "Please use a model with streaming support or disable streaming",
                    ),
                )
            )

        if requirement.function_call and not capabilities.function_call:
            reasons.append(
                _IncompatibilityReason(
                    capability="function_call",
                    required=True,
                    reason=_build_reason(
                        "function call",
                        "to run tools, action plugins or retrievals via function invocation",
                        model_id,
                        "Please choose a model with function_call capability or remove the tools/retrievals from the current configuration",
                    ),
                )
            )

        if requirement.vision and not capabilities.vision:
            reasons.append(
                _IncompatibilityReason(
                    capability="vision",
                    required=True,
                    reason=_build_reason(
                        "vision input",
                        "to process images or image content in the user messages",
                        model_id,
                        "Please use a vision-capable model or remove image inputs",
                    ),
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
                            reason=_build_reason(
                                "json_schema response format",
                                "to enforce a strict JSON schema on output",
                                model_id,
                                "This model does not declare explicit json_schema support; please select a model with the response_format=json_schema capability",
                            ),
                        )
                    )
                elif requirement.response_format == "json_object":
                    reasons.append(
                        _IncompatibilityReason(
                            capability="response_format",
                            required=True,
                            reason=_build_reason(
                                "json_object response format",
                                "to guarantee valid JSON output",
                                model_id,
                                "This model does not declare explicit JSON mode support; please select a model with the response_format=json_object capability",
                            ),
                        )
                    )

        return CapabilityEvaluationResult(
            capabilities=capabilities,
            requirement=requirement,
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
    ) -> CapabilityEvaluationResult:
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
            error_detail: Dict[str, Any] = {
                "error_code": "REQUEST_VALIDATION_ERROR",
                "message": first.reason,
                "capability": first.capability,
                "incompatibility_reasons": [
                    r.model_dump() for r in result.incompatibility_reasons
                ],
            }
            raise HTTPException(
                status_code=422,
                detail=error_detail,
            )
        return result


capability_service = CapabilityEvaluationService()
