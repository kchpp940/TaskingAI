import ipaddress
from pathlib import Path
from urllib.parse import urlparse

import aiohttp

ALLOWED_REMOTE_SCHEMES = {"http", "https"}
LOCAL_HOSTNAMES = {"localhost", "0.0.0.0", "127.0.0.1", "::1"}
LOCAL_IMAGE_ROUTE_PREFIX = "/imgs/"
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30, connect=10)

_config = {
    "path_to_volume": None,
    "raise_http_error": None,
    "error_code_provider": None,
    "error_code_validation": None,
}

__all__ = [
    "ALLOWED_REMOTE_SCHEMES",
    "LOCAL_HOSTNAMES",
    "LOCAL_IMAGE_ROUTE_PREFIX",
    "REQUEST_TIMEOUT",
    "init_config",
    "is_private_ip",
    "image_url_is_on_localhost",
    "parse_local_image_path",
    "validate_remote_url",
    "resolve_imgs_path",
    "resolve_volume_path",
]


def init_config(
    path_to_volume: str,
    raise_http_error,
    error_code_provider_error,
    error_code_request_validation_error,
):
    _config["path_to_volume"] = path_to_volume
    _config["raise_http_error"] = raise_http_error
    _config["error_code_provider"] = error_code_provider_error
    _config["error_code_validation"] = error_code_request_validation_error


def _get_path_to_volume() -> str:
    if _config["path_to_volume"] is None:
        raise RuntimeError("image_security not initialized. Call init_config() first.")
    return _config["path_to_volume"]


def _raise_provider_error(message: str):
    if _config["raise_http_error"] is None or _config["error_code_provider"] is None:
        raise RuntimeError("image_security not initialized. Call init_config() first.")
    _config["raise_http_error"](_config["error_code_provider"], message)


def _raise_validation_error(message: str):
    if _config["raise_http_error"] is None or _config["error_code_validation"] is None:
        raise RuntimeError("image_security not initialized. Call init_config() first.")
    _config["raise_http_error"](_config["error_code_validation"], message)


def is_private_ip(hostname: str) -> bool:
    try:
        ip = ipaddress.ip_address(hostname)
        return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
    except ValueError:
        return False


def _volume_base_dir() -> Path:
    return Path(_get_path_to_volume()).resolve()


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
        _raise_provider_error("Invalid local image url.")

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
        _raise_provider_error("Invalid local image path.")
    return candidate


def resolve_volume_path(target_path: str) -> Path:
    base = _volume_base_dir()
    candidate = Path(target_path).resolve()
    try:
        candidate.relative_to(base)
    except ValueError:
        _raise_validation_error("Invalid file storage path.")
    return candidate


def validate_remote_url(url: str) -> None:
    try:
        parsed = urlparse(url)
    except Exception:
        _raise_provider_error("Invalid image url.")
        return

    if parsed.scheme.lower() not in ALLOWED_REMOTE_SCHEMES:
        _raise_provider_error("Invalid image url scheme.")
        return

    hostname = parsed.hostname or ""
    if hostname in LOCAL_HOSTNAMES or is_private_ip(hostname):
        _raise_provider_error("Invalid remote image host.")
        return
