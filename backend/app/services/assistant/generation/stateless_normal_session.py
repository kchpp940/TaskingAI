from fastapi import HTTPException
from typing import List
from tkhelper.error import raise_http_error, ErrorCode
import logging

from app.schemas.model.chat_completion import ChatCompletionResponse
from app.models.inference import *
from app.models import Assistant

from .session import Session
from .utils import *
from .log import *

logger = logging.getLogger(__name__)


class StatelessNormalSession(Session):
    def __init__(self, assistant: Assistant, save_logs: bool):
        super().__init__(assistant, None, save_logs)

    async def generate(
        self,
        messages: List[ChatCompletionAnyMessage],
        functions: List[ChatCompletionFunction],
    ) -> ChatCompletionResponse:
        try:
            await self.prepare(
                stream=False,
                system_prompt_variables={},
                retrieval_log=self.save_logs,
                chat_completion_messages=messages,
                chat_completion_input_functions=functions,
            )
            function_calls_round_index = 0

            while True:
                try:
                    chat_completion_event_id = generate_random_event_id()
                    if self.save_logs:
                        chat_completion_input_log_dict = build_chat_completion_input_log_dict(
                            session_id=self.session_id,
                            event_id=chat_completion_event_id,
                            model=self.model,
                            messages=self.chat_completion_messages,
                            functions=self.chat_completion_functions,
                            status="started",
                        )
                        self.logs.append(chat_completion_input_log_dict)

                    (
                        chat_completion_assistant_message_dict,
                        chat_completion_function_calls_dict_list,
                        usage_dict,
                        response_dict,
                    ) = await self.inference()

                    if self.save_logs:
                        chat_completion_output_log_dict = build_chat_completion_output_log_dict(
                            session_id=self.session_id,
                            event_id=chat_completion_event_id,
                            model=self.model,
                            message=chat_completion_assistant_message_dict,
                            usage=usage_dict,
                            status="completed",
                        )
                        self.logs.append(chat_completion_output_log_dict)

                except HTTPException as e:
                    raise MessageGenerationException(f"Error occurred in chat completion inference. {e.detail}")
                except Exception as e:
                    raise MessageGenerationException(f"Error occurred in chat completion inference")

                logger.debug(f"chat_completion_assistant_message = {chat_completion_assistant_message_dict}")
                logger.debug(f"chat_completion_function_calls_dict_list = {chat_completion_function_calls_dict_list}")

                if chat_completion_function_calls_dict_list:
                    filtered_user_function_calls = self.filter_user_function_calls(
                        chat_completion_function_calls_dict_list
                    )
                    if filtered_user_function_calls:
                        response_dict["message"]["function_calls"] = filtered_user_function_calls
                        break

                    function_calls_round_index += 1
                    try:
                        logger.debug(f"FUNCTION_CALLS: tool_call = {chat_completion_function_calls_dict_list}")

                        await self.use_tool(
                            chat_completion_function_calls_dict_list,
                            round_index=function_calls_round_index,
                            log=self.save_logs,
                        )
                        async for _ in self.run_tools(chat_completion_function_calls_dict_list, log=self.save_logs):
                            pass
                    except MessageGenerationException as e:
                        logger.error(f"MessageGenerationException occurred in using the tools: {e}")
                        raise e
                    except Exception as e:
                        logger.error(f"Error occurred in using the tools: {e}")
                        raise MessageGenerationException(f"Error occurred in using the tools")

                else:
                    break

            response_dict["usage"]["input_tokens"] = self.total_input_tokens
            response_dict["usage"]["output_tokens"] = self.total_output_tokens

            # Build usage summary trace
            self.build_usage_summary_trace()

            # Attach trace_events to response
            response_dict["trace_events"] = self.get_trace_events_dicts()

            return ChatCompletionResponse(data=response_dict)

        except MessageGenerationInvalidRequestException as e:
            logger.error(f"StatelessNormalSession.generate: HTTPException error = {e}")
            raise_http_error(ErrorCode.INVALID_REQUEST, message=str(e))

        except MessageGenerationException as e:
            logger.error(f"StatelessNormalSession.generate: MessageGenerationException error = {e}")
            raise_http_error(ErrorCode.GENERATION_ERROR, message=str(e))

        except Exception as e:
            logger.error(f"StatelessNormalSession.generate: Exception error = {e}")
            raise_http_error(
                ErrorCode.INTERNAL_SERVER_ERROR, message=str("Assistant message not generated due to an unknown error.")
            )
