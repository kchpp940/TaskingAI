import json
import logging
from typing import Dict, List, Optional

from fastapi import HTTPException
from tkhelper.error import ErrorCode, raise_http_error
from tkhelper.schemas import BaseDataResponse
from tkhelper.utils import SSE_DONE_MSG

from app.models import MessageContent, MessageRole
from app.operators import message_ops
from app.schemas.model.chat_completion import ChatCompletionResponse

from .log import (
    build_chat_completion_input_log_dict,
    build_chat_completion_output_log_dict,
)
from .utils import (
    MessageGenerationException,
    MessageGenerationInvalidRequestException,
    generate_random_event_id,
)

logger = logging.getLogger(__name__)

__all__ = [
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


class GenerationResultBuilder:
    def __init__(self, session):
        self._session = session

    def append_chat_completion_input_log(self, event_id: str, save: bool = False):
        log_dict = build_chat_completion_input_log_dict(
            session_id=self._session.session_id,
            event_id=event_id,
            model=self._session.model,
            messages=self._session.chat_completion_messages,
            functions=self._session.chat_completion_functions,
        )
        if save:
            self._session.logs.append(log_dict)
        return log_dict

    def append_chat_completion_output_log(
        self, event_id: str, assistant_message_dict: Dict, usage_dict: Dict, save: bool = False
    ):
        log_dict = build_chat_completion_output_log_dict(
            session_id=self._session.session_id,
            event_id=event_id,
            model=self._session.model,
            message=assistant_message_dict,
            usage=usage_dict,
        )
        if save:
            self._session.logs.append(log_dict)
        return log_dict

    async def process_tool_calls(
        self,
        function_calls: List[Dict],
        round_index: int,
        log: bool = False,
    ):
        await self._session.use_tool(
            function_calls,
            round_index=round_index,
            log=log,
        )
        async for _ in self._session.run_tools(function_calls):
            pass

    async def process_tool_calls_with_debug(
        self,
        function_calls: List[Dict],
        round_index: int,
        log: bool = False,
    ):
        tool_action_call_logs = await self._session.use_tool(
            function_calls=function_calls,
            round_index=round_index,
            log=log,
        )
        for tool_action_call_log_dict in tool_action_call_logs:
            logger.debug(f"tool_action_call_log_dict = {tool_action_call_log_dict}")
            yield f"data: {json.dumps(tool_action_call_log_dict)}\n\n"

        async for tool_action_result_log_dict in self._session.run_tools(
            function_calls=function_calls, log=True
        ):
            logger.debug(f"tool_action_result_log_dict = {tool_action_result_log_dict}")
            yield f"data: {json.dumps(tool_action_result_log_dict)}\n\n"

    def apply_usage_to_response(self, response_dict: Dict):
        response_dict["usage"]["input_tokens"] = self._session.total_input_tokens
        response_dict["usage"]["output_tokens"] = self._session.total_output_tokens
        return response_dict


class MessageFinalizationHelper:
    @staticmethod
    async def persist_assistant_message(session, content_text: str, logs: Optional[List[Dict]] = None):
        if not session.chat:
            raise MessageGenerationInvalidRequestException("Chat is required to create a message.")
        return await message_ops.create(
            assistant_id=session.assistant.assistant_id,
            chat_id=session.chat.chat_id,
            create_dict={
                "role": MessageRole.ASSISTANT.value,
                "content": MessageContent(text=content_text),
                "metadata": {},
                "logs": logs,
            },
            check_max_count=False,
        )

    @staticmethod
    async def build_stateful_normal_response(session, content_text: str, logs: Optional[List[Dict]] = None):
        message = await MessageFinalizationHelper.persist_assistant_message(session, content_text, logs)
        return BaseDataResponse(data=message.to_response_dict())

    @staticmethod
    async def build_stateful_stream_events(session, content_text: str, logs: Optional[List[Dict]] = None):
        message = await MessageFinalizationHelper.persist_assistant_message(session, content_text, logs)
        message_dict = message.to_response_dict()
        yield f"data: {json.dumps(message_dict)}\n\n"
        yield SSE_DONE_MSG

    @staticmethod
    def build_stateless_normal_response(response_dict: Dict, total_input_tokens: int, total_output_tokens: int):
        response_dict["usage"]["input_tokens"] = total_input_tokens
        response_dict["usage"]["output_tokens"] = total_output_tokens
        return ChatCompletionResponse(data=response_dict)

    @staticmethod
    async def build_stateless_stream_events(
        response_dict: Dict, total_input_tokens: int, total_output_tokens: int, yield_dict: bool = False
    ):
        response_dict["usage"]["input_tokens"] = total_input_tokens
        response_dict["usage"]["output_tokens"] = total_output_tokens
        if yield_dict:
            yield response_dict
        else:
            yield f"data: {json.dumps(response_dict)}\n\n"
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
