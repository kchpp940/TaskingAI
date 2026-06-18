from abc import ABC, abstractmethod
from typing import Dict, Optional, List, Any, Union
from app.models import BundleCredentials
from pydantic import BaseModel, Field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ArtifactType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    FILE = "file"
    JSON = "json"
    TABLE = "table"


class Artifact(BaseModel):
    type: ArtifactType = Field(..., description="The type of the artifact.")
    mime_type: str = Field("text/plain", description="The MIME type of the artifact.")
    title: Optional[str] = Field(None, description="The title or name of the artifact.")
    content: Optional[Any] = Field(None, description="The inline content of the artifact, for text/json/table types.")
    preview_url: Optional[str] = Field(None, description="The URL for previewing the artifact.")
    download_url: Optional[str] = Field(None, description="The URL for downloading the artifact.")
    size: Optional[int] = Field(None, description="The size of the artifact in bytes.")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata for the artifact.")


class PluginOutput(BaseModel):
    status: int = Field(200)
    data: Dict = Field({})
    artifacts: List[Artifact] = Field([], description="List of artifacts produced by the plugin.")


class PluginInput(BaseModel):
    input_params: Dict = Field(...)
    project_id: Optional[str] = Field(None)


class PluginHandler(ABC):
    def __init__(self):
        pass

    @abstractmethod
    async def execute(
        self,
        credentials: BundleCredentials,
        plugin_input: PluginInput,
    ) -> PluginOutput:
        raise NotImplementedError
