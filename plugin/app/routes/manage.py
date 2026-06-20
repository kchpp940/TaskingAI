from fastapi import APIRouter, Request
from app.models import BaseSuccessEmptyResponse, BaseSuccessDataResponse
from config import CONFIG
import logging
from app.cache import *

logger = logging.Logger(__name__)

router = APIRouter()


@router.get(
    "/health_check",
    tags=["Manage"],
    operation_id="health_check",
    summary="Health check",
    response_model=BaseSuccessDataResponse,
    include_in_schema=False,
)
async def api_health_check(request: Request):
    lifecycle_state = getattr(request.app.state, "lifecycle_state", None)
    lifecycle_status = getattr(request.app.state, "lifecycle_status", None)

    data = {
        "status": lifecycle_status.value if lifecycle_status else "unknown",
        "degraded_services": (
            dict(lifecycle_state.degraded_services) if lifecycle_state else {}
        ),
        "failed_phase": (
            lifecycle_state.failed_phase.value
            if lifecycle_state and lifecycle_state.failed_phase
            else None
        ),
        "failure_reason": (
            lifecycle_state.failure_reason if lifecycle_state else None
        ),
        "phases": (
            [p.to_dict() for p in lifecycle_state.phase_reports]
            if lifecycle_state else []
        ),
    }
    return BaseSuccessDataResponse(data=data)


@router.get(
    "/version",
    tags=["Manage"],
    operation_id="get_version",
    summary="Get version",
    response_model=BaseSuccessDataResponse,
    include_in_schema=False,
)
async def api_version():
    return BaseSuccessDataResponse(
        data={
            "version": CONFIG.VERSION,
        }
    )


@router.get(
    "/caches",
    summary="Get caches schema",
    operation_id="get_model_schema",
    response_model=BaseSuccessDataResponse,
    tags=["Model"],
    include_in_schema=False,
)
async def api_get_caches(
    request: Request,
):
    return BaseSuccessDataResponse(
        data={
            "bundles": get_bundle_cache(),
            "plugins": get_plugin_cache(),
            "i18n": get_i18n_cache(),
        }
    )

@router.get(
    "/cache_checksums",
    tags=["Manage"],
    operation_id="get_cache_checksums",
    summary="Get Cache Checksums",
    response_model=BaseSuccessDataResponse,
    include_in_schema=False,
)
async def api_get_cache_checksums():
    return BaseSuccessDataResponse(
        data={
            "bundle_checksum": get_bundle_checksum(),
            "plugin_checksum": get_plugin_checksum(),
            "i18n_checksum": get_i18n_checksum(),
        }
    )
