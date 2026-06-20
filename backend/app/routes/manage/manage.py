from fastapi import APIRouter, HTTPException, Request
from tkhelper.schemas.base import BaseEmptyResponse, BaseDataResponse
from app.config import CONFIG
from app.services.auth.admin import create_default_admin_if_needed
import logging

logger = logging.Logger(__name__)

router = APIRouter()


@router.get(
    "/health_check",
    tags=["Manage"],
    operation_id="health_check",
    summary="Health check",
    response_model=BaseDataResponse,
)
async def api_health_check(request: Request):
    from app.database import redis_conn, postgres_pool

    lifecycle = getattr(request.app.state, "lifecycle", None)
    lifecycle_state = getattr(request.app.state, "lifecycle_state", None)
    lifecycle_status = getattr(request.app.state, "lifecycle_status", None)

    infra_errors = []
    if not await redis_conn.health_check():
        infra_errors.append("Redis health check failed.")
    if not await postgres_pool.health_check():
        infra_errors.append("Postgres health check failed.")

    overall_status = lifecycle_status.value if lifecycle_status else "unknown"
    degraded = {}
    failed_phase = None
    failure_reason = None

    if lifecycle_state:
        degraded = dict(lifecycle_state.degraded_services)
        failed_phase = lifecycle_state.failed_phase.value if lifecycle_state.failed_phase else None
        failure_reason = lifecycle_state.failure_reason
        if lifecycle_state.status.value == "degraded" and infra_errors:
            overall_status = "degraded"
        if infra_errors:
            failure_reason = (failure_reason or "") + ("; " if failure_reason else "") + "; ".join(infra_errors)

    if infra_errors and lifecycle_status and lifecycle_status.value != "degraded":
        raise HTTPException(status_code=500, detail="; ".join(infra_errors))

    return BaseDataResponse(
        data={
            "status": overall_status,
            "degraded_services": degraded,
            "failed_phase": failed_phase,
            "failure_reason": failure_reason,
            "phases": (
                [p.to_dict() for p in lifecycle_state.phase_reports]
                if lifecycle_state else []
            ),
        }
    )


@router.get(
    "/version",
    tags=["Manage"],
    operation_id="get_version",
    summary="Get application version",
    response_model=BaseDataResponse,
)
async def api_version():
    return BaseDataResponse(
        data={
            "version": CONFIG.VERSION,
            "postgres_schema_version": CONFIG.POSTGRES_SCHEMA_VERSION,
        }
    )


if CONFIG.WEB and (CONFIG.TEST or CONFIG.DEV):
    from app.database import redis_conn, postgres_pool

    @router.post(
        "/clean_data",
        tags=["Manage"],
        operation_id="clean_data",
        summary="Clean application version",
        response_model=BaseEmptyResponse,
    )
    async def api_clean_data():
        await redis_conn.clean_data()
        await postgres_pool.clean_data()
        await create_default_admin_if_needed()

        return BaseEmptyResponse()
