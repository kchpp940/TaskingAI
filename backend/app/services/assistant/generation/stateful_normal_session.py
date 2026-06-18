from fastapi import HTTPException
from typing import Dict, Any, Optional
from tkhelper.error import raise_http_error, ErrorCode
from tkhelper.utils import current_timestamp_int_milliseconds
import logging

from app.models import Assistant, Chat, Message

from .session import Session
from .utils import *
from .log import *

logger = logging.getLogger(__name__)


class StatefulNormalSession(Session):
    def __init__(self, assistant: Assistant, chat: Chat, save_logs: bool, debug: bool = False):
        super().__init__(assistant, chat, save_logs or debug)
        self.debug = debug

    async def generate(self, system_prompt_variables: Dict):
        error_event_id = None
        error_event = None
        try:
            await self.prepare(
                stream=False,
                system_prompt_variables=system_prompt_variables,
                retrieval_log=self.save_logs,
            )
            await self.chat.lock()

            function_calls_round_index = 0

            while True:
                chat_completion_event_id = None
                try:
                    chat_completion_event_id = generate_random_event_id()
                    # append chat completion input log
                    if self.save_logs:
                        chat_completion_input_log_dict = build_chat_completion_input_log_dict(
                            session_id=self.session_id,
                            event_id=chat_completion_event_id,
                            model=self.model,
                            messages=self.chat_completion_messages,
                            functions=self.chat_completion_functions,
                        )
                        self.logs.append(chat_completion_input_log_dict)

                    # inference
                    (
                        chat_completion_assistant_message_dict,
                        chat_completion_function_calls_dict_list,
                        usage_dict,
                        _,
                    ) = await self.inference(event_id=chat_completion_event_id)

                    # append chat completion output log
                    if self.save_logs:
                        chat_completion_output_log_dict = build_chat_completion_output_log_dict(
                            session_id=self.session_id,
                            event_id=chat_completion_event_id,
                            model=self.model,
                            message=chat_completion_assistant_message_dict,
                            usage=usage_dict,
                            duration_ms=self.trace_collector.duration(chat_completion_event_id),
                        )
                        self.logs.append(chat_completion_output_log_dict)
                    self.trace_collector.clear(chat_completion_event_id)

                except HTTPException as e:
                    if self.save_logs and chat_completion_event_id:
                        error_log = build_trace_error_log_dict(
                            session_id=self.session_id,
                            event_id=chat_completion_event_id,
                            event="chat_completion",
                            error_message=str(e.detail),
                            error_type="HTTPException",
                            duration_ms=self.trace_collector.duration(chat_completion_event_id),
                        )
                        self.logs.append(error_log)
                        self.trace_collector.clear(chat_completion_event_id)
                    raise MessageGenerationException(f"Error occurred in chat completion inference. {e.detail}")
                except Exception as e:
                    if self.save_logs and chat_completion_event_id:
                        error_log = build_trace_error_log_dict(
                            session_id=self.session_id,
                            event_id=chat_completion_event_id,
                            event="chat_completion",
                            error_message=str(e),
                            error_type=type(e).__name__,
                            duration_ms=self.trace_collector.duration(chat_completion_event_id),
                        )
                        self.logs.append(error_log)
                        self.trace_collector.clear(chat_completion_event_id)
                    raise MessageGenerationException(f"Error occurred in chat completion inference")

                logger.debug(f"chat_completion_assistant_message = {chat_completion_assistant_message_dict}")
                logger.debug(f"chat_completion_function_calls_dict_list = {chat_completion_function_calls_dict_list}")

                if chat_completion_function_calls_dict_list:
                    function_calls_round_index += 1
                    tool_error_event_id = None
                    try:
                        await self.use_tool(
                            chat_completion_function_calls_dict_list,
                            round_index=function_calls_round_index,
                            log=self.save_logs,
                        )
                        async for _ in self.run_tools(chat_completion_function_calls_dict_list, log=self.save_logs):
                            pass
                    except MessageGenerationException as e:
                        logger.error(f"MessageGenerationException occurred in using the tools: {e}")
                        error_event_id = generate_random_event_id()
                        error_event = "tool_call"
                        if self.save_logs:
                            error_log = build_trace_error_log_dict(
                                session_id=self.session_id,
                                event_id=error_event_id,
                                event="tool_call",
                                error_message=str(e),
                                error_type=type(e).__name__,
                            )
                            self.logs.append(error_log)
                        raise e
                    except Exception as e:
                        logger.error(f"Error occurred in using the tools: {e}")
                        error_event_id = generate_random_event_id()
                        error_event = "tool_call"
                        if self.save_logs:
                            error_log = build_trace_error_log_dict(
                                session_id=self.session_id,
                                event_id=error_event_id,
                                event="tool_call",
                                error_message=str(e),
                                error_type=type(e).__name__,
                            )
                            self.logs.append(error_log)
                        raise MessageGenerationException(f"Error occurred in using the tools")

                else:
                    break

            if self.save_logs:
                total_duration = current_timestamp_int_milliseconds() - self.session_start_timestamp
                usage_summary_log = build_usage_summary_log_dict(
                    session_id=self.session_id,
                    event_id=generate_random_event_id(),
                    total_input_tokens=self.total_input_tokens,
                    total_output_tokens=self.total_output_tokens,
                    total_duration_ms=total_duration,
                )
                self.logs.append(usage_summary_log)

            message = await self.create_assistant_message(
                content_text=chat_completion_assistant_message_dict["content"],
                logs=self.logs if self.save_logs else None,
            )
            return {
                "message": message,
                "trace": self.logs if self.debug else None,
            }

        except MessageGenerationInvalidRequestException as e:
            logger.error(f"StatefulNormalSession.generate: HTTPException error = {e}")
            if self.save_logs and not error_event_id:
                error_event_id = generate_random_event_id()
                error_log = build_trace_error_log_dict(
                    session_id=self.session_id,
                    event_id=error_event_id,
                    event="prepare",
                    error_message=str(e),
                    error_type="InvalidRequest",
                )
                self.logs.append(error_log)
            raise_http_error(ErrorCode.INVALID_REQUEST, message=str(e))

        except MessageGenerationException as e:
            logger.error(f"StatefulNormalSession.generate: MessageGenerationException error = {e}")
            if self.save_logs and not error_event_id:
                error_event_id = generate_random_event_id()
                error_log = build_trace_error_log_dict(
                    session_id=self.session_id,
                    event_id=error_event_id,
                    event="generation",
                    error_message=str(e),
                    error_type="GenerationError",
                )
                self.logs.append(error_log)
            raise_http_error(ErrorCode.GENERATION_ERROR, message=str(e))

        except Exception as e:
            logger.error(f"StatefulNormalSession.generate: Exception error = {e}")
            if self.save_logs and not error_event_id:
                error_event_id = generate_random_event_id()
                error_log = build_trace_error_log_dict(
                    session_id=self.session_id,
                    event_id=error_event_id,
                    event="generation",
                    error_message=str(e),
                    error_type=type(e).__name__,
                )
                self.logs.append(error_log)
            raise_http_error(
                ErrorCode.INTERNAL_SERVER_ERROR, message=str("Assistant message not generated due to an unknown error.")
            )

        finally:
            await self.chat.unlock()
