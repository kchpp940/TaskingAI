import time

import aiohttp
import json
import hashlib
import re
from typing import List

import base64
from io import BytesIO
from PIL import Image

from app.error import ErrorCode, raise_http_error, raise_provider_api_error
from common.image_security import (
    REQUEST_TIMEOUT,
    image_url_is_on_localhost,
    parse_local_image_path,
    validate_remote_url,
)
from config import CONFIG

__all__ = [
    "get_current_timestamp_int",
    "checksum",
    "is_valid_data_uri",
    "check_valid_list_content",
    "split_url",
    "build_url",
    "image_url_is_on_localhost",
    "fetch_image_format",
    "get_image_base64_string",
]


def get_current_timestamp_int():
    return int(time.time() * 1000)


def checksum(data) -> str:
    """
    Returns the SHA256 checksum of the given data.

    :param data: The data to checksum.
    :return: The SHA256 checksum of the given data.
    """
    data_str = json.dumps(data, sort_keys=True)
    hash_object = hashlib.sha256()
    hash_object.update(data_str.encode())
    return hash_object.hexdigest()


def is_valid_data_uri(uri: str) -> bool:
    pattern = r"^data:image\/(jpg|png|jpeg);base64,([A-Za-z0-9+/]{4})*([A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$"
    match = re.match(pattern, uri)
    return match is not None


def check_valid_list_content(content: List):
    for c in content:
        if c.type == "image_url":
            if not is_valid_data_uri(c.image_url.url):
                raise_http_error(
                    ErrorCode.REQUEST_VALIDATION_ERROR,
                    message="Invalid image URL. Only jpg, jpeg, "
                    "and png in base64 format with proper prefix "
                    "are supported.",
                )


def split_url(url: str) -> tuple:
    format_and_encoding = url[len("data:image/") :].split(";base64,")
    if len(format_and_encoding) == 2:
        image_format = format_and_encoding[0]
        encoding_content = format_and_encoding[1]
        return image_format, encoding_content
    else:
        raise_http_error(
            ErrorCode.REQUEST_VALIDATION_ERROR,
            message="Prefix error. The url prefix should be like: 'data:image/xxx;base64,'.",
        )


def build_url(base_url, path):
    try:
        if base_url.endswith("/"):
            base_url = base_url[:-1]
        if not path.startswith("/"):
            path = "/" + path
        return base_url + path
    except Exception as e:
        raise_http_error(
            ErrorCode.REQUEST_VALIDATION_ERROR,
            message=f"Failed to build url: {e}",
        )


async def fetch_image_format(url):
    if image_url_is_on_localhost(url):
        local_file_path = parse_local_image_path(url)
        with open(local_file_path, "rb") as image_file:
            image_bytes = image_file.read()
            image = Image.open(BytesIO(image_bytes))
            return image.format

    validate_remote_url(url)
    async with aiohttp.ClientSession(timeout=REQUEST_TIMEOUT) as session:
        async with session.get(url, proxy=CONFIG.PROXY) as response:
            response.raise_for_status()
            image_bytes = await response.read()
            image = Image.open(BytesIO(image_bytes))
            return image.format.lower()


async def get_image_base64_string(image_uri):
    if image_url_is_on_localhost(image_uri):
        local_file_path = parse_local_image_path(image_uri)

        with open(local_file_path, "rb") as image_file:
            image_bytes = image_file.read()
            base64_string = base64.b64encode(image_bytes).decode("utf-8")
            return base64_string

    validate_remote_url(image_uri)
    async with aiohttp.ClientSession(timeout=REQUEST_TIMEOUT) as session:
        async with session.get(url=image_uri, proxy=CONFIG.PROXY) as response:
            if response.status == 200:
                image_bytes = await response.read()
                base64_string = base64.b64encode(image_bytes).decode("utf-8")
                return base64_string
            else:
                raise_provider_api_error(f"Failed to fetch image from {image_uri}")
