from fastapi import APIRouter, Request, Depends
from typing import Dict

from ..utils import *

from app.operators import record_ops as ops
from app.schemas import *

__all__ = ["router"]

router = APIRouter()


@router.post(
    path="/collections/{collection_id}/records/{record_id}/retry",
    tags=["Retrieval - Record"],
    summary="Retry Record Import",
    operation_id="retry_record",
    response_model=RecordUpdateResponse,
    responses={422: {"description": "Unprocessable Entity"}},
)
async def api_retry(
    request: Request,
    path_params: Dict = Depends(path_params_required),
    auth_info: Dict = Depends(auth_info_required),
):
    check_path_params(
        model_operator=ops,
        object_id_required=True,
        path_params=path_params,
    )

    entity = await ops.retry(**path_params)
    return RecordUpdateResponse(
        data=entity.to_response_dict(),
    )
