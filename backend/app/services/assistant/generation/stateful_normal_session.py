import logging
from typing import Dict

from fastapi import HTTPException
from tkhelper.error import ErrorCode, raise_http_error

from app.models import Assistant, Chat

from .session import Session
from .utils import *
from .log import *
from .result_builder import MessageFinalizationHelper

logger = logging.getLogger(__name__)


class StatefulNormalSession(Session):
    def __init__(self, assistant: Assistant, chat: Chat, save_logs: bool):
        super().__init__(assistant, chat, save_logs)

    async def generate(self, system_prompt_variables: Dict):
        try:
            await self.prepare(
                stream=False,
                system_prompt_variables=system_prompt_variables,
                retrieval_log=self.save_logs,
            )
            await self.chat.lock()

            function_calls_round_index = 0
            inference_round_index = 0

            while True:
                try:
                    inference_round_index += 1
                    chat_completion_event_id = generate_random_event_id()
                    self.result_builder.append_chat_completion_input_log(
                        event_id=chat_completion_event_id, save=self.save_logs
                    )

                    (
                        assistant_message_dict,
                        function_calls,
                        usage_dict,
                        completion_data,
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
                    )

                except HTTPException as e:
                    raise MessageGenerationException(f"Error occurred in chat completion inference. {e.detail}")
                except Exception as e:
                    raise MessageGenerationException(f"Error occurred in chat completion inference")

                logger.debug(f"chat_completion_assistant_message = {assistant_message_dict}")
                logger.debug(f"chat_completion_function_calls_dict_list = {function_calls}")

                if function_calls:
                    function_calls_round_index += 1
                    try:
                        await self.result_builder.process_tool_calls(
                            function_calls,
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

            return await MessageFinalizationHelper.build_stateful_normal_response(self.result)

        except MessageGenerationInvalidRequestException as e:
            logger.error(f"StatefulNormalSession.generate: HTTPException error = {e}")
            raise_http_error(ErrorCode.INVALID_REQUEST, message=str(e))

        except MessageGenerationException as e:
            logger.error(f"StatefulNormalSession.generate: MessageGenerationException error = {e}")
            raise_http_error(ErrorCode.GENERATION_ERROR, message=str(e))

        except Exception as e:
            logger.error(f"StatefulNormalSession.generate: Exception error = {e}")
            raise_http_error(
                ErrorCode.INTERNAL_SERVER_ERROR, message=str("Assistant message not generated due to an unknown error.")
            )

        finally:
            await self.chat.unlock()
