from typing import Any, Dict, List, Optional
from tkhelper.utils import current_timestamp_int_milliseconds

from app.models import (
    MessageGenerationLog,
    Model,
    RetrievalResult,
    ToolInput,
    ToolOutput,
    TraceEvent,
    TraceEventType,
    TraceEventStatus,
)

__all__ = [
    # ---- Legacy MessageGenerationLog builders (for backward compatibility) ----
    "build_retrieval_input_log_dict",
    "build_retrieval_output_log_dict",
    "build_tool_input_log_dict",
    "build_tool_output_log_dict",
    "build_chat_completion_input_log_dict",
    "build_chat_completion_output_log_dict",
    # ---- New TraceEvent builders (stable, for frontend consumption) ----
    "build_trace_event",
    "build_trace_memory_build",
    "build_trace_system_prompt_build",
    "build_trace_retrieval_start",
    "build_trace_retrieval_complete",
    "build_trace_retrieval_error",
    "build_trace_tool_start",
    "build_trace_tool_complete",
    "build_trace_tool_error",
    "build_trace_inference_start",
    "build_trace_inference_complete",
    "build_trace_inference_error",
    "build_trace_chat_completion_start",
    "build_trace_chat_completion_complete",
    "build_trace_chat_completion_error",
    "build_trace_usage_summary",
]


# ==========================================================================
# Legacy MessageGenerationLog builders (unchanged, for debug log storage)
# ==========================================================================

def build_retrieval_input_log_dict(
    session_id: str,
    event_id: str,
    query_text: str,
    top_k: int,
    duration_ms: Optional[int] = None,
    status: str = "started",
):
    return MessageGenerationLog(
        session_id=session_id,
        event="retrieval",
        event_id=event_id,
        event_step="input",
        timestamp=current_timestamp_int_milliseconds(),
        content={
            "query_text": query_text,
            "top_k": top_k,
        },
        status=status,
        duration_ms=duration_ms,
    ).model_dump(exclude_none=True)


def build_retrieval_output_log_dict(
    session_id: str,
    event_id: str,
    retrieval_result: List[RetrievalResult],
    duration_ms: Optional[int] = None,
    status: str = "completed",
    error: Optional[str] = None,
):
    return MessageGenerationLog(
        session_id=session_id,
        event="retrieval",
        event_id=event_id,
        event_step="output",
        timestamp=current_timestamp_int_milliseconds(),
        content={
            "result": retrieval_result,
        },
        status=status,
        duration_ms=duration_ms,
        error=error,
    ).model_dump(exclude_none=True)


def build_tool_input_log_dict(
    session_id: str,
    event_id: str,
    tool_input: ToolInput,
    duration_ms: Optional[int] = None,
    status: str = "started",
):
    return MessageGenerationLog(
        session_id=session_id,
        event="tool",
        event_id=event_id,
        event_step="input",
        timestamp=current_timestamp_int_milliseconds(),
        content=tool_input.model_dump(),
        status=status,
        duration_ms=duration_ms,
    ).model_dump(exclude_none=True)


def build_tool_output_log_dict(
    session_id: str,
    event_id: str,
    tool_output: ToolOutput,
    duration_ms: Optional[int] = None,
    status: str = "completed",
    error: Optional[str] = None,
):
    return MessageGenerationLog(
        session_id=session_id,
        event="tool",
        event_id=event_id,
        event_step="output",
        timestamp=current_timestamp_int_milliseconds(),
        content=tool_output.model_dump(),
        status=status,
        duration_ms=duration_ms,
        error=error,
    ).model_dump(exclude_none=True)


def build_chat_completion_input_log_dict(
    session_id: str,
    event_id: str,
    model: Model,
    messages: List[Dict],
    functions: List[Dict],
    duration_ms: Optional[int] = None,
    status: str = "started",
):
    log = MessageGenerationLog(
        session_id=session_id,
        event="chat_completion",
        event_id=event_id,
        event_step="input",
        timestamp=current_timestamp_int_milliseconds(),
        content={
            "model_id": model.model_id,
            "model_schema_id": model.model_schema_id,
            "provider_model_id": model.provider_model_id,
            "messages": messages,
            "functions": functions,
        },
        status=status,
        duration_ms=duration_ms,
    )
    return log.model_dump(exclude_none=True)


def build_chat_completion_output_log_dict(
    session_id: str,
    event_id: str,
    model: Model,
    message: Dict,
    usage: Dict,
    duration_ms: Optional[int] = None,
    status: str = "completed",
    error: Optional[str] = None,
):
    return MessageGenerationLog(
        session_id=session_id,
        event="chat_completion",
        event_id=event_id,
        event_step="output",
        timestamp=current_timestamp_int_milliseconds(),
        content={
            "model_id": model.model_id,
            "model_schema_id": model.model_schema_id,
            "provider_model_id": model.provider_model_id,
            "message": message,
            "usage": usage,
        },
        status=status,
        duration_ms=duration_ms,
        error=error,
    ).model_dump(exclude_none=True)


# ==========================================================================
# Stable TraceEvent builders (frontend consumption)
# ==========================================================================

def build_trace_event(
    trace_id: str,
    event_id: str,
    event_type: TraceEventType,
    status: TraceEventStatus,
    content: Dict[str, Any],
    duration_ms: Optional[int] = None,
    error: Optional[str] = None,
) -> TraceEvent:
    """Generic TraceEvent builder with stable schema."""
    return TraceEvent(
        trace_id=trace_id,
        event_id=event_id,
        event_type=event_type,
        status=status,
        timestamp=current_timestamp_int_milliseconds(),
        duration_ms=duration_ms,
        content=content,
        error=error,
    )


def build_trace_memory_build(
    trace_id: str,
    event_id: str,
    num_messages: int,
    duration_ms: int,
) -> TraceEvent:
    """Memory build completed event."""
    return TraceEvent(
        trace_id=trace_id,
        event_id=event_id,
        event_type=TraceEventType.MEMORY_BUILD,
        status=TraceEventStatus.COMPLETED,
        timestamp=current_timestamp_int_milliseconds(),
        duration_ms=duration_ms,
        content={"num_messages": num_messages},
    )


def build_trace_system_prompt_build(
    trace_id: str,
    event_id: str,
    prompt_length: int,
    has_retrieval: bool,
    duration_ms: int,
) -> TraceEvent:
    """System prompt build completed event."""
    return TraceEvent(
        trace_id=trace_id,
        event_id=event_id,
        event_type=TraceEventType.SYSTEM_PROMPT_BUILD,
        status=TraceEventStatus.COMPLETED,
        timestamp=current_timestamp_int_milliseconds(),
        duration_ms=duration_ms,
        content={"prompt_length": prompt_length, "has_retrieval": has_retrieval},
    )


def build_trace_retrieval_start(
    trace_id: str,
    event_id: str,
    query_text: str,
    top_k: int,
) -> TraceEvent:
    """Retrieval started event."""
    return TraceEvent(
        trace_id=trace_id,
        event_id=event_id,
        event_type=TraceEventType.RETRIEVAL,
        status=TraceEventStatus.STARTED,
        timestamp=current_timestamp_int_milliseconds(),
        content={"query_text": query_text, "top_k": top_k},
    )


def build_trace_retrieval_complete(
    trace_id: str,
    event_id: str,
    result_count: int,
    results: List[RetrievalResult],
    duration_ms: int,
) -> TraceEvent:
    """Retrieval completed event."""
    return TraceEvent(
        trace_id=trace_id,
        event_id=event_id,
        event_type=TraceEventType.RETRIEVAL,
        status=TraceEventStatus.COMPLETED,
        timestamp=current_timestamp_int_milliseconds(),
        duration_ms=duration_ms,
        content={
            "result_count": result_count,
            "results": [r.model_dump(exclude_none=True) for r in results],
        },
    )


def build_trace_retrieval_error(
    trace_id: str,
    event_id: str,
    error: str,
    duration_ms: int,
) -> TraceEvent:
    """Retrieval error event."""
    return TraceEvent(
        trace_id=trace_id,
        event_id=event_id,
        event_type=TraceEventType.RETRIEVAL,
        status=TraceEventStatus.ERROR,
        timestamp=current_timestamp_int_milliseconds(),
        duration_ms=duration_ms,
        content={},
        error=error,
    )


def build_trace_tool_start(
    trace_id: str,
    event_id: str,
    tool_type: str,
    tool_id: str,
    name: str,
    arguments: Dict[str, Any],
) -> TraceEvent:
    """Tool call started event."""
    return TraceEvent(
        trace_id=trace_id,
        event_id=event_id,
        event_type=TraceEventType.TOOL_CALL,
        status=TraceEventStatus.STARTED,
        timestamp=current_timestamp_int_milliseconds(),
        content={
            "tool_type": tool_type,
            "tool_id": tool_id,
            "name": name,
            "arguments": arguments,
        },
    )


def build_trace_tool_complete(
    trace_id: str,
    event_id: str,
    tool_type: str,
    tool_id: str,
    output: str,
    duration_ms: int,
) -> TraceEvent:
    """Tool call completed event."""
    return TraceEvent(
        trace_id=trace_id,
        event_id=event_id,
        event_type=TraceEventType.TOOL_CALL,
        status=TraceEventStatus.COMPLETED,
        timestamp=current_timestamp_int_milliseconds(),
        duration_ms=duration_ms,
        content={
            "tool_type": tool_type,
            "tool_id": tool_id,
            "output": output,
        },
    )


def build_trace_tool_error(
    trace_id: str,
    event_id: str,
    tool_type: str,
    tool_id: str,
    error: str,
    duration_ms: int,
) -> TraceEvent:
    """Tool call error event."""
    return TraceEvent(
        trace_id=trace_id,
        event_id=event_id,
        event_type=TraceEventType.TOOL_CALL,
        status=TraceEventStatus.ERROR,
        timestamp=current_timestamp_int_milliseconds(),
        duration_ms=duration_ms,
        content={
            "tool_type": tool_type,
            "tool_id": tool_id,
        },
        error=error,
    )


def build_trace_inference_start(
    trace_id: str,
    event_id: str,
    model_id: str,
    provider_model_id: str,
    message_count: int,
    function_count: int,
) -> TraceEvent:
    """Model inference started event."""
    return TraceEvent(
        trace_id=trace_id,
        event_id=event_id,
        event_type=TraceEventType.INFERENCE,
        status=TraceEventStatus.STARTED,
        timestamp=current_timestamp_int_milliseconds(),
        content={
            "model_id": model_id,
            "provider_model_id": provider_model_id,
            "message_count": message_count,
            "function_count": function_count,
        },
    )


def build_trace_inference_complete(
    trace_id: str,
    event_id: str,
    input_tokens: int,
    output_tokens: int,
    duration_ms: int,
) -> TraceEvent:
    """Model inference completed event."""
    return TraceEvent(
        trace_id=trace_id,
        event_id=event_id,
        event_type=TraceEventType.INFERENCE,
        status=TraceEventStatus.COMPLETED,
        timestamp=current_timestamp_int_milliseconds(),
        duration_ms=duration_ms,
        content={
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        },
    )


def build_trace_inference_error(
    trace_id: str,
    event_id: str,
    error: str,
    duration_ms: int,
) -> TraceEvent:
    """Model inference error event."""
    return TraceEvent(
        trace_id=trace_id,
        event_id=event_id,
        event_type=TraceEventType.INFERENCE,
        status=TraceEventStatus.ERROR,
        timestamp=current_timestamp_int_milliseconds(),
        duration_ms=duration_ms,
        content={},
        error=error,
    )


def build_trace_chat_completion_start(
    trace_id: str,
    event_id: str,
    model_id: str,
    provider_model_id: str,
    message_count: int,
    function_count: int,
) -> TraceEvent:
    """Chat completion request started event."""
    return TraceEvent(
        trace_id=trace_id,
        event_id=event_id,
        event_type=TraceEventType.CHAT_COMPLETION,
        status=TraceEventStatus.STARTED,
        timestamp=current_timestamp_int_milliseconds(),
        content={
            "model_id": model_id,
            "provider_model_id": provider_model_id,
            "message_count": message_count,
            "function_count": function_count,
        },
    )


def build_trace_chat_completion_complete(
    trace_id: str,
    event_id: str,
    input_tokens: int,
    output_tokens: int,
    has_function_calls: bool,
    duration_ms: int,
) -> TraceEvent:
    """Chat completion request completed event."""
    return TraceEvent(
        trace_id=trace_id,
        event_id=event_id,
        event_type=TraceEventType.CHAT_COMPLETION,
        status=TraceEventStatus.COMPLETED,
        timestamp=current_timestamp_int_milliseconds(),
        duration_ms=duration_ms,
        content={
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "has_function_calls": has_function_calls,
        },
    )


def build_trace_chat_completion_error(
    trace_id: str,
    event_id: str,
    error: str,
    duration_ms: int,
) -> TraceEvent:
    """Chat completion request error event."""
    return TraceEvent(
        trace_id=trace_id,
        event_id=event_id,
        event_type=TraceEventType.CHAT_COMPLETION,
        status=TraceEventStatus.ERROR,
        timestamp=current_timestamp_int_milliseconds(),
        duration_ms=duration_ms,
        content={},
        error=error,
    )


def build_trace_usage_summary(
    trace_id: str,
    total_input_tokens: int,
    total_output_tokens: int,
) -> TraceEvent:
    """Final token usage summary event."""
    return TraceEvent(
        trace_id=trace_id,
        event_id="usage_summary",
        event_type=TraceEventType.USAGE_SUMMARY,
        status=TraceEventStatus.COMPLETED,
        timestamp=current_timestamp_int_milliseconds(),
        content={
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
        },
    )
