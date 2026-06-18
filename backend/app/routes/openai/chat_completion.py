from fastapi import APIRouter, Depends, Request

from app.operators import model_ops, assistant_ops
from app.services.inference.chat_completion import chat_completion, stream_chat_completion
from app.services.assistant.generation import StatelessNormalSession, StatelessStreamSession
from app.models.inference import has_multimodal_user_message
from .utils import *
from starlette.responses import StreamingResponse
from app.models import Assistant
from tkhelper.utils import SSE_DONE_MSG


from ..utils import auth_info_required, is_model_id, is_assistant_id

router = APIRouter()


def _openai_validate_capabilities(model, openai_data) -> None:
    """
    Validate capabilities for the OpenAI-compatible endpoint with clear, OpenAI-style errors.
    """
    tools = bool(openai_data.tools or openai_data.functions)
    vision_input = has_multimodal_user_message(openai_data.messages)
    response_format = openai_data.response_format

    if openai_data.stream and not model.allow_streaming():
        raise_request_validation_error(
            f"Model `{model.model_schema_id}` does not support streaming. "
            "Please use a model with the `stream` capability, or set stream=false."
        )

    if tools and not model.allow_function_call():
        raise_request_validation_error(
            f"Model `{model.model_schema_id}` does not support tool/function calling. "
            "Use a model with the `tools` capability, or remove the tools/functions parameter."
        )

    if vision_input and not model.allow_vision_input():
        raise_request_validation_error(
            f"Model `{model.model_schema_id}` does not support vision (image input). "
            "Use a model with the `vision` capability, or convert image inputs to text."
        )

    if response_format is not None:
        # normalize response_format
        fmt_type = None
        if isinstance(response_format, str):
            fmt = response_format.lower()
            if fmt in ("json", "json_object"):
                fmt_type = "json_object"
            elif fmt == "json_schema":
                fmt_type = "json_schema"
        else:
            fmt_type = response_format.type  # pydantic model with 'type' field

        if fmt_type and fmt_type != "text":
            if fmt_type == "json_schema" and not model.allow_json_schema():
                raise_request_validation_error(
                    f"Model `{model.model_schema_id}` does not support structured output with JSON schema. "
                    "Use a model with the `json_schema` capability, or set response_format to a supported format."
                )
            if not model.supports_response_format(fmt_type):
                caps = model.get_capabilities()
                raise_request_validation_error(
                    f"Model `{model.model_schema_id}` does not support response_format='{fmt_type}'. "
                    f"Supported formats: {caps.get('supported_response_formats', ['text'])}."
                )


# add new add_api_key
@router.post(
    "/chat/completions",
    summary="Chat Completion",
    operation_id="chat_completion",
    tags=["Inference"],
    responses={422: {"description": "Unprocessable Entity"}},
    description="Model inference for chat completion.",
)
async def api_chat_completion_openai(
    request: Request,
    openai_data: OpenaiChatCompletionRequest,
    auth_info: Dict = Depends(auth_info_required),
):
    data: ChatCompletionRequest = adapt_openai_chat_completion_input(openai_data)
    if is_model_id(model_id=data.model_id):
        # validate model
        model = await model_ops.get(model_id=data.model_id)

        # --- centralized capabilities validation BEFORE any inference ---
        _openai_validate_capabilities(model, openai_data)

        # check function call ability
        functions = [function.model_dump() for function in data.functions] if data.functions is not None else None
        if functions and not model.allow_function_call():
            raise_request_validation_error(f"Model {model.model_id} does not support function calls.")

        # prepare messages
        messages = [message.model_dump() for message in data.messages]
        payload_dict = data.model_dump()

        # perform chat completion with model
        if data.stream:
            if not model.allow_streaming():
                raise_request_validation_error(f"Model {model.model_id} does not support streaming.")

            async def generator():
                chunk_id = generate_random_chat_completion_id()
                async for chunk_dict in await stream_chat_completion(
                    model=model,
                    messages=messages,
                    configs=data.configs,
                    function_call=data.function_call,
                    functions=functions,
                ):
                    openai_chunk = await to_openai_chunk(chunk_dict, chunk_id, openai_data)
                    if openai_chunk is not None:
                        yield f"data: {json.dumps(openai_chunk)}\n\n"
                yield SSE_DONE_MSG

            return StreamingResponse(
                generator(),
                media_type="text/event-stream",
            )

        else:
            # generate none stream response
            response_data = await chat_completion(
                model=model,
                messages=messages,
                configs=data.configs,
                function_call=data.function_call,
                functions=functions,
            )
            response = ChatCompletion(**response_data)
            openai_response = adapt_openai_chat_completion_response(response, openai_data)
            openai_response_dict = openai_response.model_dump()
            for choice in openai_response_dict["choices"] if openai_response_dict.get("choices") else []:
                message_dict = choice.get("message") or {}
                if message_dict["function_call"] is None:
                    del message_dict["function_call"]
                if message_dict["tool_calls"] is None:
                    del message_dict["tool_calls"]
                if message_dict["name"] is None:
                    del message_dict["name"]
            return openai_response_dict

    elif is_assistant_id(assistant_id=data.model_id):
        # validate assistant
        assistant: Assistant = await assistant_ops.get(assistant_id=data.model_id)
        # validate the assistant's underlying model capabilities up-front
        assistant_model = await model_ops.get(model_id=assistant.model_id)
        _openai_validate_capabilities(assistant_model, openai_data)

        # perform chat completion with assistant
        if data.stream:
            session = StatelessStreamSession(
                assistant=assistant,
                save_logs=False,  # todo: enable save_logs
                yield_dict=True,
            )

            async def generator():
                chunk_id = generate_random_chat_completion_id()
                async for chunk_dict in session.stream_generate(data.messages, data.functions):
                    openai_chunk = await to_openai_chunk(chunk_dict, chunk_id, openai_data)
                    if openai_chunk is not None:
                        yield f"data: {json.dumps(openai_chunk)}\n\n"
                yield SSE_DONE_MSG

            return StreamingResponse(
                generator(),
                media_type="text/event-stream",
            )
        else:
            session = StatelessNormalSession(
                assistant=assistant,
                save_logs=False,  # todo: enable save_logs
            )
            response = await session.generate(data.messages, data.functions)
            openai_response = adapt_openai_chat_completion_response(response.data, openai_data)
            openai_response_dict = openai_response.model_dump()
            for choice in openai_response_dict["choices"] if openai_response_dict.get("choices") else []:
                message_dict = choice.get("message") or {}
                if message_dict["function_call"] is None:
                    del message_dict["function_call"]
                if message_dict["tool_calls"] is None:
                    del message_dict["tool_calls"]
                if message_dict["name"] is None:
                    del message_dict["name"]
            return openai_response_dict

    else:
        raise_request_validation_error(f"Invalid model_id: {data.model_id}")
