import base64
from io import BytesIO

import aiohttp

from app.error import raise_provider_api_error
from app.utils.image_security import (
    REQUEST_TIMEOUT,
    image_url_is_on_localhost,
    parse_local_image_path,
    validate_remote_url,
)
from config import CONFIG

__all__ = [
    "image_url_is_on_localhost",
    "fetch_image_format",
    "get_image_base64_string",
]

from PIL import Image


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
            return image.format


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
