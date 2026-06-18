from typing import Dict, List, Optional
from tkhelper.utils import current_timestamp_int_milliseconds

from app.models import MessageGenerationLog, Model, RetrievalResult, ToolInput, ToolOutput

__all__ = [
    "build_retrieval_input_log_dict",
    "build_retrieval_output_log_dict",
    "build_tool_input_log_dict",
    "build_tool_output_log_dict",
    "build_chat_completion_input_log_dict",
    "build_chat_completion_output_log_dict",
    "build_trace_start_log_dict",
    "build_trace_end_log_dict",
    "build_trace_error_log_dict",
    "build_usage_summary_log_dict",
    "TraceCollector",
]


def _truncate_text(text: str, max_len: int = 100) -> str:
    if text and len(text) > max_len:
        return text[:max_len] + "..."
    return text or ""


def build_retrieval_input_log_dict(
    session_id: str,
    event_id: str,
    query_text: str,
    top_k: int,
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
        status="start",
        input_summary=f"query: {_truncate_text(query_text)}",
    ).model_dump(exclude_none=True)


def build_retrieval_output_log_dict(
    session_id: str,
    event_id: str,
    retrieval_result: List[RetrievalResult],
    duration_ms: Optional[int] = None,
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
        status="success",
        duration_ms=duration_ms,
        input_summary=f"hit {len(retrieval_result)} chunks",
    ).model_dump(exclude_none=True)


def build_tool_input_log_dict(
    session_id: str,
    event_id: str,
    tool_input: ToolInput,
):
    args_str = _truncate_text(str(tool_input.arguments))
    return MessageGenerationLog(
        session_id=session_id,
        event="tool",
        event_id=event_id,
        event_step="input",
        timestamp=current_timestamp_int_milliseconds(),
        content=tool_input.model_dump(),
        status="start",
        input_summary=f"tool_id={tool_input.tool_id}, args={args_str}",
    ).model_dump(exclude_none=True)


def build_tool_output_log_dict(
    session_id: str,
    event_id: str,
    tool_output: ToolOutput,
    duration_ms: Optional[int] = None,
):
    output_str = _truncate_text(str(tool_output.content))
    return MessageGenerationLog(
        session_id=session_id,
        event="tool",
        event_id=event_id,
        event_step="output",
        timestamp=current_timestamp_int_milliseconds(),
        content=tool_output.model_dump(),
        status="success",
        duration_ms=duration_ms,
        input_summary=f"result: {output_str}",
    ).model_dump(exclude_none=True)


def build_chat_completion_input_log_dict(
    session_id: str,
    event_id: str,
    model: Model,
    messages: List[Dict],
    functions: List[Dict],
):
    return MessageGenerationLog(
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
        status="start",
        input_summary=f"model={model.provider_model_id}, msgs={len(messages)}, funcs={len(functions)}",
    ).model_dump(exclude_none=True)


def build_chat_completion_output_log_dict(
    session_id: str,
    event_id: str,
    model: Model,
    message: Dict,
    usage: Dict,
    duration_ms: Optional[int] = None,
):
    usage_str = f"in={usage.get('input_tokens', 0)}, out={usage.get('output_tokens', 0)}" if usage else ""
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
        status="success",
        duration_ms=duration_ms,
        input_summary=usage_str,
    ).model_dump(exclude_none=True)


def build_trace_start_log_dict(
    session_id: str,
    event_id: str,
    event: str,
    content: Dict,
    input_summary: Optional[str] = None,
):
    return MessageGenerationLog(
        session_id=session_id,
        event=event,
        event_id=event_id,
        event_step="start",
        timestamp=current_timestamp_int_milliseconds(),
        content=content,
        status="start",
        input_summary=input_summary,
    ).model_dump(exclude_none=True)


def build_trace_end_log_dict(
    session_id: str,
    event_id: str,
    event: str,
    content: Dict,
    duration_ms: int,
    input_summary: Optional[str] = None,
):
    return MessageGenerationLog(
        session_id=session_id,
        event=event,
        event_id=event_id,
        event_step="end",
        timestamp=current_timestamp_int_milliseconds(),
        content=content,
        status="success",
        duration_ms=duration_ms,
        input_summary=input_summary,
    ).model_dump(exclude_none=True)


def build_trace_error_log_dict(
    session_id: str,
    event_id: str,
    event: str,
    error_message: str,
    error_type: Optional[str] = None,
    duration_ms: Optional[int] = None,
    content: Optional[Dict] = None,
):
    return MessageGenerationLog(
        session_id=session_id,
        event=event,
        event_id=event_id,
        event_step="error",
        timestamp=current_timestamp_int_milliseconds(),
        content=content or {},
        status="error",
        duration_ms=duration_ms,
        error={
            "message": error_message,
            "type": error_type or "Exception",
        },
        input_summary=f"error: {_truncate_text(error_message)}",
    ).model_dump(exclude_none=True)


def build_usage_summary_log_dict(
    session_id: str,
    event_id: str,
    total_input_tokens: int,
    total_output_tokens: int,
    total_duration_ms: Optional[int] = None,
):
    return MessageGenerationLog(
        session_id=session_id,
        event="usage_summary",
        event_id=event_id,
        event_step="summary",
        timestamp=current_timestamp_int_milliseconds(),
        content={
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
        },
        status="success",
        duration_ms=total_duration_ms,
        input_summary=f"total_in={total_input_tokens}, total_out={total_output_tokens}",
    ).model_dump(exclude_none=True)


class TraceCollector:
    def __init__(self):
        self._start_times: Dict[str, int] = {}

    def start(self, event_id: str) -> int:
        now = current_timestamp_int_milliseconds()
        self._start_times[event_id] = now
        return now

    def duration(self, event_id: str) -> Optional[int]:
        start = self._start_times.get(event_id)
        if start is None:
            return None
        return current_timestamp_int_milliseconds() - start

    def clear(self, event_id: str):
        if event_id in self._start_times:
            del self._start_times[event_id]
