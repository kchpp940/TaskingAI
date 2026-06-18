import asyncio
import json
from typing import Dict

from fastapi import HTTPException
from tkhelper.error import ErrorCode

from app.models import Assistant, Chat
from .session import *
from .log import *
from .utils import *
from .result_builder import MessageFinalizationHelper

import logging

logger = logging.getLogger(__name__)


class StatefulStreamSession(Session):
    def __init__(self, assistant: Assistant, chat: Chat, stream: bool, debug: bool, save_logs: bool):
        super().__init__(assistant, chat, save_logs)
        self.stream = stream
        self.debug = debug

    async def stream_generate(self, system_prompt_variables: Dict):
        try:
            await self.prepare(
                stream=self.stream,
                system_prompt_variables=system_prompt_variables,
                retrieval_log=self.debug or self.save_logs,
            )
            await self.chat.lock()

            if self.debug and self.logs:
                for log_dict in self.logs:
                    yield f"data: {json.dumps(log_dict)}\n\n"
                    await asyncio.sleep(0.1)

            function_calls_round_index = 0
            while True:
                chat_completion_function_calls_dict_list = None
                chat_completion_assistant_message_dict = None

                try:
                    chat_completion_event_id = generate_random_event_id()

                    input_log = self.result_builder.append_chat_completion_input_log(
                        event_id=chat_completion_event_id, save=self.save_logs
                    )
                    if self.debug:
                        yield f"data: {json.dumps(input_log)}\n\n"

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
                    else:
                        logger.debug(f"completion start inference, stream = {self.stream}")
                        (
                            chat_completion_assistant_message_dict,
                            chat_completion_function_calls_dict_list,
                            usage_dict,
                            _,
                        ) = await self.inference()

                    output_log = self.result_builder.append_chat_completion_output_log(
                        event_id=chat_completion_event_id,
                        assistant_message_dict=chat_completion_assistant_message_dict,
                        usage_dict=usage_dict,
                        save=self.save_logs,
                    )
                    if self.debug:
                        yield f"data: {json.dumps(output_log)}\n\n"

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

                        if self.debug:
                            async for sse_event in self.result_builder.process_tool_calls_with_debug(
                                function_calls=chat_completion_function_calls_dict_list,
                                round_index=function_calls_round_index,
                                log=self.debug or self.save_logs,
                            ):
                                yield sse_event
                        else:
                            await self.result_builder.process_tool_calls(
                                function_calls=chat_completion_function_calls_dict_list,
                                round_index=function_calls_round_index,
                                log=self.save_logs,
                            )

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

            async for event in MessageFinalizationHelper.build_stateful_stream_events(
                session=self,
                content_text=chat_completion_assistant_message_dict["content"],
                logs=self.logs if self.save_logs else None,
            ):
                yield event

        except MessageGenerationInvalidRequestException as e:
            async for event in MessageFinalizationHelper.build_sse_error(ErrorCode.INVALID_REQUEST, str(e)):
                yield event

        except MessageGenerationException as e:
            async for event in MessageFinalizationHelper.build_sse_error(ErrorCode.GENERATION_ERROR, str(e)):
                yield event

        except Exception as e:
            logger.error(f"stream_generate: unknown error occurred in stream_generate {e}")
            async for event in MessageFinalizationHelper.build_sse_error(
                ErrorCode.UNKNOWN_ERROR, "Assistant message not generated due to an unknown error."
            ):
                yield event

        finally:
            await self.chat.unlock()
