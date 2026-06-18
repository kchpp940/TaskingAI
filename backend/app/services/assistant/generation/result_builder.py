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
)

logger = logging.getLogger(__name__)

__all__ = [
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

    retrieval_results: List[Any] = field(default_factory=list)

    inference_rounds: List[InferenceRound] = field(default_factory=list)
    tool_rounds: List[ToolRound] = field(default_factory=list)

    artifacts: List[Dict] = field(default_factory=list)

    persisted_message: Optional[Any] = None

    _accumulated_round_ids: Set[int] = field(default_factory=set, init=False, repr=False)

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
            "num_retrieval_results": len(self.all_retrieval_results),
            "num_inference_rounds": len(self.inference_rounds),
            "num_accumulated_rounds": len(self._accumulated_round_ids),
            "num_tool_rounds": len(self.tool_rounds),
            "total_tool_calls": self.total_tool_calls,
            "num_artifacts": len(self.artifacts),
            "message_persisted": self.persisted_message is not None,
        }


class GenerationResultBuilder:
    def __init__(self, session, result: GenerationResult):
        self._session = session
        self._result = result

    @property
    def result(self) -> GenerationResult:
        return self._result

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


class MessageFinalizationHelper:
    @staticmethod
    async def persist_assistant_message(result: GenerationResult):
        if not result.chat_id:
            raise MessageGenerationInvalidRequestException("Chat is required to create a message.")
        if result.content_text is None:
            raise MessageGenerationException("Assistant message content is not available to persist.")
        metadata = {
            "num_tool_rounds": len(result.tool_rounds),
            "total_tool_calls": result.total_tool_calls,
            "num_artifacts": len(result.artifacts),
            "num_retrieval_results": len(result.all_retrieval_results),
        }
        if result.artifacts:
            metadata["artifacts"] = result.artifacts
        message = await message_ops.create(
            assistant_id=result.assistant_id,
            chat_id=result.chat_id,
            create_dict={
                "role": MessageRole.ASSISTANT.value,
                "content": MessageContent(text=result.content_text),
                "metadata": metadata,
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
    def build_stateless_normal_response(result: GenerationResult) -> ChatCompletionResponse:
        if result.final_response_dict is None:
            raise MessageGenerationException("No response dict available for stateless response.")
        result.apply_usage_to_response(result.final_response_dict)
        return ChatCompletionResponse(data=result.final_response_dict)

    @staticmethod
    async def build_stateless_stream_events(result: GenerationResult, yield_dict: bool = False):
        if result.final_response_dict is None:
            raise MessageGenerationException("No response dict available for stateless response.")
        result.apply_usage_to_response(result.final_response_dict)
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
