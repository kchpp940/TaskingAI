from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


__all__ = ["TraceEventType", "TraceEventStatus", "TraceEvent"]


class TraceEventType(str, Enum):
    MEMORY_BUILD = "memory_build"
    SYSTEM_PROMPT_BUILD = "system_prompt_build"
    RETRIEVAL = "retrieval"
    TOOL_CALL = "tool_call"
    INFERENCE = "inference"
    CHAT_COMPLETION = "chat_completion"
    USAGE_SUMMARY = "usage_summary"


class TraceEventStatus(str, Enum):
    STARTED = "started"
    COMPLETED = "completed"
    ERROR = "error"


class TraceEvent(BaseModel):
    """
    Stable schema for generation trace events.
    Emitted by both normal and streaming generation paths.
    Frontend consumes only this structure for trace visualization.
    """

    object: str = Field(
        "TraceEvent",
        Literal="TraceEvent",
        description="The object type, always `TraceEvent`.",
    )
    trace_id: str = Field(
        ...,
        min_length=24,
        max_length=24,
        description="The unique ID for the entire generation trace.",
    )
    event_id: str = Field(
        ...,
        min_length=24,
        max_length=24,
        description="The unique ID for this specific event.",
    )
    event_type: TraceEventType = Field(
        ...,
        description="The type of trace event.",
    )
    status: TraceEventStatus = Field(
        ...,
        description="Status of the event: started, completed, or error.",
    )
    timestamp: int = Field(
        ...,
        ge=0,
        description="Unix timestamp in milliseconds when the event started.",
        example=1700000000000,
    )
    duration_ms: Optional[int] = Field(
        None,
        description="Duration of the event in milliseconds. Only present when status is completed or error.",
        ge=0,
    )
    content: Dict[str, Any] = Field(
        default_factory=dict,
        description="Structured content for the event. Schema varies by event_type but is stable for each type.",
    )
    error: Optional[str] = Field(
        None,
        description="Error message. Only present when status is error.",
    )

    class Config:
        use_enum_values = True

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump(exclude_none=True)
