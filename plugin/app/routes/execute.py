import logging
import re
from typing import Any, Dict, Union, Optional, List
from pydantic import BaseModel, Field, model_validator

from app.error import raise_http_error, ErrorCode, TKHttpException
from app.cache import get_plugin_handler, get_plugin
from app.models import (
    validate_bundle_credentials,
    BundleCredentials,
    PluginInput,
    PluginOutput,
    PluginHandler,
    Artifact,
    ArtifactType,
)

router = APIRouter()
logger = logging.getLogger(__name__)


IMAGE_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.bmp', '.tiff')
FILE_EXTENSIONS = ('.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.zip', '.tar', '.gz', '.csv', '.txt')

URL_PATTERN = re.compile(
    r'https?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
)


def detect_mime_type(url: str) -> str:
    """Detect MIME type based on URL extension."""
    lower_url = url.lower()
    if lower_url.endswith('.png'):
        return 'image/png'
    elif lower_url.endswith('.jpg') or lower_url.endswith('.jpeg'):
        return 'image/jpeg'
    elif lower_url.endswith('.gif'):
        return 'image/gif'
    elif lower_url.endswith('.webp'):
        return 'image/webp'
    elif lower_url.endswith('.svg'):
        return 'image/svg+xml'
    elif lower_url.endswith('.pdf'):
        return 'application/pdf'
    elif lower_url.endswith('.doc') or lower_url.endswith('.docx'):
        return 'application/msword'
    elif lower_url.endswith('.xls') or lower_url.endswith('.xlsx'):
        return 'application/vnd.ms-excel'
    elif lower_url.endswith('.csv'):
        return 'text/csv'
    elif lower_url.endswith('.txt'):
        return 'text/plain'
    elif lower_url.endswith('.zip'):
        return 'application/zip'
    return 'application/octet-stream'


def is_image_url(url: str) -> bool:
    """Check if URL points to an image."""
    if not isinstance(url, str):
        return False
    if not URL_PATTERN.match(url):
        return False
    lower_url = url.lower()
    return any(lower_url.endswith(ext) for ext in IMAGE_EXTENSIONS)


def is_file_url(url: str) -> bool:
    """Check if URL points to a file."""
    if not isinstance(url, str):
        return False
    if not URL_PATTERN.match(url):
        return False
    lower_url = url.lower()
    return any(lower_url.endswith(ext) for ext in FILE_EXTENSIONS)


def extract_urls_from_dict(data: Any, path: str = '') -> List[Dict]:
    """Recursively extract URLs from a dict."""
    urls = []
    if isinstance(data, dict):
        for key, value in data.items():
            current_path = f"{path}.{key}" if path else key
            if isinstance(value, str) and URL_PATTERN.match(value):
                urls.append({'url': value, 'key': key, 'path': current_path})
            elif isinstance(value, (dict, list)):
                urls.extend(extract_urls_from_dict(value, current_path))
    elif isinstance(data, list):
        for i, item in enumerate(data):
            current_path = f"{path}[{i}]"
            if isinstance(item, str) and URL_PATTERN.match(item):
                urls.append({'url': item, 'key': f'[{i}]', 'path': current_path})
            elif isinstance(item, (dict, list)):
                urls.extend(extract_urls_from_dict(item, current_path))
    return urls


def auto_convert_to_artifacts(data: Dict, existing_artifacts: List[Artifact]) -> List[Artifact]:
    """
    Automatically convert recognizable structures in data to artifacts.
    Only runs if the plugin didn't already return artifacts.
    """
    if existing_artifacts:
        return existing_artifacts
    
    artifacts: List[Artifact] = []
    
    # Strategy 1: Look for common image keys
    image_keys = ['image_url', 'url', 'image', 'img_url', 'picture_url', 'photo_url', 'preview_url', 'download_url']
    for key in image_keys:
        if key in data and is_image_url(data[key]):
            artifacts.append(
                Artifact(
                    type=ArtifactType.IMAGE,
                    mime_type=detect_mime_type(data[key]),
                    title=key.replace('_', ' ').title(),
                    preview_url=data[key],
                    download_url=data[key],
                )
            )
    
    # Strategy 2: Look for common file keys
    file_keys = ['file_url', 'file', 'download_url', 'attachment_url', 'pdf_url', 'document_url']
    for key in file_keys:
        if key in data and is_file_url(data[key]):
            artifacts.append(
                Artifact(
                    type=ArtifactType.FILE,
                    mime_type=detect_mime_type(data[key]),
                    title=key.replace('_', ' ').title(),
                    download_url=data[key],
                )
            )
    
    # Strategy 3: Look for results list (e.g., Pexels returns list of images)
    if 'results' in data and isinstance(data['results'], list) and len(data['results']) > 0:
        for i, item in enumerate(data['results'][:5]):  # Max 5 images to avoid clutter
            if isinstance(item, dict):
                # Try to find image in src dict (Pexels format)
                if 'src' in item and isinstance(item['src'], dict):
                    for size_key in ['large', 'original', 'medium', 'small']:
                        if size_key in item['src'] and is_image_url(item['src'][size_key]):
                            artifacts.append(
                                Artifact(
                                    type=ArtifactType.IMAGE,
                                    mime_type=detect_mime_type(item['src'][size_key]),
                                    title=f"Image {i+1}" + (f" - {item.get('photographer', '')}" if item.get('photographer') else ""),
                                    preview_url=item['src'][size_key],
                                    download_url=item['src']['original'] if 'original' in item['src'] else item['src'][size_key],
                                    metadata={'url': item.get('url'), 'photographer': item.get('photographer')}
                                )
                            )
                            break
                # Try direct url field
                elif 'url' in item and is_image_url(item['url']):
                    artifacts.append(
                        Artifact(
                            type=ArtifactType.IMAGE,
                            mime_type=detect_mime_type(item['url']),
                            title=f"Image {i+1}",
                            preview_url=item['url'],
                            download_url=item['url'],
                        )
                    )
    
    # Strategy 4: Look for tabular data
    if 'columns' in data and 'rows' in data:
        columns = data['columns']
        rows = data['rows']
        if isinstance(columns, list) and isinstance(rows, list) and len(columns) > 0 and len(rows) > 0:
            artifacts.append(
                Artifact(
                    type=ArtifactType.TABLE,
                    mime_type='application/json',
                    title='Table Data',
                    content={'columns': columns, 'rows': rows},
                )
            )
    
    # Strategy 5: Look for JSON data that is not URLs
    if not artifacts and len(data) > 0:
        # Check if data looks like structured JSON (not just URLs)
        has_complex_data = any(
            isinstance(v, (dict, list)) and not (isinstance(v, str) and URL_PATTERN.match(v))
            for v in data.values()
        )
        if has_complex_data:
            artifacts.append(
                Artifact(
                    type=ArtifactType.JSON,
                    mime_type='application/json',
                    title='Result Data',
                    content=data,
                )
            )
    
    return artifacts


class RunToolRequest(BaseModel):
    project_id: Optional[str] = Field(None, description="The project id.")

    bundle_id: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="The bundle id.",
        examples=["bundle_1"],
    )
    plugin_id: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="The plugin id.",
        examples=["plugin_1"],
    )
    input_params: Dict = Field(
        {},
        description="The input parameters of the plugin.",
        examples=[
            {
                "input_1": "value_1",
                "input_2": "value_2",
            }
        ],
    )
    credentials: BundleCredentials = Field(
        ...,
        description="The credentials of the model provider.",
        examples=[{"API_KEY": "YOUR_API_KEY"}],
    )

    @model_validator(mode="before")
    def validate_before(cls, data: Any):

        # validate bundle credentials
        credentials = validate_bundle_credentials(data)
        data["credentials"] = credentials
        data.pop("encrypted_credentials", None)

        return data

    @model_validator(mode="after")
    def validate_after(cls, data: Any):

        # validate plugin_id
        plugin = get_plugin(
            bundle_id=data.bundle_id,
            plugin_id=data.plugin_id,
        )

        if not plugin:
            raise_http_error(ErrorCode.OBJECT_NOT_FOUND, "Plugin not found")

        # validate input_params
        plugin.validate_input(data.input_params)

        return data


class RunToolResponse(BaseModel):
    status: str = Field(
        "success",
        Literal="success",
        description="The status of the response.",
    )
    data: PluginOutput = Field(
        ...,
        description="The data of the response.",
    )


class BaseDataResponse(BaseModel):
    status: str = Field("success", Literal="success", description="The status of the response.")
    data: Any = Field(...)


@router.post(
    "/execute",
    operation_id="execute_plugin",
    summary="Execute a plugin.",
    tags=["Plugin"],
    responses={422: {"description": "Unprocessable Entity"}},
    response_model=Union[RunToolResponse, BaseDataResponse],
)
async def api_execute(
    data: RunToolRequest,
):
    plugin: PluginHandler = get_plugin_handler(
        bundle_id=data.bundle_id,
        plugin_id=data.plugin_id,
    )
    if not plugin:
        raise_http_error(ErrorCode.OBJECT_NOT_FOUND, f"Plugin {data.plugin_id} not found")

    cleaned_dict = {k: v for k, v in data.input_params.items() if v is not None}
    data.input_params = cleaned_dict

    try:
        plugin_output = await plugin.execute(
            credentials=data.credentials,
            plugin_input=PluginInput(input_params=data.input_params, project_id=data.project_id),
        )
    except TKHttpException as e:
        logger.error(f"api_execute: {data.bundle_id}/{data.plugin_id}. Input params: {data.input_params}. Error: {e}")
        return BaseDataResponse(
            data={
                "status": e.status_code,
                "data": {
                    "error": e.detail.get("message", "Error when handling response from provider"),
                },
            }
        )
    except Exception as e:
        raise_http_error(ErrorCode.INTERNAL_SERVER_ERROR, str(e))

    # Auto-convert recognizable data structures to artifacts for backward compatibility
    if plugin_output.status == 200 and not plugin_output.artifacts:
        try:
            auto_artifacts = auto_convert_to_artifacts(plugin_output.data, plugin_output.artifacts)
            if auto_artifacts:
                plugin_output.artifacts = auto_artifacts
                logger.info(
                    f"api_execute: auto-converted {len(auto_artifacts)} artifacts for "
                    f"{data.bundle_id}/{data.plugin_id}"
                )
        except Exception as e:
            logger.warning(f"api_execute: auto-convert artifacts failed: {e}")

    return RunToolResponse(
        data=plugin_output,
    )
