import logging
from fastapi import HTTPException
from abc import ABC
from typing import Dict, List, Optional, Tuple

from app.models import (
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
)

from app.services.model import get_model
from app.services.tool import run_tools, fetch_tools
from app.services.inference.chat_completion import chat_completion, stream_chat_completion

from .utils import *
from .log import *
from .result_builder import GenerationResult, GenerationResultBuilder

logger = logging.getLogger(__name__)

__all__ = [
    "Session",
    "MESSAGE_CHUNK",
    "MESSAGE",
    "USAGE",
    "MESSAGE_RESPONSE",
    "TOOL_RUN_TYPE_LOG",
    "TOOL_RUN_TYPE_TOOL_OUTPUT",
    "TOOL_RUN_TYPE_RETRIEVAL_RESULT",
]

MESSAGE_CHUNK = 2
MESSAGE = 3
USAGE = 4
MESSAGE_RESPONSE = 5

TOOL_RUN_TYPE_LOG = "log"
TOOL_RUN_TYPE_TOOL_OUTPUT = "tool_output"
TOOL_RUN_TYPE_RETRIEVAL_RESULT = "retrieval_result"


class Session(ABC):
    def __init__(self, assistant: Assistant, chat: Optional[Chat], save_logs: bool):
        self.assistant: Assistant = assistant
        self.chat: Optional[Chat] = chat

        self.tool_dict: Dict[str, Tool] = {}
        self.tool_use_count: Dict[str, List[int]] = {}
        self.max_tool_use_count = 5

        self.function_names = []

        self.retrieval_tool_name = None
        self.retrieval_collection_ids = None

        self.model: Model = None

        self.chat_memory_messages = None

        self.system_prompt = None
        self.chat_completion_messages = None
        self.chat_completion_functions = []

        self.session_id = generate_random_session_id()

        self.save_logs = save_logs

        self.trace_collector = TraceCollector()
        self.session_start_timestamp = current_timestamp_int_milliseconds()

        self.result: GenerationResult = GenerationResult(
            session_id=self.session_id,
            assistant_id=assistant.assistant_id,
            chat_id=chat.chat_id if chat else None,
        )
        self.logs = self.result.logs
        self.result_builder = GenerationResultBuilder(self, self.result)

    @property
    def total_input_tokens(self) -> int:
        return self.result.total_input_tokens

    @total_input_tokens.setter
    def total_input_tokens(self, value: int):
        self.result.total_input_tokens = value

    @property
    def total_output_tokens(self) -> int:
        return self.result.total_output_tokens

    @total_output_tokens.setter
    def total_output_tokens(self, value: int):
        self.result.total_output_tokens = value

    async def prepare(
        self,
        stream: bool,
        system_prompt_variables: Dict,
        retrieval_log: bool = False,
        chat_completion_messages: List[ChatCompletionAnyMessage] = None,
        chat_completion_input_functions: List[ChatCompletionFunction] = None,
    ):
        if self.chat and chat_completion_messages is not None:
            raise ValueError("chat_completion_messages should be None when chat is not None.")

        if not self.chat and chat_completion_messages is None:
            raise ValueError("chat_completion_messages should not be None when chat is None.")

        if chat_completion_input_functions is not None and chat_completion_messages is None:
            raise ValueError("chat_completion_input_functions should be None when chat_completion_messages is None.")

        if self.chat and await self.chat.is_chat_locked():
            raise MessageGenerationInvalidRequestException(
                f"Chat {self.chat.chat_id} is locked. Please try again later."
            )

        try:
            self.model = await get_model(self.assistant.model_id)
        except Exception as e:
            raise MessageGenerationInvalidRequestException(f"Failed to load model {self.assistant.model_id}.")

        if not self.model.allow_streaming() and stream:
            raise MessageGenerationInvalidRequestException(
                f"Assistant model {self.model.model_id} does not support streaming. "
            )

        memory_event_id = generate_random_event_id()
        self.trace_collector.start(memory_event_id)
        self.result_builder.start_trace(
            event_id=memory_event_id,
            event="memory",
            input_summary="loading chat memory",
            metadata={"has_chat": self.chat is not None},
        )
        if retrieval_log:
            memory_log_input = build_trace_start_log_dict(
                session_id=self.session_id,
                event_id=memory_event_id,
                event="memory",
                content={
                    "has_chat": self.chat is not None,
                },
                input_summary="loading chat memory",
            )
            self.logs.append(memory_log_input)

        if self.chat:
            self.chat_memory_messages = await get_chat_memory_messages(self.chat)
            logger.debug(f"Chat memory: {self.chat_memory_messages}")
        else:
            self.chat_memory_messages = [
                message.model_dump()
                for message in chat_completion_messages
                if message.role != ChatCompletionRole.SYSTEM
            ]

        if retrieval_log:
            memory_log_output = build_trace_end_log_dict(
                session_id=self.session_id,
                event_id=memory_event_id,
                event="memory",
                content={
                    "num_messages": len(self.chat_memory_messages),
                },
                duration_ms=self.trace_collector.duration(memory_event_id),
                input_summary=f"{len(self.chat_memory_messages)} memory messages loaded",
            )
            self.logs.append(memory_log_output)
        self.result_builder.end_trace(
            event_id=memory_event_id,
            event="memory",
            input_summary=f"{len(self.chat_memory_messages)} memory messages loaded",
            metadata={"num_messages": len(self.chat_memory_messages)},
        )
        self.trace_collector.clear(memory_event_id)

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

        retrieval_doc = None

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
                    self.trace_collector.start(retrieval_event_id)
                    self.result_builder.start_trace(
                        event_id=retrieval_event_id,
                        event="retrieval",
                        input_summary=f"retrieving with top_k={self.assistant.retrieval_configs.top_k}",
                        metadata={
                            "top_k": self.assistant.retrieval_configs.top_k,
                            "method": self.assistant.retrieval_configs.method.value,
                        },
                    )
                    if retrieval_log:
                        retrieval_log_input = build_retrieval_input_log_dict(
                            session_id=self.session_id,
                            event_id=retrieval_event_id,
                            query_text=retrieval_query_text,
                            top_k=self.assistant.retrieval_configs.top_k,
                        )
                        self.logs.append(retrieval_log_input)

                    retrieval_doc, retrieval_results = await query_assistant_retrieval(
                        assistant=self.assistant,
                        query_text=retrieval_query_text,
                    )

                    self.result.retrieval_results.extend(retrieval_results)

                    if retrieval_log:
                        retrieval_log_output = build_retrieval_output_log_dict(
                            session_id=self.session_id,
                            event_id=retrieval_event_id,
                            retrieval_result=retrieval_results,
                            duration_ms=self.trace_collector.duration(retrieval_event_id),
                        )
                        self.logs.append(retrieval_log_output)
                    self.result_builder.end_trace(
                        event_id=retrieval_event_id,
                        event="retrieval",
                        input_summary=f"{len(retrieval_results)} retrieval results",
                        metadata={"num_results": len(retrieval_results)},
                    )
                    self.trace_collector.clear(retrieval_event_id)

            else:
                retrieval_function = build_retrieval_function_dict(
                    existing_tool_names=list(self.tool_dict.keys()),
                    description=self.assistant.retrieval_configs.function_description,
                )
                self.retrieval_tool_name = retrieval_function["name"]
                self.chat_completion_functions.append(retrieval_function)

        prompt_event_id = generate_random_event_id()
        self.trace_collector.start(prompt_event_id)
        self.result_builder.start_trace(
            event_id=prompt_event_id,
            event="prompt_build",
            input_summary="building system prompt",
            metadata={
                "num_variables": len(system_prompt_variables or {}),
                "has_retrieval_doc": retrieval_doc is not None,
            },
        )
        if retrieval_log:
            prompt_log_input = build_trace_start_log_dict(
                session_id=self.session_id,
                event_id=prompt_event_id,
                event="prompt_build",
                content={
                    "num_variables": len(system_prompt_variables or {}),
                    "has_retrieval_doc": retrieval_doc is not None,
                },
                input_summary="building system prompt",
            )
            self.logs.append(prompt_log_input)

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

        self.chat_completion_messages = build_chat_completion_messages(
            system_prompt=self.system_prompt,
            history_messages=self.chat_memory_messages,
        )

        if retrieval_log:
            prompt_log_output = build_trace_end_log_dict(
                session_id=self.session_id,
                event_id=prompt_event_id,
                event="prompt_build",
                content={
                    "prompt_length": len(self.system_prompt),
                    "num_messages": len(self.chat_completion_messages),
                },
                duration_ms=self.trace_collector.duration(prompt_event_id),
                input_summary=f"prompt built, {len(self.chat_completion_messages)} messages ready",
            )
            self.logs.append(prompt_log_output)
        self.result_builder.end_trace(
            event_id=prompt_event_id,
            event="prompt_build",
            input_summary=f"prompt built, {len(self.chat_completion_messages)} messages ready",
            metadata={
                "prompt_length": len(self.system_prompt),
                "num_messages": len(self.chat_completion_messages),
            },
        )
        self.trace_collector.clear(prompt_event_id)

    async def use_tool(self, function_calls, round_index: int, log=False):
        logs = []

        tool_use_event_id = f"tool_use_round_{round_index}"
        self.trace_collector.start(tool_use_event_id)
        self.result_builder.start_trace(
            event_id=tool_use_event_id,
            event="tool_use",
            input_summary=f"validate {len(function_calls)} function call(s)",
            metadata={
                "round_index": round_index,
                "num_function_calls": len(function_calls),
                "function_names": [fc.get("name") for fc in function_calls],
            },
        )

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
                    retrieval_input_log_dict = build_retrieval_input_log_dict(
                        session_id=self.session_id,
                        event_id=event_id,
                        query_text=query_text,
                        top_k=self.assistant.retrieval_configs.top_k,
                    )
                    logs.append(retrieval_input_log_dict)

        self.result_builder.end_trace(
            event_id=tool_use_event_id,
            event="tool_use",
            input_summary=f"validated {len(function_calls)} function call(s)",
            metadata={
                "round_index": round_index,
                "num_function_calls": len(function_calls),
            },
        )
        self.trace_collector.clear(tool_use_event_id)

        if self.save_logs:
            self.logs.extend(logs)
        return logs

    async def run_tools(self, function_calls, log=False):
        self.chat_completion_messages.append({"role": "assistant", "function_calls": function_calls})

        tool_run_event_id = f"tool_run_{generate_random_event_id()[:8]}"
        self.trace_collector.start(tool_run_event_id)
        self.result_builder.start_trace(
            event_id=tool_run_event_id,
            event="tool_run",
            input_summary=f"executing {len(function_calls)} tool call(s)",
            metadata={
                "num_function_calls": len(function_calls),
                "function_names": [fc.get("name") for fc in function_calls],
            },
        )

        tool_inputs = []

        for function_call in function_calls:
            function_call_id = function_call["id"]
            tool_name = function_call["name"]
            arguments = function_call.get("arguments") or {}

            if tool_name == self.retrieval_tool_name:
                query_text = arguments.get("query_text")
                if not query_text:
                    raise MessageGenerationException("Error occurred when retrieving related documents")

                self.trace_collector.start(function_call_id)
                retrieval_content, retrieval_results = await query_assistant_retrieval(
                    assistant=self.assistant,
                    query_text=query_text,
                )

                logger.debug(f"Retrieval query: {query_text}")
                logger.debug(f"Retrieval result: {str(retrieval_results)[:200]}...")

                yield TOOL_RUN_TYPE_RETRIEVAL_RESULT, retrieval_results

                if log:
                    retrieval_output_log_dict = build_retrieval_output_log_dict(
                        session_id=self.session_id,
                        event_id=function_call_id,
                        retrieval_result=retrieval_results,
                        duration_ms=self.trace_collector.duration(function_call_id),
                    )
                    if self.save_logs:
                        self.logs.append(retrieval_output_log_dict)
                    yield TOOL_RUN_TYPE_LOG, retrieval_output_log_dict
                self.trace_collector.clear(function_call_id)

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
                tool_inputs.append(tool_input)

        num_tool_outputs = 0
        num_retrieval_results = 0

        if tool_inputs:
            if log:
                for tool_input in tool_inputs:
                    self.trace_collector.start(tool_input.tool_call_id)
                    tool_input_log_dict = build_tool_input_log_dict(
                        session_id=self.session_id,
                        event_id=tool_input.tool_call_id,
                        tool_input=tool_input,
                    )
                    if self.save_logs:
                        self.logs.append(tool_input_log_dict)
                    yield TOOL_RUN_TYPE_LOG, tool_input_log_dict
            tool_outputs: List[ToolOutput] = await run_tools(tool_inputs)
            for tool_output in tool_outputs:
                self.chat_completion_messages.append(tool_output.to_function_message())
                yield TOOL_RUN_TYPE_TOOL_OUTPUT, tool_output
                num_tool_outputs += 1

                if log:
                    tool_action_result_log_dict = build_tool_output_log_dict(
                        session_id=self.session_id,
                        event_id=tool_output.tool_call_id,
                        tool_output=tool_output,
                        duration_ms=self.trace_collector.duration(tool_output.tool_call_id),
                    )
                    if self.save_logs:
                        self.logs.append(tool_action_result_log_dict)
                    yield TOOL_RUN_TYPE_LOG, tool_action_result_log_dict
                self.trace_collector.clear(tool_output.tool_call_id)

        self.result_builder.end_trace(
            event_id=tool_run_event_id,
            event="tool_run",
            input_summary=f"executed {num_tool_outputs} tool(s), {num_retrieval_results} retrieval(s)",
            metadata={
                "num_function_calls": len(function_calls),
                "num_tool_outputs": num_tool_outputs,
                "num_retrieval_results": num_retrieval_results,
            },
        )
        self.trace_collector.clear(tool_run_event_id)

    async def inference(self, event_id: Optional[str] = None) -> Tuple[Dict, List, Dict, Dict]:
        if event_id:
            self.trace_collector.start(event_id)
            self.result_builder.start_trace(
                event_id=event_id,
                event="inference",
                input_summary="non-stream chat completion",
                metadata={
                    "model_id": self.model.model_id,
                    "num_messages": len(self.chat_completion_messages),
                    "num_functions": len(self.chat_completion_functions),
                },
            )

        completion_data = await chat_completion(
            model=self.model,
            messages=self.chat_completion_messages,
            functions=self.chat_completion_functions,
            configs={},
        )

        assistant_message_dict = completion_data["message"]
        function_calls = assistant_message_dict.get("function_calls")
        usage = completion_data.get("usage")

        if event_id:
            self.result_builder.end_trace(
                event_id=event_id,
                event="inference",
                input_summary=f"inference done, has_functions={function_calls is not None}",
                metadata={
                    "has_function_calls": function_calls is not None,
                    "num_function_calls": len(function_calls) if function_calls else 0,
                    "usage": usage,
                },
            )
        return assistant_message_dict, function_calls, usage, completion_data

    async def stream_inference(self, message_chunk_object_name="MessageChunk", event_id: Optional[str] = None):
        if event_id:
            self.trace_collector.start(event_id)
            self.result_builder.start_trace(
                event_id=event_id,
                event="inference_stream",
                input_summary="streaming chat completion",
                metadata={
                    "model_id": self.model.model_id,
                    "num_messages": len(self.chat_completion_messages),
                    "num_functions": len(self.chat_completion_functions),
                },
            )
        try:
            chunk_generator = await stream_chat_completion(
                model=self.model,
                messages=self.chat_completion_messages,
                functions=self.chat_completion_functions,
                configs={},
                chunk_handler=None,
            )
        except HTTPException as e:
            logger.error(f"HTTPException occurred in streaming chat completion: {e}")
            raise MessageGenerationException(f"Error occurred in streaming chat completion.")

        final_has_functions = False
        final_num_functions = 0
        final_usage = None

        async for chunk in chunk_generator:
            if chunk.get("object").lower() == "error":
                raise MessageGenerationException(f"{chunk.get('message')}")

            assistant_message_dict = chunk.get("message")
            if assistant_message_dict:
                yield MESSAGE, assistant_message_dict
                function_calls = assistant_message_dict.get("function_calls")
                final_has_functions = function_calls is not None
                final_num_functions = len(function_calls) if function_calls else 0
                usage = chunk.get("usage")
                if usage:
                    final_usage = usage
                    yield USAGE, usage
                yield MESSAGE_RESPONSE, chunk

            else:
                delta = chunk.get("delta")
                if delta:
                    chunk.update({"object": message_chunk_object_name})
                    yield MESSAGE_CHUNK, chunk

        if event_id:
            self.result_builder.end_trace(
                event_id=event_id,
                event="inference_stream",
                input_summary=f"stream done, has_functions={final_has_functions}",
                metadata={
                    "has_function_calls": final_has_functions,
                    "num_function_calls": final_num_functions,
                    "usage": final_usage,
                },
            )

    def has_user_input_function_call(self, function_calls):
        if not function_calls:
            return False
        for function_call in function_calls:
            if function_call["name"] in self.function_names:
                return True
        return False

    def filter_user_function_calls(self, function_calls) -> Optional[List[Dict]]:
        results = [function_call for function_call in function_calls if function_call["name"] in self.function_names]

        if results:
            return results

        else:
            return None
