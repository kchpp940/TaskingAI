import asyncio
import json
from typing import Dict

from fastapi import HTTPException
from tkhelper.utils import SSE_DONE_MSG
from tkhelper.error import ErrorCode

from app.models import Assistant, Chat
from .session import *
from .log import *
from .utils import *

import logging

logger = logging.getLogger(__name__)


def error_message(code, message: str):
    return {
        "object": "Error",
        "code": code,
        "message": message,
    }


class StatefulStreamSession(Session):
    def __init__(self, assistant: Assistant, chat: Chat, stream: bool, debug: bool, save_logs: bool):
        super().__init__(assistant, chat, save_logs, debug=debug)
        self.stream = stream

    async def stream_generate(self, system_prompt_variables: Dict):
        try:
            await self.prepare(
                stream=self.stream,
                system_prompt_variables=system_prompt_variables,
                retrieval_log=self.debug or self.save_logs,
            )
            await self.chat.lock()

            # Emit prep-phase TraceEvents via SSE when debug is enabled
            if self.debug:
                for trace_event in self.trace_events:
                    yield f"data: {json.dumps(trace_event.to_dict())}\n\n"
                    await asyncio.sleep(0.1)

            # Also emit legacy MessageGenerationLog for backward compatibility
            if self.debug:
                for log_dict in self.logs:
                    yield f"data: {json.dumps(log_dict)}\n\n"
                    await asyncio.sleep(0.1)

            function_calls_round_index = 0
            while True:
                chat_completion_function_calls_dict_list = None
                chat_completion_assistant_message_dict = None

                try:
                    chat_completion_event_id = generate_random_event_id()
                    if self.debug or self.save_logs:
                        chat_completion_input_log_dict = build_chat_completion_input_log_dict(
                            session_id=self.session_id,
                            event_id=chat_completion_event_id,
                            model=self.model,
                            messages=self.chat_completion_messages,
                            functions=self.chat_completion_functions,
                            status="started",
                        )
                        if self.save_logs:
                            self.logs.append(chat_completion_input_log_dict)
                        if self.debug:
                            yield f"data: {json.dumps(chat_completion_input_log_dict)}\n\n"

                    if self.stream:
                        usage_dict = None
                        logger.debug(f"completion start inference, stream = {self.stream}")
                        async for t, data in self.stream_inference(message_chunk_object_name="MessageChunk"):
                            logger.debug(f"completion streaming, {t}: {data}")
                            if t == MESSAGE_CHUNK:
                                yield f"data: {json.dumps(data)}\n\n"
                            elif t == MESSAGE:
                                chat_completion_assistant_message_dict = data
                                function_calls = data.get("function_calls")
                                if function_calls:
                                    chat_completion_function_calls_dict_list = function_calls
                            elif t == USAGE:
                                usage_dict = data
                            elif t == MESSAGE_RESPONSE:
                                pass
                            else:
                                raise MessageGenerationException("Unknown data type")

                        # Emit the chat_completion trace events after inference
                        if self.debug:
                            for trace_event in self.trace_events:
                                # Only emit events that were just added during this inference
                                if trace_event.event_id == chat_completion_event_id:
                                    yield f"data: {json.dumps(trace_event.to_dict())}\n\n"
                    else:
                        logger.debug(f"completion start inference, stream = {self.stream}")
                        (
                            chat_completion_assistant_message_dict,
                            chat_completion_function_calls_dict_list,
                            usage_dict,
                            _,
                        ) = await self.inference()

                        if self.debug:
                            for trace_event in self.trace_events:
                                if trace_event.event_id == chat_completion_event_id:
                                    yield f"data: {json.dumps(trace_event.to_dict())}\n\n"

                    if self.debug or self.save_logs:
                        chat_completion_output_log_dict = build_chat_completion_output_log_dict(
                            session_id=self.session_id,
                            event_id=chat_completion_event_id,
                            model=self.model,
                            message=chat_completion_assistant_message_dict,
                            usage=usage_dict,
                            status="completed",
                        )
                        if self.save_logs:
                            self.logs.append(chat_completion_output_log_dict)
                        if self.debug:
                            yield f"data: {json.dumps(chat_completion_output_log_dict)}\n\n"

                except MessageGenerationException as e:
                    raise e
                except HTTPException as e:
                    raise MessageGenerationException(f"Error occurred in chat completion inference. {e.detail}")
                except Exception as e:
                    logger.error(f"Error occurred in chat completion inference: {e}")
                    raise MessageGenerationException(f"Error occurred in chat completion inference")

                if chat_completion_function_calls_dict_list:
                    function_calls_round_index += 1
                    try:
                        logger.debug(f"FUNCTION_CALLS: tool_call = {chat_completion_function_calls_dict_list}")

                        # use_tool returns legacy MessageGenerationLog dicts
                        tool_action_call_logs = await self.use_tool(
                            function_calls=chat_completion_function_calls_dict_list,
                            round_index=function_calls_round_index,
                            log=self.debug or self.save_logs,
                        )
                        if self.debug:
                            for tool_action_call_log_dict in tool_action_call_logs:
                                logger.debug(f"tool_action_call_log_dict = {tool_action_call_log_dict}")
                                yield f"data: {json.dumps(tool_action_call_log_dict)}\n\n"

                        # run_tools yields TraceEvent dicts (stable structure)
                        if self.debug:
                            async for trace_event_dict in self.run_tools(
                                function_calls=chat_completion_function_calls_dict_list, log=True
                            ):
                                logger.debug(f"trace_event_dict = {trace_event_dict}")
                                yield f"data: {json.dumps(trace_event_dict)}\n\n"
                        else:
                            async for _ in self.run_tools(chat_completion_function_calls_dict_list):
                                pass

                    except MessageGenerationException as e:
                        logger.error(f"MessageGenerationException occurred in using the tools: {e}")
                        raise e

                    except Exception as e:
                        logger.error(f"Error occurred in using the tools: {e}")
                        raise MessageGenerationException(f"Error occurred in using the tools")

                else:
                    break

            if not chat_completion_assistant_message_dict:
                raise MessageGenerationException("Assistant message not generated.")

            # Build and emit usage summary TraceEvent
            usage_summary_trace = self.build_usage_summary_trace()
            if self.debug and usage_summary_trace:
                yield f"data: {json.dumps(usage_summary_trace.to_dict())}\n\n"

            # Persist trace_events along with the message when debug is enabled
            persistent_trace_events = self.get_trace_events_dicts()

            message = await self.create_assistant_message(
                content_text=chat_completion_assistant_message_dict["content"],
                logs=self.logs if self.save_logs else None,
                trace_events=persistent_trace_events,
            )
            message_dict = message.to_response_dict()
            yield f"data: {json.dumps(message_dict)}\n\n"
            yield SSE_DONE_MSG

        except MessageGenerationInvalidRequestException as e:
            err_dict = error_message(code=ErrorCode.INVALID_REQUEST, message=str(e))
            yield f"data: {json.dumps(err_dict)}\n\n"
            yield SSE_DONE_MSG

        except MessageGenerationException as e:
            err_dict = error_message(code=ErrorCode.GENERATION_ERROR, message=str(e))
            yield f"data: {json.dumps(err_dict)}\n\n"
            yield SSE_DONE_MSG

        except Exception as e:
            err_dict = error_message(
                code=ErrorCode.UNKNOWN_ERROR,
                message="Assistant message not generated due to an unknown error.",
            )
            logger.error(f"stream_generate: unknown error occurred in stream_generate {e}")
            yield f"data: {json.dumps(err_dict)}\n\n"
            yield SSE_DONE_MSG

        finally:
            await self.chat.unlock()
