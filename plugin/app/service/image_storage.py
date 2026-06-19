import base64
import os
import string
import random
import hashlib
import logging
from typing import Optional, Tuple, Any

from aiohttp import ClientSession
import aioboto3

from app.error import raise_provider_api_error, raise_http_error, ErrorCode
from app.cache import ArtifactCacheEntry, get_default_artifact_cache
from config import CONFIG

from datetime import datetime

logger = logging.getLogger(__name__)


class StorageResult(Tuple):
    """
    Backward-compatible storage result.
    Can be used as:
      url = save_base64_image_to_s3_or_local(...)  # old API
      url, entry = save_base64_image_to_s3_or_local(...)  # new API
    """
    def __new__(cls, url: str, entry: ArtifactCacheEntry):
        return tuple.__new__(cls, (url, entry))

    @property
    def url(self) -> str:
        return self[0]

    @property
    def artifact_entry(self) -> ArtifactCacheEntry:
        return self[1]

    def __str__(self) -> str:
        return self[0]


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
    image_path = f"{CONFIG.PATH_TO_VOLUME}/{image_id}.{file_format}" if specific_path is None else specific_path

    directory = os.path.dirname(image_path)
    if not os.path.exists(directory):
        os.makedirs(directory)

    with open(image_path, "wb") as file:
        file.write(image_data)

    return image_path

async def save_url_image(image_url: str, file_format="png", specific_path=None):
    image_id = generate_random_id(16)
    image_path = f"{CONFIG.PATH_TO_VOLUME}/{image_id}.{file_format}" if specific_path is None else specific_path

    directory = os.path.dirname(image_path)
    if not os.path.exists(directory):
        os.makedirs(directory)

    with open(image_path, "wb") as file:
        async with ClientSession() as session:
            async with session.get(image_url) as response:
                file.write(await response.read())

    return image_path


def delete_image(image_path: str):
    if os.path.exists(image_path):
        os.remove(image_path)


def generate_s3_path(project_id: str, file_format: str):
    file_category = "imgs/p/" if CONFIG.INCLUDE_FILE_CATEGORY_IN_STORAGE_PATH else ""
    return f"{file_category}{project_id}/{get_base62_date()}/pgIM{generate_random_id(8)}.{file_format}"


async def _register_artifact(
    storage_key: str,
    storage_provider: str,
    plugin_id: str,
    artifact_type: str,
    size: int,
    content_hash: str = "",
    metadata: Optional[dict] = None,
) -> ArtifactCacheEntry:
    """
    Register a stored artifact in ArtifactCache with its TTL policy.
    Returns the created ArtifactCacheEntry.
    """
    cache = get_default_artifact_cache()
    entry = await cache.create(
        plugin_id=plugin_id,
        artifact_type=artifact_type,
        storage_key=storage_key,
        storage_provider=storage_provider,
        metadata=metadata or {},
        size=size,
        content_hash=content_hash,
    )
    logger.info(
        f"Artifact registered: artifact_id={entry.artifact_id}, "
        f"plugin_id={plugin_id}, storage_provider={storage_provider}, size={size}"
    )
    return entry


async def upload_local_image_to_s3_then_delete(
    local_image_path: str, s3_image_path: str, plugin_id: str, metadata: dict = None
) -> StorageResult:
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
            file_size = os.path.getsize(local_image_path)

            with open(local_image_path, "rb") as file:
                metadata.update({"plugin_id": plugin_id})
                await s3.upload_fileobj(
                    Fileobj=file, Bucket=bucket_name, Key=s3_image_path, ExtraArgs={"Metadata": metadata}
                )

            entry = await _register_artifact(
                storage_key=s3_image_path,
                storage_provider="s3",
                plugin_id=plugin_id,
                artifact_type="image",
                size=file_size,
                metadata=metadata,
            )

            delete_image(local_image_path)
            public_url = f"{public_domain}/{s3_image_path}"
            return StorageResult(public_url, entry)
        except Exception as e:
            raise_provider_api_error(str(e))


async def upload_url_image_to_s3(
    image_url: str, project_id: str, file_format: str, plugin_id: str, metadata: dict = None
) -> StorageResult:
    if metadata is None:
        metadata = {}

    image_path = await save_url_image(image_url, file_format)
    s3_image_path = generate_s3_path(project_id, file_format)
    return await upload_local_image_to_s3_then_delete(image_path, s3_image_path, plugin_id, metadata)


async def upload_base64_image_to_s3(
    base64_image_string: str, project_id: str, file_format: str, plugin_id: str, metadata: dict = None
) -> StorageResult:
    if metadata is None:
        metadata = {}

    image_path = save_base64_image(base64_image_string, file_format)
    s3_image_path = generate_s3_path(project_id, file_format)
    return await upload_local_image_to_s3_then_delete(image_path, s3_image_path, plugin_id, metadata)

async def save_base64_image_to_s3_or_local(base64_image_string: str, project_id: str, file_format: str, plugin_id: str, metadata: dict = None) -> StorageResult:
    if CONFIG.OBJECT_STORAGE_TYPE == 's3':
        return await upload_base64_image_to_s3(base64_image_string, project_id, file_format, plugin_id, metadata)
    elif CONFIG.OBJECT_STORAGE_TYPE == 'local':
        generated_s3_path = generate_s3_path(project_id, file_format)
        specific_path = f"{CONFIG.PATH_TO_VOLUME}/{generated_s3_path}"
        image_path = save_base64_image(base64_image_string, file_format, specific_path)

        content_hash = hashlib.sha256(base64_image_string.encode("utf-8")).hexdigest()[:32]
        entry = await _register_artifact(
            storage_key=generated_s3_path,
            storage_provider="local",
            plugin_id=plugin_id,
            artifact_type="image",
            size=os.path.getsize(image_path),
            content_hash=content_hash,
            metadata=metadata or {},
        )
        public_url = f"{CONFIG.HOST_URL}/{generated_s3_path}"
        return StorageResult(public_url, entry)
    else:
        raise_http_error(ErrorCode.REQUEST_VALIDATION_ERROR,"No image storage service available")

async def save_url_image_to_s3_or_local(image_url: str, project_id: str, file_format: str, plugin_id: str, metadata: dict = None) -> StorageResult:
    if CONFIG.OBJECT_STORAGE_TYPE == 's3':
        return await upload_url_image_to_s3(image_url, project_id, file_format, plugin_id, metadata)
    elif CONFIG.OBJECT_STORAGE_TYPE == 'local':
        generated_s3_path = generate_s3_path(project_id, file_format)
        specific_path = f"{CONFIG.PATH_TO_VOLUME}/{generated_s3_path}"
        image_path = await save_url_image(image_url, file_format, specific_path)

        content_hash = hashlib.sha256(image_url.encode("utf-8")).hexdigest()[:32]
        entry = await _register_artifact(
            storage_key=generated_s3_path,
            storage_provider="local",
            plugin_id=plugin_id,
            artifact_type="image",
            size=os.path.getsize(image_path),
            content_hash=content_hash,
            metadata=metadata or {},
        )
        public_url = f"{CONFIG.HOST_URL}/{generated_s3_path}"
        return StorageResult(public_url, entry)
    else:
        raise_http_error(ErrorCode.REQUEST_VALIDATION_ERROR,"No image storage service available")