from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field
from app.models import Message

__all__ = [
    "MessageGenerateRequest",
    "MessageGenerateResponse",
]


class MessageGenerateRequest(BaseModel):
    system_prompt_variables: Dict[str, str] = Field(
        {},
        min_length=0,
        max_length=16,
        description="The variables that fit the system prompt template.",
        examples=[{"language": "English"}],
    )
    stream: bool = Field(
        False,
        description="Whether to return the assistant message in stream format. When this option is turned on, the response data will be returned in SSE format.",
        examples=[False],
    )
    debug: bool = Field(
        False,
        description="Whether to include trace debug information in the response. When stream=True, trace events are returned as SSE MessageGenerationLog events. When stream=False, trace events are returned in the 'trace' field of the JSON response.",
        examples=[False],
    )


class MessageGenerateResponse(BaseModel):
    status: str = Field("success", description="Response status, always 'success'.")
    data: Message = Field(..., description="The generated assistant message object.")
    trace: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="Structured trace events for debugging the generation process. "
                    "Only present when debug=True and stream=False. "
                    "Each event contains event type, status, duration, input summary, and error info if any.",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "status": "success",
                    "data": {
                        "object": "Message",
                        "message_id": "msg_xxx",
                        "assistant_id": "ast_xxx",
                        "chat_id": "chat_xxx",
                        "role": "assistant",
                        "content": {"text": "Hello!"}
                    },
                    "trace": [
                        {
                            "object": "MessageGenerationLog",
                            "session_id": "sess_xxx",
                            "event": "memory",
                            "event_id": "ev_xxx",
                            "event_step": "load",
                            "timestamp": 1718700000000,
                            "status": "success",
                            "duration_ms": 15,
                            "input_summary": "Load 5 memory messages"
                        }
                    ]
                }
            ]
        }
    }
