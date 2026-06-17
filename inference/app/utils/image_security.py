import ipaddress
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import aiohttp

from app.error import ErrorCode, raise_http_error
from config import CONFIG

ALLOWED_REMOTE_SCHEMES = {"http", "https"}
LOCAL_HOSTNAMES = {"localhost", "0.0.0.0", "127.0.0.1", "::1"}
LOCAL_IMAGE_ROUTE_PREFIX = "/imgs/"
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30, connect=10)

__all__ = [
    "ALLOWED_REMOTE_SCHEMES",
    "LOCAL_HOSTNAMES",
    "LOCAL_IMAGE_ROUTE_PREFIX",
    "REQUEST_TIMEOUT",
    "is_private_ip",
    "image_url_is_on_localhost",
    "parse_local_image_path",
    "validate_remote_url",
    "resolve_imgs_path",
    "resolve_volume_path",
]


def is_private_ip(hostname: str) -> bool:
    try:
        ip = ipaddress.ip_address(hostname)
        return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
    except ValueError:
        return False


def _volume_base_dir() -> Path:
    return Path(CONFIG.PATH_TO_VOLUME).resolve()


def _imgs_base_dir() -> Path:
    return (_volume_base_dir() / "imgs").resolve()


def image_url_is_on_localhost(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except Exception:
        return False

    hostname = (parsed.hostname or "").lower()
    if hostname not in LOCAL_HOSTNAMES and not is_private_ip(hostname):
        return False

    if not parsed.path.startswith(LOCAL_IMAGE_ROUTE_PREFIX):
        raise_http_error(ErrorCode.PROVIDER_ERROR, "Invalid local image url.")

    return True


def parse_local_image_path(url: str) -> Path:
    parsed = urlparse(url)
    relative = parsed.path[len(LOCAL_IMAGE_ROUTE_PREFIX):]
    return resolve_imgs_path(relative)


def resolve_imgs_path(relative_path: str) -> Path:
    base = _imgs_base_dir()
    candidate = (base / relative_path.lstrip("/")).resolve()
    try:
        candidate.relative_to(base)
    except ValueError:
        raise_http_error(ErrorCode.PROVIDER_ERROR, "Invalid local image path.")
    return candidate


def resolve_volume_path(target_path: str) -> Path:
    base = _volume_base_dir()
    candidate = Path(target_path).resolve()
    try:
        candidate.relative_to(base)
    except ValueError:
        raise_http_error(ErrorCode.REQUEST_VALIDATION_ERROR, "Invalid file storage path.")
    return candidate


def validate_remote_url(url: str) -> None:
    try:
        parsed = urlparse(url)
    except Exception:
        raise_http_error(ErrorCode.PROVIDER_ERROR, "Invalid image url.")

    if parsed.scheme.lower() not in ALLOWED_REMOTE_SCHEMES:
        raise_http_error(ErrorCode.PROVIDER_ERROR, "Invalid image url scheme.")

    hostname = parsed.hostname or ""
    if hostname in LOCAL_HOSTNAMES or is_private_ip(hostname):
        raise_http_error(ErrorCode.PROVIDER_ERROR, "Invalid remote image host.")
