from fastapi import APIRouter, Depends, Request, HTTPException
from typing import Dict
from starlette.responses import StreamingResponse
import json
import logging

from tkhelper.utils import SSE_DONE_MSG
from tkhelper.error import raise_request_validation_error
from tkhelper.schemas.base import BaseDataResponse
from tkhelper.error import raise_http_error, ErrorCode

from app.schemas.model.chat_completion import ChatCompletionRequest
from app.services.inference.chat_completion import chat_completion, stream_chat_completion
from app.services.assistant.generation import StatelessNormalSession, StatelessStreamSession
from app.operators import model_ops, assistant_ops
from app.models import Model, Assistant
from app.models.inference import has_multimodal_user_message

from ..utils import auth_info_required, is_model_id, is_assistant_id

router = APIRouter()

logger = logging.getLogger(__name__)


def error_message(code, message: str):
    return {
        "object": "Error",
        "code": code,
        "message": message,
    }


def _validate_model_capabilities(model: Model, data: ChatCompletionRequest) -> None:
    """
    Centralized capability validation before generation.
    Raises clear, user-friendly errors when the model lacks required capabilities.
    """
    functions = [function.model_dump() for function in data.functions] if data.functions is not None else None
    vision_input = has_multimodal_user_message(data.messages)
    configs = data.configs or {}
    response_format = configs.get("response_format")

    # --- streaming ---
    if data.stream and not model.allow_streaming():
        raise_request_validation_error(
            f"Model {model.model_id} ({model.model_schema_id}) does not support streaming. "
            "Choose a model with the `stream` capability or disable streaming."
        )

    # --- tools / function call ---
    if functions and not model.allow_function_call():
        raise_request_validation_error(
            f"Model {model.model_id} ({model.model_schema_id}) does not support tool/function calling. "
            "Choose a model with the `tools` capability to use functions."
        )

    # --- vision / image input ---
    if vision_input and not model.allow_vision_input():
        raise_request_validation_error(
            f"Model {model.model_id} ({model.model_schema_id}) does not support vision (image input). "
            "Choose a model with the `vision` capability for multimodal messages."
        )

    # --- response_format / JSON mode ---
    if response_format:
        fmt = response_format.lower() if isinstance(response_format, str) else str(response_format).lower()
        normalized = None
        if fmt in ("json", "json_object"):
            normalized = "json_object"
        elif fmt == "json_schema":
            normalized = "json_schema"
        if normalized:
            if normalized == "json_schema" and not model.allow_json_schema():
                raise_request_validation_error(
                    f"Model {model.model_id} ({model.model_schema_id}) does not support structured output "
                    "with JSON schema. Choose a model with the `json_schema` capability."
                )
            if not model.supports_response_format(normalized):
                caps = model.get_capabilities()
                raise_request_validation_error(
                    f"Model {model.model_id} ({model.model_schema_id}) does not support "
                    f"response_format='{normalized}'. Supported formats: "
                    f"{caps.get('supported_response_formats', ['text'])}."
                )


@router.post(
    "/inference/chat_completion",
    summary="Chat Completion",
    operation_id="chat_completion",
    tags=["Inference"],
    responses={422: {"description": "Unprocessable Entity"}},
    description="Model inference for chat completion.",
    response_model=BaseDataResponse,
)
async def api_chat_completion(
    request: Request,
    data: ChatCompletionRequest,
    auth_info: Dict = Depends(auth_info_required),
):
    if is_model_id(model_id=data.model_id):
        # validate model
        base_model: Model = await model_ops.get(model_id=data.model_id)
        functions = [function.model_dump() for function in data.functions] if data.functions is not None else None

        # prepare messages
        messages = [message.model_dump() for message in data.messages]

        fallbacks = base_model.fallbacks.model_list
        models_to_attempt = [base_model.model_id] + ([fb.model_id for fb in fallbacks] if fallbacks else [])
        main_exception = None
        for i, model_id in enumerate(models_to_attempt):
            # Merge configurations from input or use model's default if none provided
            model = await model_ops.get(model_id=model_id)
            input_configs = data.configs or {}
            model_configs = model.configs or {}
            configs = {**model_configs, **input_configs}

            # unified capabilities check BEFORE attempting inference
            _validate_model_capabilities(model, data)

            # check function call ability
            if functions and not model.allow_function_call():
                raise_request_validation_error(f"Model {model.model_id} does not support function calls.")

            try:
                # perform chat completion with model
                if data.stream:
                    if not model.allow_streaming():
                        raise_request_validation_error(f"Model {model.model_id} does not support streaming.")
                    async def generator(sse_chunk_dicts):
                        async for chunk_dict in sse_chunk_dicts:
                            yield f"data: {json.dumps(chunk_dict)}\n\n"
                        yield SSE_DONE_MSG

                    sse_chunk_dicts = await stream_chat_completion(
                        model=model,
                        messages=messages,
                        configs=configs,
                        function_call=data.function_call,
                        functions=functions,
                    )

                    return StreamingResponse(
                        generator(sse_chunk_dicts),
                        media_type="text/event-stream",
                    )
                else:
                    # generate none stream response
                    response_data = await chat_completion(
                        model=model,
                        messages=messages,
                        configs=configs,
                        function_call=data.function_call,
                        functions=functions,
                    )
                    return BaseDataResponse(data=response_data)
            except HTTPException as e:
                if e.status_code == 422:
                    raise_http_error(ErrorCode.REQUEST_VALIDATION_ERROR, e.detail)
                if i == 0:
                    main_exception = e.detail["message"]
                logger.debug(f"Model {model_id} failed to respond: {e.detail}")
                continue
            except Exception as e:
                raise e
        if fallbacks:
            raise_http_error(
                ErrorCode.PROVIDER_ERROR,
                f"All models failed to respond. Main model {data.model_id} error: {main_exception}",
            )
        else:
            raise_http_error(ErrorCode.PROVIDER_ERROR, f"Model {data.model_id} failed to respond: " + main_exception)

    elif is_assistant_id(assistant_id=data.model_id):
        # validate assistant
        assistant: Assistant = await assistant_ops.get(assistant_id=data.model_id)
        # validate underlying model capabilities up-front
        model: Model = await model_ops.get(model_id=assistant.model_id)
        _validate_model_capabilities(model, data)

        # perform chat completion with assistant
        if data.stream:
            session = StatelessStreamSession(
                assistant=assistant,
                save_logs=False,  # todo: enable save_logs
            )
            return StreamingResponse(
                session.stream_generate(data.messages, data.functions),
                media_type="text/event-stream",
            )
        else:
            session = StatelessNormalSession(
                assistant=assistant,
                save_logs=False,  # todo: enable save_logs
            )
            return await session.generate(data.messages, data.functions)

    else:
        raise_request_validation_error(f"Invalid model_id: {data.model_id}")
