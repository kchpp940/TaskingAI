from typing import Dict
from tkhelper.error import raise_request_validation_error
import json
from ..schemas import OpenaiChatCompletionRequest, OpenaiChatCompletionResponse, OpenaiChoice, OpenaiCompletionUsage
from app.schemas import ChatCompletionRequest
from app.models import (
    ChatCompletionSystemMessage,
    ChatCompletionUserMessage,
    ChatCompletionAssistantMessage,
    ChatCompletionFunctionMessage,
    ChatCompletionFunction,
    ChatCompletionFunctionCall,
    ChatCompletionRole,
    ChatCompletionFunctionParameters,
    ChatCompletionFinishReason,
    ChatCompletion,
)
from ..models import *
from .utils import generate_random_chat_completion_id, generate_random_function_call_id


def adapt_openai_chat_completion_input(data: OpenaiChatCompletionRequest) -> ChatCompletionRequest:
    model_id = data.model

    def convert_message(message: Dict):
        role = message.get("role")
        content = message.get("content")
        tool_calls = message.get("tool_calls")
        func_call = message.get("function_call")

        if not role:
            raise_request_validation_error("role is required for each message.")

        if role == "system":
            return ChatCompletionSystemMessage(content=content, role=ChatCompletionRole.SYSTEM)
        elif role == "user":
            return ChatCompletionUserMessage(content=content, role=ChatCompletionRole.USER)
        elif role == "assistant":
            function_calls = []
            if tool_calls:
                if not isinstance(tool_calls, list):
                    raise_request_validation_error("tool_calls must be a list.")
                function_calls.extend(
                    [
                        ChatCompletionFunctionCall(
                            name=tool_call["function"]["name"],
                            arguments=json.loads(tool_call["function"]["arguments"])
                            if isinstance(tool_call["function"]["arguments"], str)
                            else tool_call["function"]["arguments"],
                            id=tool_call.get("id") or generate_random_function_call_id(),
                        )
                        for tool_call in tool_calls
                    ]
                )
            elif func_call:
                if not isinstance(func_call, dict):
                    raise_request_validation_error("function_call must be a dictionary.")
                function_calls.append(
                    ChatCompletionFunctionCall(
                        name=func_call["name"],
                        arguments=json.loads(func_call["arguments"])
                        if isinstance(func_call["arguments"], str)
                        else func_call["arguments"],
                        id=func_call.get("id") or generate_random_function_call_id(),
                    )
                )
            function_calls = function_calls if function_calls else None
            return ChatCompletionAssistantMessage(
                content=content, role=ChatCompletionRole.ASSISTANT, function_calls=function_calls
            )
        elif role == "tool":
            tool_call_id = message.get("tool_call_id") or message.get("id")
            if not tool_call_id:
                raise_request_validation_error("tool_call_id is required for tool messages.")
            return ChatCompletionFunctionMessage(
                content=content, role=ChatCompletionRole.FUNCTION, id=tool_call_id
            )
        elif role == "function":
            func_id = message.get("id") or message.get("name")
            if not func_id:
                raise_request_validation_error("id or name is required for function messages.")
            return ChatCompletionFunctionMessage(
                content=content, role=ChatCompletionRole.FUNCTION, id=func_id
            )
        else:
            raise ValueError(f"Unsupported message type: {type(message)}")

    messages = [convert_message(msg).model_dump() for msg in data.messages]

    if data.function_call in ["none", "auto"]:
        function_call = data.function_call
    elif isinstance(data.function_call, OpenaiChatCompletionFunctionCallOptionParam):
        function_call = data.function_call.name
    else:
        function_call = None

    functions = None
    if data.functions:
        functions = [
            ChatCompletionFunction(
                name=function.name,
                description=function.description,
                parameters=ChatCompletionFunctionParameters(**function.parameters.model_dump()),
            )
            for function in data.functions
        ]
    if data.tools:
        functions = [
            ChatCompletionFunction(
                name=tool.function.name,
                description=tool.function.description,
                parameters=ChatCompletionFunctionParameters(**tool.function.parameters.model_dump()),
            )
            for tool in data.tools
        ]
    return ChatCompletionRequest(
        model_id=model_id, messages=messages, function_call=function_call, functions=functions, stream=data.stream
    )


def adapt_openai_chat_completion_response(
    chat_completion: ChatCompletion, data: OpenaiChatCompletionRequest
) -> OpenaiChatCompletionResponse:
    finish_reason_map = {
        ChatCompletionFinishReason.STOP: "stop",
        ChatCompletionFinishReason.LENGTH: "length",
        ChatCompletionFinishReason.FUNCTION_CALLS: "tool_calls",
        ChatCompletionFinishReason.RECITATION: "stop",
        ChatCompletionFinishReason.ERROR: "content_filter",
        ChatCompletionFinishReason.UNKNOWN: "stop",
    }

    finish_reason = finish_reason_map.get(chat_completion.finish_reason, "stop")
    tool_calls, function_call = None, None
    if data.tools:
        tool_calls = (
            [
                OpenaiChatCompletionMessageToolCallParam(
                    id=fc.id,
                    function=OpenaiFunctionCall(name=fc.name, arguments=json.dumps(fc.arguments)),
                    type="function",
                )
                for fc in chat_completion.message.function_calls
            ]
            if chat_completion.message.function_calls
            else None
        )
    elif data.functions:
        function_call = (
            {
                "name": chat_completion.message.function_calls[0].name,
                "arguments": json.dumps(chat_completion.message.function_calls[0].arguments),
            }
            if chat_completion.message.function_calls
            else None
        )
        finish_reason = "function_call"

    openai_message = OpenaiChatCompletionAssistantMessageParam(
        role="assistant",
        content=chat_completion.message.content if not (function_call or tool_calls) else None,
        tool_calls=tool_calls,
        function_call=function_call,
        name=None,
    )

    usage = OpenaiCompletionUsage(
        prompt_tokens=chat_completion.usage.input_tokens,
        completion_tokens=chat_completion.usage.output_tokens,
        total_tokens=chat_completion.usage.input_tokens + chat_completion.usage.output_tokens,
    )

    choice = OpenaiChoice(finish_reason=finish_reason, index=0, logprobs=None, message=openai_message)
    openai_response = OpenaiChatCompletionResponse(
        id=generate_random_chat_completion_id(),
        choices=[choice],
        created=chat_completion.created_timestamp // 1000,
        model=data.model,
        object="chat.completion",
        system_fingerprint=None,  # Optional handling
        usage=usage,  # Optional handling
    )
    return openai_response


def adapt_openai_chat_completion_stream_chunk(chunk: Dict, chunk_id: str, data: OpenaiChatCompletionRequest) -> Dict:
    chat_completion_chunk = {
        "id": chunk_id,
        "created": chunk["created_timestamp"] // 1000,
        "model": data.model,
        "object": "chat.completion.chunk",
        "system_fingerprint": None,
        "choices": [],
    }

    if "delta" in chunk:
        delta = {
            "content": chunk["delta"],
            "role": chunk["role"],
        }

        tool_calls_delta = chunk.get("tool_calls")
        if tool_calls_delta:
            if data.tools:
                delta["tool_calls"] = [
                    {
                        "index": tc.get("index", idx),
                        "id": tc.get("id"),
                        "function": {
                            "name": tc.get("function", {}).get("name"),
                            "arguments": tc.get("function", {}).get("arguments"),
                        },
                        "type": "function",
                    }
                    for idx, tc in enumerate(tool_calls_delta)
                ]
            else:
                first_tc = tool_calls_delta[0] if tool_calls_delta else {}
                delta["function_call"] = {
                    "name": first_tc.get("function", {}).get("name"),
                    "arguments": first_tc.get("function", {}).get("arguments"),
                }

        finish_reason = chunk.get("finish_reason")
        if finish_reason:
            finish_reason_map = {
                "stop": "stop",
                "length": "length",
                "function_calls": "tool_calls" if data.tools else "function_call",
                "recitation": "stop",
                "error": "content_filter",
                "unknown": "stop",
            }
            finish_reason = finish_reason_map.get(finish_reason, None)

        chat_completion_chunk["choices"].append(
            {
                "delta": delta,
                "finish_reason": finish_reason,
                "index": chunk.get("index", 0),
                "logprobs": None,
            }
        )

    return chat_completion_chunk


def adapt_openai_chat_completion_stream(
    chat_completion: Dict, chunk_id: str, data: OpenaiChatCompletionRequest
) -> Dict:
    message = chat_completion["message"]
    role = message["role"]
    created_timestamp_seconds = chat_completion["created_timestamp"] // 1000

    function_calls = message.get("function_calls")
    if not function_calls:
        return None

    if data.tools:
        tool_calls = []
        for idx, call in enumerate(function_calls):
            tool_call = {
                "index": idx,
                "id": call["id"],
                "function": {"name": call["name"], "arguments": json.dumps(call["arguments"])},
                "type": "function",
            }
            tool_calls.append(tool_call)

        delta = {"content": None, "role": role, "tool_calls": tool_calls}
        finish_reason = "tool_calls"
    else:
        function_call = {
            "name": function_calls[0]["name"],
            "arguments": json.dumps(function_calls[0]["arguments"]),
        }
        delta = {"content": None, "role": role, "function_call": function_call}
        finish_reason = "function_call"

    choice = {"delta": delta, "finish_reason": finish_reason, "index": 0, "logprobs": None}

    openai_chat_completion_chunk = {
        "id": chunk_id,
        "choices": [choice],
        "created": created_timestamp_seconds,
        "model": data.model,
        "object": "chat.completion.chunk",
        "system_fingerprint": None,
    }

    return openai_chat_completion_chunk


async def to_openai_chunk(c: Dict, chunk_id: str, data: OpenaiChatCompletionRequest):
    if c.get("object") == "ChatCompletionChunk":
        return adapt_openai_chat_completion_stream_chunk(c, chunk_id, data)
    elif c.get("object") == "ChatCompletion":
        return adapt_openai_chat_completion_stream(c, chunk_id, data)
    return None
