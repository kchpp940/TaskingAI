from starlette.responses import FileResponse, Response, RedirectResponse

from fastapi import APIRouter, Request, Query
from app.error import ErrorCode, raise_http_error
import os
from typing import Optional
from app.cache import get_bundle, get_default_artifact_cache, ArtifactCacheEntry
from config import CONFIG

router = APIRouter()


async def _resolve_artifact_storage_path(
    artifact_id: str,
    plugin_id: str,
    artifact_type: str = "image",
) -> ArtifactCacheEntry:
    """
    Look up artifact via ArtifactCache and renew its TTL on access.
    Raises HTTP 404 if not cached or storage_key is missing.
    """
    cache = get_default_artifact_cache()
    entry = await cache.get(artifact_id=artifact_id, plugin_id=plugin_id, artifact_type=artifact_type)
    if not entry or not entry.storage_key:
        raise_http_error(
            ErrorCode.OBJECT_NOT_FOUND,
            message=f"Artifact {artifact_id} not found or expired.",
        )
    return entry


@router.get(
    "/plugins/artifacts/{plugin_id}/{artifact_type}/{artifact_id}",
    tags=["Plugin"],
    summary="Get Artifact (cached reference)",
    operation_id="get_artifact",
    responses={422: {"description": "Unprocessable Entity"}},
)
async def api_get_artifact(
    plugin_id: str,
    artifact_type: str,
    artifact_id: str,
    redirect: Optional[bool] = Query(True, description="Redirect to storage URL for S3, or return file for local"),
    request: Request = None,
):
    entry = await _resolve_artifact_storage_path(artifact_id, plugin_id, artifact_type)

    if entry.storage_provider == "s3":
        endpoint = CONFIG.S3_ENDPOINT
        bucket_name = CONFIG.S3_IMAGE_BUCKET_NAME
        public_domain = CONFIG.S3_BUCKET_PUBLIC_DOMAIN if CONFIG.S3_BUCKET_PUBLIC_DOMAIN else f"{endpoint}/{bucket_name}"
        url = f"{public_domain}/{entry.storage_key}"
        if redirect:
            return RedirectResponse(url=url)
        return Response(content=url, media_type="text/plain")

    elif entry.storage_provider == "local":
        local_path = os.path.join(CONFIG.PATH_TO_VOLUME, entry.storage_key)
        if not os.path.exists(local_path):
            raise_http_error(
                ErrorCode.OBJECT_NOT_FOUND,
                message=f"Artifact {artifact_id} file missing.",
            )
        ext = os.path.splitext(entry.storage_key)[1].lstrip(".") or "png"
        media_type = f"image/{ext}" if ext in ("png", "jpg", "jpeg", "gif", "webp", "svg") else "application/octet-stream"
        return FileResponse(
            path=local_path,
            headers={"Content-Disposition": "inline"},
            media_type=media_type,
            filename=f"{artifact_id}.{ext}",
        )
    else:
        raise_http_error(
            ErrorCode.INTERNAL_SERVER_ERROR,
            message=f"Unknown storage provider: {entry.storage_provider}",
        )


@router.get(
    "/plugins/artifacts/{plugin_id}/{artifact_type}/{artifact_id}/renew",
    tags=["Plugin"],
    summary="Renew Artifact TTL",
    operation_id="renew_artifact",
    responses={422: {"description": "Unprocessable Entity"}},
)
async def api_renew_artifact(
    plugin_id: str,
    artifact_type: str,
    artifact_id: str,
    ttl: Optional[int] = Query(None, description="TTL in seconds, defaults to artifact cache default"),
):
    cache = get_default_artifact_cache()
    ok = await cache.renew(artifact_id=artifact_id, plugin_id=plugin_id, artifact_type=artifact_type, ttl=ttl)
    if not ok:
        raise_http_error(
            ErrorCode.OBJECT_NOT_FOUND,
            message=f"Artifact {artifact_id} not found or cannot be renewed.",
        )
    return {"artifact_id": artifact_id, "renewed": True, "ttl": ttl}


@router.get(
    "/plugins/bundles/icons/{bundle_id}.png",
    tags=["Plugin"],
    summary="Get bundle Icon File",
    operation_id="get_bundle_icon",
    responses={422: {"description": "Unprocessable Entity"}},
)
async def api_get_bundle_icon(
        bundle_id: str,
        request: Request,
):
    bundle = get_bundle(bundle_id)
    if not bundle:
        raise_http_error(
            ErrorCode.OBJECT_NOT_FOUND,
            message=f"bundle {bundle_id} not found.",
        )

    current_path = os.path.dirname(os.path.abspath(__file__))
    png_file_path = f"../../bundles/{bundle_id}/resources/icon.png"
    abs_png_file_path = os.path.join(current_path, png_file_path)

    return FileResponse(
        path=abs_png_file_path,
        headers={"Content-Disposition": "inline"},
        media_type="image/png",
        filename=f"{bundle_id}.png",
    )
