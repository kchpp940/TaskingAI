from pydantic import BaseModel, Field
from typing import Dict, Union, List, Any, Optional
from enum import Enum
import json

__all__ = ["ToolType", "ToolRef", "Tool", "ToolInput", "ToolOutput", "ArtifactType", "Artifact"]


class ToolType(str, Enum):
    ACTION = "action"
    PLUGIN = "plugin"


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


class ToolRef(BaseModel):
    type: ToolType = Field(..., description="The tool type.")
    id: str = Field(..., description="The tool ID.")


class Tool(BaseModel):
    tool_id: str = Field(
        ...,
        description="The tool ID.",
        examples=["action_1"],
    )

    type: ToolType = Field(
        ...,
        description="The tool type, which can be `action`, `plugin` or `function`.",
        examples=["action", "plugin", "function"],
    )

    function_def: Dict = Field(
        ...,
        description="The function definition for chat completion function-call.",
    )

    def function_name(self):
        return self.function_def["name"]


class ToolInput(BaseModel):
    type: ToolType = Field(
        ...,
        description="The tool type, which can be `function` or `action`.",
        examples=["action", "plugin"],
    )

    tool_id: str = Field(
        ...,
        description="The tool ID.",
        examples=["action_1"],
    )

    tool_call_id: str = Field(
        ...,
        description="The tool call ID.",
        examples=["call_1"],
    )

    arguments: Dict = Field(
        ...,
        description="The tool input arguments.",
    )


class ToolOutput(BaseModel):
    type: ToolType = Field(
        ...,
        description="The tool type, which can be `function` or `action`.",
        examples=["action", "plugin"],
    )

    tool_id: str = Field(
        ...,
        description="The tool ID.",
        examples=["action_1"],
    )

    tool_call_id: str = Field(
        ...,
        description="The tool call ID.",
        examples=["call_1"],
    )

    status: int = Field(
        ...,
        description="The tool output status.",
        examples=[200, 400, 500],
    )

    data: Union[Dict, List] = Field(
        ...,
        description="The tool output data.",
    )

    artifacts: List[Artifact] = Field(
        [],
        description="List of artifacts produced by the tool.",
    )

    def to_function_message(self):
        if self.status == 200:
            return {
                "role": "function",
                "content": json.dumps(self.data),
                "id": self.tool_call_id,
            }
        else:
            return {
                "role": "function",
                "content": json.dumps({"status": self.status, "error": self.data}),
                "id": self.tool_call_id,
            }
