from fastapi import APIRouter, Depends, Request
from typing import Dict
from starlette.responses import StreamingResponse, Response

from app.services.assistant import get_assistant_and_chat, StatefulNormalSession, StatefulStreamSession
from app.schemas.assistant.generate import MessageGenerateRequest, MessageGenerateResponse

from ..utils import auth_info_required

import logging

logger = logging.getLogger(__name__)

router = APIRouter()


def _build_streaming_response(
    assistant,
    chat,
    stream: bool,
    debug: bool,
    system_prompt_variables: Dict,
) -> StreamingResponse:
    session = StatefulStreamSession(
        assistant=assistant,
        chat=chat,
        stream=stream,
        debug=debug,
        save_logs=debug,
    )
    return StreamingResponse(
        session.stream_generate(system_prompt_variables),
        media_type="text/event-stream",
    )


async def _build_json_response(
    assistant,
    chat,
    debug: bool,
    system_prompt_variables: Dict,
) -> MessageGenerateResponse:
    session = StatefulNormalSession(
        assistant=assistant,
        chat=chat,
        save_logs=False,
        debug=debug,
    )
    result = await session.generate(system_prompt_variables)
    return MessageGenerateResponse(
        data=result["message"],
        trace=result["trace"],
    )


@router.post(
    "/assistants/{assistant_id}/chats/{chat_id}/generate",
    summary="Generate message",
    operation_id="generate_message",
    tags=["Assistant - Message"],
    responses={
        200: {
            "description": "Successful response. "
                           "When stream=false: returns JSON with 'status', 'data', and optional 'trace' fields. "
                           "When stream=true: returns Server-Sent Events (SSE) stream.",
        },
        422: {"description": "Unprocessable Entity"},
    },
    description="Generate a new message with the role of 'assistant'. "
                "Set stream=true for SSE streaming response. Set debug=true to include trace events "
                "(via 'trace' field for JSON, via MessageGenerationLog SSE events for streaming).",
    response_model=MessageGenerateResponse,
    response_model_exclude_none=True,
)
async def api_chat_generate(
    request: Request,
    assistant_id: str,
    chat_id: str,
    payload: MessageGenerateRequest,
    auth_info: Dict = Depends(auth_info_required),
) -> Response:
    system_prompt_variables = payload.system_prompt_variables
    assistant, chat = await get_assistant_and_chat(assistant_id, chat_id)

    if payload.stream:
        return _build_streaming_response(
            assistant=assistant,
            chat=chat,
            stream=True,
            debug=payload.debug,
            system_prompt_variables=system_prompt_variables,
        )
    else:
        return await _build_json_response(
            assistant=assistant,
            chat=chat,
            debug=payload.debug,
            system_prompt_variables=system_prompt_variables,
        )
