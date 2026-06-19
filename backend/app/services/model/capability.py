from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from tkhelper.error import raise_request_validation_error

__all__ = [
    "NormalizedCapabilities",
    "CapabilityEvaluationService",
    "CapabilityEvaluationResult",
]


class NormalizedCapabilities(BaseModel):
    streaming: bool = Field(False, description="Whether the model supports streaming output.")
    function_call: bool = Field(False, description="Whether the model supports function/tool calls.")
    vision: bool = Field(False, description="Whether the model supports image/vision input.")
    input_token_limit: Optional[int] = Field(None, description="Maximum input token count.")
    output_token_limit: Optional[int] = Field(None, description="Maximum output token count.")


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


class CapabilityEvaluationService:
    @staticmethod
    def evaluate_model_capabilities(
        model_type: str,
        model_properties: Optional[Dict],
    ) -> NormalizedCapabilities:
        if model_type != "chat_completion":
            return NormalizedCapabilities()

        props = model_properties or {}
        return NormalizedCapabilities(
            streaming=bool(props.get("streaming", False)),
            function_call=bool(props.get("function_call", False)),
            vision=bool(props.get("vision", False)),
            input_token_limit=props.get("input_token_limit"),
            output_token_limit=props.get("output_token_limit"),
        )

    @staticmethod
    def evaluate_model_schema_capabilities(
        model_schema_type: str,
        model_schema_properties: Optional[Dict],
    ) -> NormalizedCapabilities:
        if model_schema_type not in ("chat_completion", "wildcard"):
            return NormalizedCapabilities()

        props = model_schema_properties or {}
        return NormalizedCapabilities(
            streaming=bool(props.get("streaming", True)) if model_schema_type == "wildcard" else bool(props.get("streaming", False)),
            function_call=bool(props.get("function_call", True)) if model_schema_type == "wildcard" else bool(props.get("function_call", False)),
            vision=bool(props.get("vision", True)) if model_schema_type == "wildcard" else bool(props.get("vision", False)),
            input_token_limit=props.get("input_token_limit"),
            output_token_limit=props.get("output_token_limit"),
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

        return base

    @staticmethod
    def validate_requirements(
        capabilities: NormalizedCapabilities,
        require_streaming: bool = False,
        require_function_call: bool = False,
        require_vision: bool = False,
        model_id: Optional[str] = None,
    ) -> CapabilityEvaluationResult:
        reasons: List[_IncompatibilityReason] = []

        if require_streaming and not capabilities.streaming:
            reasons.append(
                _IncompatibilityReason(
                    capability="streaming",
                    required=True,
                    reason=f"Model {model_id or ''} does not support streaming.",
                )
            )

        if require_function_call and not capabilities.function_call:
            reasons.append(
                _IncompatibilityReason(
                    capability="function_call",
                    required=True,
                    reason=f"Model {model_id or ''} does not support function call.",
                )
            )

        if require_vision and not capabilities.vision:
            reasons.append(
                _IncompatibilityReason(
                    capability="vision",
                    required=True,
                    reason=f"Model {model_id or ''} does not support vision input.",
                )
            )

        return CapabilityEvaluationResult(
            capabilities=capabilities,
            incompatibility_reasons=reasons,
        )

    @staticmethod
    def check_and_raise(
        capabilities: NormalizedCapabilities,
        require_streaming: bool = False,
        require_function_call: bool = False,
        require_vision: bool = False,
        model_id: Optional[str] = None,
    ) -> NormalizedCapabilities:
        result = CapabilityEvaluationService.validate_requirements(
            capabilities=capabilities,
            require_streaming=require_streaming,
            require_function_call=require_function_call,
            require_vision=require_vision,
            model_id=model_id,
        )
        if not result.is_compatible:
            first = result.incompatibility_reasons[0]
            raise_request_validation_error(first.reason)
        return capabilities


capability_service = CapabilityEvaluationService()
