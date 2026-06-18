import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from fastapi import HTTPException
from tkhelper.error import ErrorCode, raise_http_error
from tkhelper.schemas import BaseDataResponse
from tkhelper.utils import SSE_DONE_MSG

from app.models import MessageContent, MessageRole, ToolOutput
from app.operators import message_ops
from app.schemas.model.chat_completion import ChatCompletionResponse

from .log import (
    build_chat_completion_input_log_dict,
    build_chat_completion_output_log_dict,
)
from .session import (
    TOOL_RUN_TYPE_LOG,
    TOOL_RUN_TYPE_TOOL_OUTPUT,
    TOOL_RUN_TYPE_RETRIEVAL_RESULT,
)
from .utils import (
    MessageGenerationException,
    MessageGenerationInvalidRequestException,
    generate_random_event_id,
    current_timestamp_int_milliseconds,
)

logger = logging.getLogger(__name__)

__all__ = [
    "TraceEvent",
    "GenerationResult",
    "InferenceRound",
    "ToolRound",
    "GenerationResultBuilder",
    "MessageFinalizationHelper",
    "error_message",
]


def error_message(code, message: str):
    return {
        "object": "Error",
        "code": code,
        "message": message,
    }


def _extract_artifacts_from_tool_output(tool_output: ToolOutput) -> List[Dict[str, Any]]:
    artifacts: List[Dict[str, Any]] = []
    if tool_output.status != 200:
        return artifacts
    data = tool_output.data
    if isinstance(data, dict):
        for key in ("artifact", "artifacts", "file", "files"):
            value = data.get(key)
            if value is None:
                continue
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        artifacts.append(item)
            elif isinstance(value, dict):
                artifacts.append(value)
    for idx, artifact in enumerate(artifacts):
        if "source" not in artifact:
            artifact["source"] = {
                "type": "tool",
                "tool_id": tool_output.tool_id,
                "tool_type": tool_output.type.value if hasattr(tool_output.type, "value") else tool_output.type,
                "tool_call_id": tool_output.tool_call_id,
                "index": idx,
            }
    return artifacts


def _extract_artifacts_from_retrieval(retrieval_results: List[Any]) -> List[Dict[str, Any]]:
    artifacts: List[Dict[str, Any]] = []
    for idx, result in enumerate(retrieval_results or []):
        if isinstance(result, dict):
            if "artifact" in result or "file" in result or "url" in result:
                artifact = {
                    "source": {
                        "type": "retrieval",
                        "index": idx,
                    }
                }
                for key in ("artifact", "file", "url", "name", "title"):
                    if key in result:
                        artifact[key] = result[key]
                artifacts.append(artifact)
    return artifacts


@dataclass
class TraceEvent:
    event_id: str
    event: str
    step: str
    timestamp: int
    duration_ms: Optional[int] = None
    status: Optional[str] = None
    input_summary: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        d = {
            "event_id": self.event_id,
            "event": self.event,
            "step": self.step,
            "timestamp": self.timestamp,
        }
        if self.duration_ms is not None:
            d["duration_ms"] = self.duration_ms
        if self.status is not None:
            d["status"] = self.status
        if self.input_summary is not None:
            d["input_summary"] = self.input_summary
        if self.metadata:
            d["metadata"] = self.metadata
        return d


@dataclass
class InferenceRound:
    round_index: int
    event_id: str
    assistant_message_dict: Optional[Dict] = None
    function_calls: Optional[List[Dict]] = None
    usage_dict: Optional[Dict] = None
    response_dict: Optional[Dict] = None
    duration_ms: Optional[int] = None
    _usage_accumulated: bool = field(default=False, init=False, repr=False)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "round_index": self.round_index,
            "event_id": self.event_id,
            "assistant_message_dict": self.assistant_message_dict,
            "function_calls": self.function_calls,
            "usage_dict": self.usage_dict,
            "duration_ms": self.duration_ms,
        }


@dataclass
class ToolRound:
    round_index: int
    function_calls: List[Dict]
    tool_outputs: List[ToolOutput] = field(default_factory=list)
    retrieval_results: List[Any] = field(default_factory=list)
    tool_call_logs: List[Dict] = field(default_factory=list)
    extracted_artifacts: List[Dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "round_index": self.round_index,
            "function_calls": self.function_calls,
            "tool_outputs": [to.model_dump() for to in self.tool_outputs],
            "retrieval_results": self.retrieval_results,
            "tool_call_logs": self.tool_call_logs,
            "num_extracted_artifacts": len(self.extracted_artifacts),
        }


@dataclass
class GenerationResult:
    session_id: str
    assistant_id: str
    chat_id: Optional[str] = None

    final_assistant_message_dict: Optional[Dict] = None
    filtered_user_function_calls: Optional[List[Dict]] = None

    final_response_dict: Optional[Dict] = None

    total_input_tokens: int = 0
    total_output_tokens: int = 0

    logs: List[Dict] = field(default_factory=list)
    trace_events: List[TraceEvent] = field(default_factory=list)

    retrieval_results: List[Any] = field(default_factory=list)

    inference_rounds: List[InferenceRound] = field(default_factory=list)
    tool_rounds: List[ToolRound] = field(default_factory=list)

    artifacts: List[Dict] = field(default_factory=list)

    persisted_message: Optional[Any] = None

    _accumulated_round_ids: Set[int] = field(default_factory=set, init=False, repr=False)
    _active_trace_starts: Dict[str, int] = field(default_factory=dict, init=False, repr=False)

    @property
    def content_text(self) -> Optional[str]:
        if self.final_assistant_message_dict is None:
            return None
        return self.final_assistant_message_dict.get("content")

    @property
    def has_user_function_calls(self) -> bool:
        return self.filtered_user_function_calls is not None

    @property
    def total_tool_calls(self) -> int:
        return sum(len(tr.function_calls) for tr in self.tool_rounds)

    @property
    def all_tool_outputs(self) -> List[ToolOutput]:
        outputs: List[ToolOutput] = []
        for tr in self.tool_rounds:
            outputs.extend(tr.tool_outputs)
        return outputs

    @property
    def all_retrieval_results(self) -> List[Any]:
        results: List[Any] = list(self.retrieval_results)
        for tr in self.tool_rounds:
            results.extend(tr.retrieval_results)
        return results

    @property
    def num_trace_events(self) -> int:
        return len(self.trace_events)

    def accumulate_usage(self, input_tokens: int, output_tokens: int, round_index: Optional[int] = None):
        if round_index is not None:
            if round_index in self._accumulated_round_ids:
                logger.warning(
                    f"Usage for round {round_index} already accumulated; skipping to avoid double-counting."
                )
                return
            self._accumulated_round_ids.add(round_index)
        self.total_input_tokens += input_tokens or 0
        self.total_output_tokens += output_tokens or 0

    def apply_usage_to_response(self, response_dict: Dict) -> Dict:
        if "usage" not in response_dict:
            response_dict["usage"] = {}
        response_dict["usage"]["input_tokens"] = self.total_input_tokens
        response_dict["usage"]["output_tokens"] = self.total_output_tokens
        self.final_response_dict = response_dict
        return response_dict

    def trace_summary(self) -> Dict[str, Any]:
        event_types: Dict[str, Dict[str, Any]] = {}
        for ev in self.trace_events:
            et = event_types.setdefault(ev.event, {"count": 0, "total_duration_ms": 0})
            et["count"] += 1
            if ev.duration_ms is not None:
                et["total_duration_ms"] += ev.duration_ms
        return {
            "num_events": len(self.trace_events),
            "events": event_types,
        }

    def as_summary_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "assistant_id": self.assistant_id,
            "chat_id": self.chat_id,
            "final_content_text": self.content_text,
            "has_user_function_calls": self.has_user_function_calls,
            "num_filtered_user_function_calls": len(self.filtered_user_function_calls or []),
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "num_logs": len(self.logs),
            "num_trace_events": self.num_trace_events,
            "num_retrieval_results": len(self.all_retrieval_results),
            "num_inference_rounds": len(self.inference_rounds),
            "num_accumulated_rounds": len(self._accumulated_round_ids),
            "num_tool_rounds": len(self.tool_rounds),
            "total_tool_calls": self.total_tool_calls,
            "num_artifacts": len(self.artifacts),
            "message_persisted": self.persisted_message is not None,
            "trace_summary": self.trace_summary(),
        }


class GenerationResultBuilder:
    def __init__(self, session, result: GenerationResult):
        self._session = session
        self._result = result

    @property
    def result(self) -> GenerationResult:
        return self._result

    def add_trace_event(
        self,
        event_id: str,
        event: str,
        step: str,
        timestamp: Optional[int] = None,
        duration_ms: Optional[int] = None,
        status: Optional[str] = None,
        input_summary: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TraceEvent:
        te = TraceEvent(
            event_id=event_id,
            event=event,
            step=step,
            timestamp=timestamp if timestamp is not None else current_timestamp_int_milliseconds(),
            duration_ms=duration_ms,
            status=status,
            input_summary=input_summary,
            metadata=metadata or {},
        )
        self._result.trace_events.append(te)
        return te

    def start_trace(
        self,
        event_id: str,
        event: str,
        input_summary: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TraceEvent:
        ts = current_timestamp_int_milliseconds()
        self._result._active_trace_starts[event_id] = ts
        return self.add_trace_event(
            event_id=event_id,
            event=event,
            step="start",
            timestamp=ts,
            status="start",
            input_summary=input_summary,
            metadata=metadata,
        )

    def end_trace(
        self,
        event_id: str,
        event: str,
        status: str = "success",
        input_summary: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TraceEvent:
        ts = current_timestamp_int_milliseconds()
        start_ts = self._result._active_trace_starts.pop(event_id, None)
        duration_ms = ts - start_ts if start_ts is not None else None
        return self.add_trace_event(
            event_id=event_id,
            event=event,
            step="end",
            timestamp=ts,
            duration_ms=duration_ms,
            status=status,
            input_summary=input_summary,
            metadata=metadata,
        )

    def append_chat_completion_input_log(self, event_id: str, save: bool = False):
        log_dict = build_chat_completion_input_log_dict(
            session_id=self._result.session_id,
            event_id=event_id,
            model=self._session.model,
            messages=self._session.chat_completion_messages,
            functions=self._session.chat_completion_functions,
        )
        if save:
            self._result.logs.append(log_dict)
        return log_dict

    def append_chat_completion_output_log(
        self, event_id: str, assistant_message_dict: Dict, usage_dict: Dict, save: bool = False
    ):
        log_dict = build_chat_completion_output_log_dict(
            session_id=self._result.session_id,
            event_id=event_id,
            model=self._session.model,
            message=assistant_message_dict,
            usage=usage_dict,
        )
        if save:
            self._result.logs.append(log_dict)
        return log_dict

    def begin_inference_round(self, round_index: int, event_id: str) -> InferenceRound:
        ir = InferenceRound(round_index=round_index, event_id=event_id)
        self._result.inference_rounds.append(ir)
        return ir

    def complete_inference_round(
        self,
        ir: InferenceRound,
        assistant_message_dict: Dict,
        function_calls: Optional[List[Dict]],
        usage_dict: Optional[Dict],
        response_dict: Optional[Dict] = None,
        duration_ms: Optional[int] = None,
    ):
        ir.assistant_message_dict = assistant_message_dict
        ir.function_calls = function_calls
        ir.usage_dict = usage_dict
        ir.response_dict = response_dict
        ir.duration_ms = duration_ms
        if usage_dict and not ir._usage_accumulated:
            self._result.accumulate_usage(
                usage_dict.get("input_tokens", 0),
                usage_dict.get("output_tokens", 0),
                round_index=ir.round_index,
            )
            ir._usage_accumulated = True
        if function_calls:
            filtered = self._session.filter_user_function_calls(function_calls)
            if filtered:
                self._result.filtered_user_function_calls = filtered
            if response_dict and filtered:
                response_dict["message"]["function_calls"] = filtered
        if not function_calls or self._result.has_user_function_calls:
            self._result.final_assistant_message_dict = assistant_message_dict
            if response_dict:
                self._result.apply_usage_to_response(response_dict)
        return ir

    def begin_tool_round(self, round_index: int, function_calls: List[Dict]) -> ToolRound:
        tr = ToolRound(round_index=round_index, function_calls=function_calls)
        self._result.tool_rounds.append(tr)
        return tr

    def _consume_tool_run_event(
        self,
        tr: ToolRound,
        event: Tuple[str, Any],
    ):
        event_type, payload = event
        if event_type == TOOL_RUN_TYPE_TOOL_OUTPUT:
            tool_output: ToolOutput = payload
            tr.tool_outputs.append(tool_output)
            extracted = _extract_artifacts_from_tool_output(tool_output)
            if extracted:
                tr.extracted_artifacts.extend(extracted)
                self._result.artifacts.extend(extracted)
        elif event_type == TOOL_RUN_TYPE_RETRIEVAL_RESULT:
            tr.retrieval_results.extend(payload)
            extracted = _extract_artifacts_from_retrieval(payload)
            if extracted:
                tr.extracted_artifacts.extend(extracted)
                self._result.artifacts.extend(extracted)
        elif event_type == TOOL_RUN_TYPE_LOG:
            tr.tool_call_logs.append(payload)
        else:
            logger.warning(f"Unknown tool run event type: {event_type}")

    async def process_tool_calls(
        self,
        function_calls: List[Dict],
        round_index: int,
        log: bool = False,
    ) -> ToolRound:
        tr = self.begin_tool_round(round_index, function_calls)
        use_logs = await self._session.use_tool(
            function_calls,
            round_index=round_index,
            log=log,
        )
        tr.tool_call_logs.extend(use_logs)
        async for event in self._session.run_tools(function_calls, log=log):
            self._consume_tool_run_event(tr, event)
        return tr

    async def process_tool_calls_with_debug(
        self,
        function_calls: List[Dict],
        round_index: int,
        log: bool = False,
    ):
        tr = self.begin_tool_round(round_index, function_calls)
        tool_action_call_logs = await self._session.use_tool(
            function_calls=function_calls,
            round_index=round_index,
            log=log,
        )
        tr.tool_call_logs.extend(tool_action_call_logs)
        for tool_action_call_log_dict in tool_action_call_logs:
            logger.debug(f"tool_action_call_log_dict = {tool_action_call_log_dict}")
            yield f"data: {json.dumps(tool_action_call_log_dict)}\n\n"

        async for event in self._session.run_tools(
            function_calls=function_calls, log=True
        ):
            self._consume_tool_run_event(tr, event)
            event_type, payload = event
            if event_type == TOOL_RUN_TYPE_LOG:
                logger.debug(f"tool_action_result_log_dict = {payload}")
                yield f"data: {json.dumps(payload)}\n\n"

    def add_artifact(self, artifact: Dict):
        self._result.artifacts.append(artifact)

    def extend_logs(self, log_dicts: List[Dict]):
        self._result.logs.extend(log_dicts)

    def attach_artifacts_to_response(self, response_dict: Dict) -> Dict:
        if not self._result.artifacts:
            return response_dict
        message_dict = response_dict.get("message")
        if message_dict is not None:
            content = message_dict.get("content")
            if isinstance(content, str):
                message_dict["content"] = {
                    "text": content,
                    "artifacts": self._result.artifacts,
                }
            elif isinstance(content, dict):
                content["artifacts"] = self._result.artifacts
            else:
                message_dict["artifacts"] = self._result.artifacts
        else:
            response_dict["artifacts"] = self._result.artifacts
        return response_dict


class MessageFinalizationHelper:
    @staticmethod
    def _build_metadata(result: GenerationResult) -> Dict[str, Any]:
        return {
            "num_tool_rounds": len(result.tool_rounds),
            "total_tool_calls": result.total_tool_calls,
            "num_artifacts": len(result.artifacts),
            "num_retrieval_results": len(result.all_retrieval_results),
            "num_trace_events": result.num_trace_events,
            "num_inference_rounds": len(result.inference_rounds),
            "trace_summary": result.trace_summary(),
        }

    @staticmethod
    async def persist_assistant_message(result: GenerationResult):
        if not result.chat_id:
            raise MessageGenerationInvalidRequestException("Chat is required to create a message.")
        if result.content_text is None:
            raise MessageGenerationException("Assistant message content is not available to persist.")

        content_kwargs: Dict[str, Any] = {"text": result.content_text}
        if result.artifacts:
            content_kwargs["artifacts"] = result.artifacts
        content = MessageContent(**content_kwargs)

        message = await message_ops.create(
            assistant_id=result.assistant_id,
            chat_id=result.chat_id,
            create_dict={
                "role": MessageRole.ASSISTANT.value,
                "content": content,
                "metadata": MessageFinalizationHelper._build_metadata(result),
                "logs": result.logs,
            },
            check_max_count=False,
        )
        result.persisted_message = message
        return message

    @staticmethod
    async def build_stateful_normal_response(result: GenerationResult):
        message = await MessageFinalizationHelper.persist_assistant_message(result)
        return BaseDataResponse(data=message.to_response_dict())

    @staticmethod
    async def build_stateful_stream_events(result: GenerationResult):
        message = await MessageFinalizationHelper.persist_assistant_message(result)
        message_dict = message.to_response_dict()
        yield f"data: {json.dumps(message_dict)}\n\n"
        yield SSE_DONE_MSG

    @staticmethod
    def build_stateless_normal_response(result: GenerationResult, builder: Optional[GenerationResultBuilder] = None) -> ChatCompletionResponse:
        if result.final_response_dict is None:
            raise MessageGenerationException("No response dict available for stateless response.")
        result.apply_usage_to_response(result.final_response_dict)
        if builder is not None and result.artifacts:
            builder.attach_artifacts_to_response(result.final_response_dict)
        return ChatCompletionResponse(data=result.final_response_dict)

    @staticmethod
    async def build_stateless_stream_events(
        result: GenerationResult,
        yield_dict: bool = False,
        builder: Optional[GenerationResultBuilder] = None,
    ):
        if result.final_response_dict is None:
            raise MessageGenerationException("No response dict available for stateless response.")
        result.apply_usage_to_response(result.final_response_dict)
        if builder is not None and result.artifacts:
            builder.attach_artifacts_to_response(result.final_response_dict)
        if yield_dict:
            yield result.final_response_dict
        else:
            yield f"data: {json.dumps(result.final_response_dict)}\n\n"
            yield SSE_DONE_MSG

    @staticmethod
    async def build_sse_error(error_code, message: str, yield_dict: bool = False):
        err_dict = error_message(code=error_code, message=message)
        if yield_dict:
            yield err_dict
        else:
            yield f"data: {json.dumps(err_dict)}\n\n"
            yield SSE_DONE_MSG

    @staticmethod
    def raise_http_error_for_exception(exc):
        if isinstance(exc, MessageGenerationInvalidRequestException):
            raise_http_error(ErrorCode.INVALID_REQUEST, message=str(exc))
        elif isinstance(exc, MessageGenerationException):
            raise_http_error(ErrorCode.GENERATION_ERROR, message=str(exc))
        else:
            raise_http_error(
                ErrorCode.INTERNAL_SERVER_ERROR, message="Assistant message not generated due to an unknown error."
            )
