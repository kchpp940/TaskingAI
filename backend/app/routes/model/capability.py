from tkhelper.schemas.base import BaseListResponse

from ..utils import auth_info_required

from fastapi import APIRouter, Depends, Request
from typing import Dict, List
from app.operators import model_ops
from app.schemas.model.capability import ModelCapabilityEvaluateRequest
from app.services.model.capability import (
    capability_service,
    CapabilityRequirement as ServiceCapabilityRequirement,
)
from tkhelper.error import ErrorCode, raise_http_error

router = APIRouter()


@router.post(
    "/models/capability/evaluate",
    tags=["Model - Model"],
    summary="Evaluate Model Capabilities",
    operation_id="evaluate_model_capabilities",
)
async def api_evaluate_model_capabilities(
    request: Request,
    data: ModelCapabilityEvaluateRequest,
    auth_info: Dict = Depends(auth_info_required),
):
    if data.model_ids:
        models = []
        for mid in data.model_ids:
            try:
                m = await model_ops.get(model_id=mid)
                models.append(m)
            except Exception:
                continue
    else:
        model_type = data.model_type or "chat_completion"
        entities, _ = await model_ops.list(
            limit=1000,
            equal_filters={"type": model_type} if model_type else {},
        )
        models = entities

    requirement = ServiceCapabilityRequirement(
        streaming=data.requirement.streaming,
        function_call=data.requirement.function_call,
        vision=data.requirement.vision,
        response_format=data.requirement.response_format,
    )

    results: List[Dict] = []
    for model in models:
        if not model.is_chat_completion() and not data.model_ids:
            continue
        capabilities = model.get_normalized_capabilities()
        eval_result = capability_service.validate_requirements(
            capabilities=capabilities,
            requirement=requirement,
            model_id=model.model_id,
        )
        results.append({
            "model_id": model.model_id,
            "normalized_capabilities": capabilities.model_dump(exclude_none=True),
            "is_compatible": eval_result.is_compatible,
            "incompatibility_reasons": [r.model_dump() for r in eval_result.incompatibility_reasons],
        })

    return BaseListResponse(
        data=results,
        fetched_count=len(results),
        total_count=len(results),
        has_more=False,
    )
