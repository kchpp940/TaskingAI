import logging
import time
from fastapi import HTTPException
from abc import ABC
from typing import Dict, List, Optional, Tuple

from app.models import (
    MessageRole,
    MessageContent,
    Model,
    Assistant,
    Chat,
    Tool,
    ToolInput,
    ToolOutput,
    ChatCompletionAnyMessage,
    ChatCompletionFunction,
    ChatCompletionRole,
    RetrievalMethod,
    TraceEvent,
    TraceEventType,
    TraceEventStatus,
)

from app.operators import message_ops
from app.services.model import get_model
from app.services.tool import run_tools, fetch_tools
from app.services.inference.chat_completion import chat_completion, stream_chat_completion

from .utils import *
from .log import *

logger = logging.getLogger(__name__)

__all__ = ["Session", "MESSAGE_CHUNK", "MESSAGE", "USAGE", "MESSAGE_RESPONSE"]

MESSAGE_CHUNK = 2
MESSAGE = 3
USAGE = 4
MESSAGE_RESPONSE = 5


class Session(ABC):
    def __init__(self, assistant: Assistant, chat: Optional[Chat], save_logs: bool, debug: bool = False):
        # assistant
        self.assistant: Assistant = assistant
        self.chat: Optional[Chat] = chat

        # tools
        self.tool_dict: Dict[str, Tool] = {}
        self.tool_use_count: Dict[str, List[int]] = {}
        self.max_tool_use_count = 5

        # functions (input by stateless chat completion)
        self.function_names = []

        # retrievals
        self.retrieval_tool_name = None
        self.retrieval_collection_ids = None

        # model
        self.model: Model = None

        # chat memory
        self.chat_memory_messages = None

        # chat completion parameters
        self.system_prompt = None
        self.chat_completion_messages = None
        self.chat_completion_functions = []

        # id
        self.session_id = generate_random_session_id()

        # trace_id - unique identifier for the entire generation trace
        self.trace_id = generate_random_session_id()

        # usage
        self.total_input_tokens = 0
        self.total_output_tokens = 0

        # logs (legacy, for storage only)
        self.logs = []
        self.save_logs = save_logs

        # debug flag - controls TraceEvent collection and output
        self.debug = debug

        # stable trace events (only collected when debug=True)
        self.trace_events: List[TraceEvent] = []

    def _add_trace_event(self, event: TraceEvent):
        if self.debug:
            self.trace_events.append(event)

    async def create_assistant_message(
        self,
        content_text: str,
        logs: List[Dict] = None,
        trace_events: List[Dict] = None,
    ):
        if not self.chat:
            raise MessageGenerationInvalidRequestException("Chat is required to create a message.")
        create_dict = {
            "role": MessageRole.ASSISTANT.value,
            "content": MessageContent(text=content_text),
            "metadata": {},
        }
        if logs is not None:
            create_dict["logs"] = logs
        if trace_events is not None:
            create_dict["trace_events"] = trace_events
        return await message_ops.create(
            assistant_id=self.assistant.assistant_id,
            chat_id=self.chat.chat_id,
            create_dict=create_dict,
            check_max_count=False,
        )

    async def prepare(
        self,
        stream: bool,
        system_prompt_variables: Dict,
        retrieval_log: bool = False,
        chat_completion_messages: List[ChatCompletionAnyMessage] = None,
        chat_completion_input_functions: List[ChatCompletionFunction] = None,
    ):
        """
        Prepare the session for generating messages.
        Emits TraceEvents for memory_build, retrieval, and system_prompt_build.
        """

        if self.chat and chat_completion_messages is not None:
            raise ValueError("chat_completion_messages should be None when chat is not None.")

        if not self.chat and chat_completion_messages is None:
            raise ValueError("chat_completion_messages should not be None when chat is None.")

        if chat_completion_input_functions is not None and chat_completion_messages is None:
            raise ValueError("chat_completion_input_functions should be None when chat_completion_messages is None.")

        # check chat lock
        if self.chat and await self.chat.is_chat_locked():
            raise MessageGenerationInvalidRequestException(
                f"Chat {self.chat.chat_id} is locked. Please try again later."
            )

        # Get model
        try:
            self.model = await get_model(self.assistant.model_id)
        except Exception as e:
            raise MessageGenerationInvalidRequestException(f"Failed to load model {self.assistant.model_id}.")

        # Check model streaming
        if not self.model.allow_streaming() and stream:
            raise MessageGenerationInvalidRequestException(
                f"Assistant model {self.model.model_id} does not support streaming. "
            )

        # Get chat memory (with trace)
        t0 = time.monotonic()
        if self.chat:
            self.chat_memory_messages = await get_chat_memory_messages(self.chat)
            logger.debug(f"Chat memory: {self.chat_memory_messages}")
        else:
            self.chat_memory_messages = [
                message.model_dump()
                for message in chat_completion_messages
                if message.role != ChatCompletionRole.SYSTEM
            ]
        mem_duration = int((time.monotonic() - t0) * 1000)
        num_messages = len(self.chat_memory_messages) if self.chat_memory_messages else 0

        mem_trace = build_trace_memory_build(
            trace_id=self.trace_id,
            event_id=generate_random_event_id(),
            num_messages=num_messages,
            duration_ms=mem_duration,
        )
        self._add_trace_event(mem_trace)

        # Get tools
        if self.assistant.tools:
            try:
                tools = await fetch_tools(self.assistant.tools)
            except HTTPException as e:
                raise MessageGenerationInvalidRequestException(f"Failed to fetch all the assistant tools: {e.detail}")
            self.tool_dict.update({tool.function_name(): tool for tool in tools})
            self.chat_completion_functions = [tool.function_def for tool in tools]
            logger.debug(f"Tool functions fetched: {self.chat_completion_functions}")

        if chat_completion_input_functions:
            self.chat_completion_functions.extend(
                [function.model_dump() for function in chat_completion_input_functions]
            )
            self.function_names = [function.name for function in chat_completion_input_functions]

        # Get retrievals
        retrieval_doc = None
        retrieval_results = []

        if self.assistant.retrievals:
            self.retrieval_collection_ids = [
                retrieval.id for retrieval in self.assistant.retrievals if retrieval.type == "collection"
            ]

            if self.assistant.retrieval_configs.method != RetrievalMethod.FUNCTION_CALL:
                retrieval_query_text = get_system_prompt_retrieval_query_text(
                    chat_memory_messages=self.chat_memory_messages,
                    method=self.assistant.retrieval_configs.method,
                )
                if retrieval_query_text:
                    retrieval_event_id = generate_random_event_id()
                    retrieval_start_trace = build_trace_retrieval_start(
                        trace_id=self.trace_id,
                        event_id=retrieval_event_id,
                        query_text=retrieval_query_text,
                        top_k=self.assistant.retrieval_configs.top_k,
                    )
                    self._add_trace_event(retrieval_start_trace)

                    t1 = time.monotonic()
                    retrieval_error = None
                    try:
                        retrieval_doc, retrieval_results = await query_assistant_retrieval(
                            assistant=self.assistant,
                            query_text=retrieval_query_text,
                        )
                    except MessageGenerationException as e:
                        retrieval_error = str(e)
                        raise
                    finally:
                        retrieval_duration = int((time.monotonic() - t1) * 1000)
                        if retrieval_error:
                            retrieval_end_trace = build_trace_retrieval_error(
                                trace_id=self.trace_id,
                                event_id=retrieval_event_id,
                                error=retrieval_error,
                                duration_ms=retrieval_duration,
                            )
                        else:
                            retrieval_end_trace = build_trace_retrieval_complete(
                                trace_id=self.trace_id,
                                event_id=retrieval_event_id,
                                result_count=len(retrieval_results),
                                results=retrieval_results,
                                duration_ms=retrieval_duration,
                            )
                        self._add_trace_event(retrieval_end_trace)

                        # Also append legacy MessageGenerationLog for storage
                        if retrieval_log or self.save_logs:
                            if retrieval_error:
                                retrieval_log_output = build_retrieval_output_log_dict(
                                    session_id=self.session_id,
                                    event_id=retrieval_event_id,
                                    retrieval_result=[],
                                    duration_ms=retrieval_duration,
                                    status="error",
                                    error=retrieval_error,
                                )
                            else:
                                retrieval_log_output = build_retrieval_output_log_dict(
                                    session_id=self.session_id,
                                    event_id=retrieval_event_id,
                                    retrieval_result=retrieval_results,
                                    duration_ms=retrieval_duration,
                                    status="completed",
                                )
                            if self.save_logs:
                                self.logs.append(retrieval_log_output)

                            retrieval_log_input = build_retrieval_input_log_dict(
                                session_id=self.session_id,
                                event_id=retrieval_event_id,
                                query_text=retrieval_query_text,
                                top_k=self.assistant.retrieval_configs.top_k,
                            )
                            if self.save_logs:
                                self.logs.append(retrieval_log_input)

            else:
                retrieval_function = build_retrieval_function_dict(
                    existing_tool_names=list(self.tool_dict.keys()),
                    description=self.assistant.retrieval_configs.function_description,
                )
                self.retrieval_tool_name = retrieval_function["name"]
                self.chat_completion_functions.append(retrieval_function)

        # Build system prompt (with trace)
        t2 = time.monotonic()
        self.system_prompt = build_system_prompt(
            system_prompt_template=self.assistant.system_prompt_template,
            system_prompt_variables=system_prompt_variables or {},
            retrieval_doc=retrieval_doc,
        )

        if chat_completion_messages:
            user_system_prompt = [
                message.content for message in chat_completion_messages if message.role == ChatCompletionRole.SYSTEM
            ]
            if user_system_prompt:
                user_system_prompt = user_system_prompt[0]
                if "{{user_system_prompt}}" in self.system_prompt:
                    self.system_prompt = self.system_prompt.replace("{{user_system_prompt}}", user_system_prompt)
                else:
                    self.system_prompt += "\n\n" + user_system_prompt

        prompt_duration = int((time.monotonic() - t2) * 1000)
        prompt_trace = build_trace_system_prompt_build(
            trace_id=self.trace_id,
            event_id=generate_random_event_id(),
            prompt_length=len(self.system_prompt) if self.system_prompt else 0,
            has_retrieval=retrieval_doc is not None,
            duration_ms=prompt_duration,
        )
        self._add_trace_event(prompt_trace)

        self.chat_completion_messages = build_chat_completion_messages(
            system_prompt=self.system_prompt,
            history_messages=self.chat_memory_messages,
        )

    async def use_tool(self, function_calls, round_index: int, log=False):
        """
        use tool and count the use times
        :return: list of legacy MessageGenerationLog dicts if log is True
        """

        logs = []

        for function_call in function_calls:
            function_call_id = function_call["id"]
            event_id = function_call_id

            tool_name = function_call["name"]
            arguments = function_call.get("arguments") or {}

            if self.tool_use_count.get(tool_name) and not (round_index in self.tool_use_count[tool_name]):
                self.tool_use_count[tool_name].append(round_index)
                if len(self.tool_use_count[tool_name]) > self.max_tool_use_count:
                    self.chat_completion_functions = [
                        item for item in self.chat_completion_functions if item["name"] != tool_name
                    ]
                    raise MessageGenerationException(f"{tool_name} has been used for more than 5 rounds.")
            else:
                if tool_name in self.tool_dict or tool_name == self.retrieval_tool_name:
                    self.tool_use_count[tool_name] = [round_index]
                else:
                    raise MessageGenerationException(
                        f"The tool {tool_name} called by the model {self.model.model_id} "
                        f"({self.model.provider_id}/{self.model.provider_model_id}) does not exist."
                    )

            if log:
                if tool_name == self.retrieval_tool_name:
                    query_text = arguments.get("query_text")
                    retrieval_start_trace = build_trace_retrieval_start(
                        trace_id=self.trace_id,
                        event_id=event_id,
                        query_text=query_text or "",
                        top_k=self.assistant.retrieval_configs.top_k,
                    )
                    self._add_trace_event(retrieval_start_trace)

                    retrieval_input_log_dict = build_retrieval_input_log_dict(
                        session_id=self.session_id,
                        event_id=event_id,
                        query_text=query_text,
                        top_k=self.assistant.retrieval_configs.top_k,
                    )
                    logs.append(retrieval_input_log_dict)

        if self.save_logs:
            self.logs.extend(logs)
        return logs

    async def run_tools(self, function_calls, log=False):
        """
        Run tool and emit TraceEvents + legacy logs.
        :return: generator of TraceEvent dicts (stable) for SSE emission
        """
        self.chat_completion_messages.append({"role": "assistant", "function_calls": function_calls})

        tool_inputs = []

        for function_call in function_calls:
            function_call_id = function_call["id"]
            tool_name = function_call["name"]
            arguments = function_call.get("arguments") or {}

            if tool_name == self.retrieval_tool_name:
                query_text = arguments.get("query_text")
                if not query_text:
                    raise MessageGenerationException("Error occurred when retrieving related documents")

                t0 = time.monotonic()
                retrieval_error = None
                retrieval_content = None
                retrieval_results = []
                try:
                    retrieval_content, retrieval_results = await query_assistant_retrieval(
                        assistant=self.assistant,
                        query_text=query_text,
                    )
                except MessageGenerationException as e:
                    retrieval_error = str(e)
                    raise
                finally:
                    retrieval_duration = int((time.monotonic() - t0) * 1000)
                    if retrieval_error:
                        retrieval_end_trace = build_trace_retrieval_error(
                            trace_id=self.trace_id,
                            event_id=function_call_id,
                            error=retrieval_error,
                            duration_ms=retrieval_duration,
                        )
                    else:
                        retrieval_end_trace = build_trace_retrieval_complete(
                            trace_id=self.trace_id,
                            event_id=function_call_id,
                            result_count=len(retrieval_results),
                            results=retrieval_results,
                            duration_ms=retrieval_duration,
                        )
                    self._add_trace_event(retrieval_end_trace)

                    if log:
                        retrieval_log_output = build_retrieval_output_log_dict(
                            session_id=self.session_id,
                            event_id=function_call_id,
                            retrieval_result=retrieval_results if retrieval_error is None else [],
                            duration_ms=retrieval_duration,
                            status="error" if retrieval_error else "completed",
                            error=retrieval_error,
                        )
                        if self.save_logs:
                            self.logs.append(retrieval_log_output)
                        if not retrieval_error:
                            yield retrieval_end_trace.to_dict()

                if retrieval_content is not None:
                    self.chat_completion_messages.append(
                        {"role": "function", "content": retrieval_content, "id": function_call_id}
                    )

            else:
                tool_input = ToolInput(
                    type=self.tool_dict[tool_name].type,
                    tool_id=self.tool_dict[tool_name].tool_id,
                    tool_call_id=function_call_id,
                    arguments=arguments,
                )
                tool_inputs.append((tool_name, tool_input))

        if tool_inputs:
            for tool_name, tool_input in tool_inputs:
                tool_start_trace = build_trace_tool_start(
                    trace_id=self.trace_id,
                    event_id=tool_input.tool_call_id,
                    tool_type=tool_input.type,
                    tool_id=tool_input.tool_id,
                    name=tool_name,
                    arguments=tool_input.arguments,
                )
                self._add_trace_event(tool_start_trace)

                if log:
                    tool_input_log_dict = build_tool_input_log_dict(
                        session_id=self.session_id,
                        event_id=tool_input.tool_call_id,
                        tool_input=tool_input,
                    )
                    if self.save_logs:
                        self.logs.append(tool_input_log_dict)
                    yield tool_start_trace.to_dict()

            t1 = time.monotonic()
            tool_error = None
            try:
                tool_outputs: List[ToolOutput] = await run_tools([ti for _, ti in tool_inputs])
            except Exception as e:
                tool_error = str(e)
                raise
            finally:
                tool_duration = int((time.monotonic() - t1) * 1000)

            for tool_output in tool_outputs:
                self.chat_completion_messages.append(tool_output.to_function_message())

                if tool_error:
                    tool_end_trace = build_trace_tool_error(
                        trace_id=self.trace_id,
                        event_id=tool_output.tool_call_id,
                        tool_type=tool_output.type,
                        tool_id=tool_output.tool_id,
                        error=tool_error,
                        duration_ms=tool_duration,
                    )
                else:
                    tool_end_trace = build_trace_tool_complete(
                        trace_id=self.trace_id,
                        event_id=tool_output.tool_call_id,
                        tool_type=tool_output.type,
                        tool_id=tool_output.tool_id,
                        output=tool_output.content,
                        duration_ms=tool_duration,
                    )
                self._add_trace_event(tool_end_trace)

                if log:
                    tool_output_log_dict = build_tool_output_log_dict(
                        session_id=self.session_id,
                        event_id=tool_output.tool_call_id,
                        tool_output=tool_output,
                        duration_ms=tool_duration,
                        status="error" if tool_error else "completed",
                        error=tool_error,
                    )
                    if self.save_logs:
                        self.logs.append(tool_output_log_dict)
                    yield tool_end_trace.to_dict()

    async def inference(self) -> Tuple[Dict, List, Dict, Dict]:
        """
        Perform chat completion inference. Emits TraceEvents.
        :return: (assistant_message_dict, function_calls, usage_dict, completion_data_dict)
        """
        inference_event_id = generate_random_event_id()

        # start trace
        start_trace = build_trace_chat_completion_start(
            trace_id=self.trace_id,
            event_id=inference_event_id,
            model_id=self.model.model_id,
            provider_model_id=self.model.provider_model_id,
            message_count=len(self.chat_completion_messages),
            function_count=len(self.chat_completion_functions),
        )
        self._add_trace_event(start_trace)

        t0 = time.monotonic()
        try:
            completion_data = await chat_completion(
                model=self.model,
                messages=self.chat_completion_messages,
                functions=self.chat_completion_functions,
                configs={},
            )
        except Exception as e:
            duration = int((time.monotonic() - t0) * 1000)
            error_trace = build_trace_chat_completion_error(
                trace_id=self.trace_id,
                event_id=inference_event_id,
                error=str(e),
                duration_ms=duration,
            )
            self._add_trace_event(error_trace)
            raise

        duration = int((time.monotonic() - t0) * 1000)

        assistant_message_dict = completion_data["message"]
        function_calls = assistant_message_dict.get("function_calls")
        usage = completion_data.get("usage")
        self.total_input_tokens += usage.get("input_tokens", 0)
        self.total_output_tokens += usage.get("output_tokens", 0)

        complete_trace = build_trace_chat_completion_complete(
            trace_id=self.trace_id,
            event_id=inference_event_id,
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            has_function_calls=bool(function_calls),
            duration_ms=duration,
        )
        self._add_trace_event(complete_trace)

        return assistant_message_dict, function_calls, usage, completion_data

    async def stream_inference(self, message_chunk_object_name="MessageChunk"):
        """
        Streaming chat completion inference. Emits TraceEvents.
        """
        inference_event_id = generate_random_event_id()

        start_trace = build_trace_chat_completion_start(
            trace_id=self.trace_id,
            event_id=inference_event_id,
            model_id=self.model.model_id,
            provider_model_id=self.model.provider_model_id,
            message_count=len(self.chat_completion_messages),
            function_count=len(self.chat_completion_functions),
        )
        self._add_trace_event(start_trace)

        t0 = time.monotonic()
        stream_usage_dict = None
        function_calls_detected = False

        try:
            chunk_generator = await stream_chat_completion(
                model=self.model,
                messages=self.chat_completion_messages,
                functions=self.chat_completion_functions,
                configs={},
                chunk_handler=None,
            )
        except HTTPException as e:
            duration = int((time.monotonic() - t0) * 1000)
            error_trace = build_trace_chat_completion_error(
                trace_id=self.trace_id,
                event_id=inference_event_id,
                error=str(e.detail),
                duration_ms=duration,
            )
            self._add_trace_event(error_trace)
            logger.error(f"HTTPException occurred in streaming chat completion: {e}")
            raise MessageGenerationException(f"Error occurred in streaming chat completion.")

        try:
            async for chunk in chunk_generator:
                if chunk.get("object").lower() == "error":
                    raise MessageGenerationException(f"{chunk.get('message')}")

                assistant_message_dict = chunk.get("message")
                if assistant_message_dict:
                    if assistant_message_dict.get("function_calls"):
                        function_calls_detected = True
                    yield MESSAGE, assistant_message_dict
                    usage = chunk.get("usage")
                    if usage:
                        self.total_input_tokens += usage.get("input_tokens", 0)
                        self.total_output_tokens += usage.get("output_tokens", 0)
                        stream_usage_dict = usage
                        yield USAGE, usage
                    yield MESSAGE_RESPONSE, chunk

                else:
                    delta = chunk.get("delta")
                    if delta:
                        chunk.update({"object": message_chunk_object_name})
                        yield MESSAGE_CHUNK, chunk
        finally:
            duration = int((time.monotonic() - t0) * 1000)
            complete_trace = build_trace_chat_completion_complete(
                trace_id=self.trace_id,
                event_id=inference_event_id,
                input_tokens=stream_usage_dict.get("input_tokens", 0) if stream_usage_dict else 0,
                output_tokens=stream_usage_dict.get("output_tokens", 0) if stream_usage_dict else 0,
                has_function_calls=function_calls_detected,
                duration_ms=duration,
            )
            self._add_trace_event(complete_trace)

    def has_user_input_function_call(self, function_calls):
        if not function_calls:
            return False
        for function_call in function_calls:
            if function_call["name"] in self.function_names:
                return True
        return False

    def filter_user_function_calls(self, function_calls) -> Optional[List[Dict]]:
        results = [function_call for function_call in function_calls if function_call["name"] in self.function_names]
        return results if results else None

    def build_usage_summary_trace(self) -> Optional[TraceEvent]:
        """Build and store the final usage summary TraceEvent. Only when debug=True."""
        if not self.debug:
            return None
        trace = build_trace_usage_summary(
            trace_id=self.trace_id,
            total_input_tokens=self.total_input_tokens,
            total_output_tokens=self.total_output_tokens,
        )
        self._add_trace_event(trace)
        return trace

    def get_trace_events_dicts(self) -> Optional[List[Dict]]:
        """Return trace events as dicts only when debug=True, otherwise None."""
        if not self.debug:
            return None
        return [e.to_dict() for e in self.trace_events]
