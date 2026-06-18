import json
from typing import List, Union
from fastapi import HTTPException

from tkhelper.error import ErrorCode

from app.models.inference import *
from app.models import Assistant

from .session import *
from .utils import *
from .log import *
from .utils import generate_random_event_id
from .result_builder import MessageFinalizationHelper

import logging

logger = logging.getLogger(__name__)


class StatelessStreamSession(Session):
    def __init__(self, assistant: Assistant, save_logs: bool, yield_dict: bool = False):
        super().__init__(assistant, None, save_logs)
        self.stream = True
        self.yield_dict = yield_dict

    async def stream_generate(
        self,
        messages: List[
            Union[
                ChatCompletionFunctionMessage,
                ChatCompletionAssistantMessage,
                ChatCompletionUserMessage,
                ChatCompletionSystemMessage,
            ]
        ],
        functions: List[ChatCompletionFunction],
    ):
        try:
            await self.prepare(
                stream=self.stream,
                system_prompt_variables={},
                retrieval_log=self.save_logs,
                chat_completion_messages=messages,
                chat_completion_input_functions=functions,
            )

            function_calls_round_index = 0
            inference_round_index = 0
            while True:
                function_calls = None
                assistant_message_dict = None
                usage_dict = None
                response_dict = None

                try:
                    inference_round_index += 1
                    chat_completion_event_id = generate_random_event_id()
                    self.result_builder.append_chat_completion_input_log(
                        event_id=chat_completion_event_id, save=self.save_logs
                    )

                    if self.stream:
                        logger.debug(f"completion start inference, stream = {self.stream}")
                        async for t, data in self.stream_inference(message_chunk_object_name="ChatCompletionChunk"):
                            logger.debug(f"completion streaming, {t}: {data}")
                            if t == MESSAGE_CHUNK:
                                if self.yield_dict:
                                    yield data
                                else:
                                    yield f"data: {json.dumps(data)}\n\n"
                            elif t == MESSAGE:
                                assistant_message_dict = data
                                function_calls = data.get("function_calls")
                            elif t == USAGE:
                                usage_dict = data
                            elif t == MESSAGE_RESPONSE:
                                response_dict = data
                            else:
                                raise MessageGenerationException("Unknown data type")
                    else:
                        logger.debug(f"completion start inference, stream = {self.stream}")
                        (
                            assistant_message_dict,
                            function_calls,
                            usage_dict,
                            response_dict,
                        ) = await self.inference()

                    self.result_builder.append_chat_completion_output_log(
                        event_id=chat_completion_event_id,
                        assistant_message_dict=assistant_message_dict,
                        usage_dict=usage_dict,
                        save=self.save_logs,
                    )

                    ir = self.result_builder.begin_inference_round(
                        round_index=inference_round_index, event_id=chat_completion_event_id
                    )
                    self.result_builder.complete_inference_round(
                        ir=ir,
                        assistant_message_dict=assistant_message_dict,
                        function_calls=function_calls,
                        usage_dict=usage_dict,
                        response_dict=response_dict,
                    )

                except MessageGenerationException as e:
                    raise e
                except HTTPException as e:
                    logger.error(f"HTTPException occurred in chat completion inference: {e}")
                    raise MessageGenerationException(f"Error occurred in chat completion inference. {e.detail}")
                except Exception as e:
                    logger.error(f"Error occurred in chat completion inference: {e}")
                    raise MessageGenerationException(f"Error occurred in chat completion inference")

                if function_calls:
                    if self.result.has_user_function_calls:
                        break

                    function_calls_round_index += 1
                    try:
                        logger.debug(f"FUNCTION_CALLS: tool_call = {function_calls}")

                        await self.result_builder.process_tool_calls(
                            function_calls=function_calls,
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

            if self.result.final_assistant_message_dict is None:
                raise MessageGenerationException("Assistant message not generated.")

            if self.result.final_response_dict is None:
                raise MessageGenerationException("Assistant message not generated.")

            async for event in MessageFinalizationHelper.build_stateless_stream_events(
                self.result, yield_dict=self.yield_dict
            ):
                yield event

        except MessageGenerationInvalidRequestException as e:
            async for event in MessageFinalizationHelper.build_sse_error(
                ErrorCode.INVALID_REQUEST, str(e), yield_dict=self.yield_dict
            ):
                yield event

        except MessageGenerationException as e:
            async for event in MessageFinalizationHelper.build_sse_error(
                ErrorCode.GENERATION_ERROR, str(e), yield_dict=self.yield_dict
            ):
                yield event

        except Exception as e:
            logger.error(f"stream_generate: unknown error occurred in stream_generate {e}")
            async for event in MessageFinalizationHelper.build_sse_error(
                ErrorCode.UNKNOWN_ERROR,
                "Assistant message not generated due to an unknown error.",
                yield_dict=self.yield_dict,
            ):
                yield event
