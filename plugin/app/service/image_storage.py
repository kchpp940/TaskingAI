import base64
import os
import string
import random

from aiohttp import ClientSession
import aioboto3

from app.error import raise_provider_api_error, raise_http_error, ErrorCode
from common.image_security import (
    REQUEST_TIMEOUT,
    resolve_volume_path,
    validate_remote_url,
)
from config import CONFIG

from datetime import datetime


def base62_encode(num):
    chars = string.ascii_uppercase + string.ascii_lowercase + string.digits
    result = []

    while num > 0:
        num, rem = divmod(num, 62)
        result.append(chars[rem])
    return "".join(reversed(result))


def get_base62_date():
    current_date = datetime.utcnow()
    date_str = current_date.strftime("%Y%m%d")
    date_int = int(date_str)
    base62_date = base62_encode(date_int)

    return base62_date


def generate_random_id(length):
    first_letter = string.ascii_uppercase + string.ascii_lowercase
    letters = string.ascii_uppercase + string.ascii_lowercase + string.digits
    return random.choice(first_letter) + "".join(random.choice(letters) for _ in range(length - 1))


def save_base64_image(image_data: str, file_format="png", specific_path=None):
    image_data = base64.b64decode(image_data)
    image_id = generate_random_id(16)
    if specific_path is None:
        target = f"{CONFIG.PATH_TO_VOLUME}/imgs/{image_id}.{file_format}"
    else:
        target = specific_path
    image_path = str(resolve_volume_path(target))

    directory = os.path.dirname(image_path)
    if not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)

    with open(image_path, "wb") as file:
        file.write(image_data)

    return image_path


async def save_url_image(image_url: str, file_format="png", specific_path=None):
    validate_remote_url(image_url)
    image_id = generate_random_id(16)
    if specific_path is None:
        target = f"{CONFIG.PATH_TO_VOLUME}/imgs/{image_id}.{file_format}"
    else:
        target = specific_path
    image_path = str(resolve_volume_path(target))

    directory = os.path.dirname(image_path)
    if not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)

    with open(image_path, "wb") as file:
        async with ClientSession(timeout=REQUEST_TIMEOUT) as session:
            async with session.get(image_url, proxy=CONFIG.PROXY) as response:
                response.raise_for_status()
                file.write(await response.read())

    return image_path


def delete_image(image_path: str):
    safe_path = str(resolve_volume_path(image_path))
    if os.path.exists(safe_path) and os.path.isfile(safe_path):
        os.remove(safe_path)


def generate_s3_path(project_id: str, file_format: str):
    file_category = "imgs/p/" if CONFIG.INCLUDE_FILE_CATEGORY_IN_STORAGE_PATH else ""
    return f"{file_category}{project_id}/{get_base62_date()}/pgIM{generate_random_id(8)}.{file_format}"


async def upload_local_image_to_s3_then_delete(
    local_image_path: str, s3_image_path: str, plugin_id: str, metadata: dict = None
):
    safe_local_path = str(resolve_volume_path(local_image_path))
    access_key_id = CONFIG.S3_ACCESS_KEY_ID
    access_key_secret = CONFIG.S3_ACCESS_KEY_SECRET
    endpoint = CONFIG.S3_ENDPOINT
    bucket_name = CONFIG.S3_IMAGE_BUCKET_NAME
    public_domain = CONFIG.S3_BUCKET_PUBLIC_DOMAIN if CONFIG.S3_BUCKET_PUBLIC_DOMAIN else f"{endpoint}/{bucket_name}"

    if metadata is None:
        metadata = {}

    session = aioboto3.Session(aws_access_key_id=access_key_id, aws_secret_access_key=access_key_secret)
    async with session.client("s3", endpoint_url=endpoint) as s3:
        try:
            with open(safe_local_path, "rb") as file:
                metadata.update({"plugin_id": plugin_id})
                await s3.upload_fileobj(
                    Fileobj=file, Bucket=bucket_name, Key=s3_image_path, ExtraArgs={"Metadata": metadata}
                )
            delete_image(safe_local_path)
            return f"{public_domain}/{s3_image_path}"
        except Exception as e:
            raise_provider_api_error(str(e))


async def upload_url_image_to_s3(
    image_url: str, project_id: str, file_format: str, plugin_id: str, metadata: dict = None
):
    if metadata is None:
        metadata = {}

    image_path = await save_url_image(image_url, file_format)
    s3_image_path = generate_s3_path(project_id, file_format)
    url = await upload_local_image_to_s3_then_delete(image_path, s3_image_path, plugin_id, metadata)

    return url


async def upload_base64_image_to_s3(
    base64_image_string: str, project_id: str, file_format: str, plugin_id: str, metadata: dict = None
):
    if metadata is None:
        metadata = {}

    image_path = save_base64_image(base64_image_string, file_format)
    s3_image_path = generate_s3_path(project_id, file_format)
    url = await upload_local_image_to_s3_then_delete(image_path, s3_image_path, plugin_id, metadata)

    return url


async def save_base64_image_to_s3_or_local(base64_image_string: str, project_id: str, file_format: str, plugin_id: str, metadata: dict = None):
    if CONFIG.OBJECT_STORAGE_TYPE == 's3':
        return await upload_base64_image_to_s3(base64_image_string, project_id, file_format, plugin_id, metadata)
    elif CONFIG.OBJECT_STORAGE_TYPE == 'local':
        generated_s3_path = generate_s3_path(project_id, file_format)
        specific_path = f"{CONFIG.PATH_TO_VOLUME}/{generated_s3_path}"
        save_base64_image(base64_image_string, file_format, specific_path)
        return f"{CONFIG.HOST_URL}/{generated_s3_path}"
    else:
        raise_http_error(ErrorCode.REQUEST_VALIDATION_ERROR, "No image storage service available")


async def save_url_image_to_s3_or_local(image_url: str, project_id: str, file_format: str, plugin_id: str, metadata: dict = None):
    if CONFIG.OBJECT_STORAGE_TYPE == 's3':
        return await upload_url_image_to_s3(image_url, project_id, file_format, plugin_id, metadata)
    elif CONFIG.OBJECT_STORAGE_TYPE == 'local':
        generated_s3_path = generate_s3_path(project_id, file_format)
        specific_path = f"{CONFIG.PATH_TO_VOLUME}/{generated_s3_path}"
        await save_url_image(image_url, file_format, specific_path)
        return f"{CONFIG.HOST_URL}/{generated_s3_path}"
    else:
        raise_http_error(ErrorCode.REQUEST_VALIDATION_ERROR, "No image storage service available")
