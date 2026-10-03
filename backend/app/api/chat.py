import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from starlette.concurrency import run_in_threadpool

from app.api.chat_stream import streaming_response
from app.auth import AuthenticatedUser, get_current_user
from app.dependencies import get_chat_service
from app.foundry import FoundryConfigurationError, FoundryError, FoundryThrottled
from app.persistence import ConversationStore, get_store
from app.protection import ChatLimits, ChatThrottled
from app.services.chat import ChatService

MESSAGE_MAX_BYTES = ChatLimits.from_environment().message_bytes

router = APIRouter(prefix="/api", tags=["chat"])


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    stream: bool = False
    message: str = Field(default="", max_length=MESSAGE_MAX_BYTES)
    attachment_ids: list[str] = Field(default_factory=list, max_length=1)

    @model_validator(mode="after")
    def require_content(self):
        if not self.message and not self.attachment_ids:
            raise ValueError("A message or image is required.")
        if self.attachment_ids and not self.stream:
            raise ValueError("Images require streaming.")
        return self

    conversation_id: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
    )

    @field_validator("message")
    @classmethod
    def limit_utf8_bytes(cls, value: str) -> str:
        if len(value.encode("utf-8")) > MESSAGE_MAX_BYTES:
            raise ValueError("Message exceeds the UTF-8 byte limit.")
        return value


class ChatResponse(BaseModel):
    message: str


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[ChatService, Depends(get_chat_service)],
    http_request: Request,
    store: Annotated[ConversationStore, Depends(get_store)],
) -> ChatResponse:
    if request.stream:
        return await streaming_response(
            http_request,
            current_user,
            store,
            service,
            request.conversation_id,
            request.message,
            request.attachment_ids,
        )
    try:
        with http_request.app.state.chat_admission.admit(current_user):
            attempt, context = await run_in_threadpool(
                store.begin_turn, request.conversation_id, current_user, request.message
            )
            try:
                answer = await service.reply(context, request.conversation_id)
            except BaseException:
                # Shield cleanup on disconnect; expired leases also recover worker crashes.
                await asyncio.shield(
                    run_in_threadpool(
                        store.finish_turn,
                        request.conversation_id,
                        current_user,
                        attempt,
                    )
                )
                raise
            await run_in_threadpool(
                store.finish_turn,
                request.conversation_id,
                current_user,
                attempt,
                answer,
            )
    except (ChatThrottled, FoundryThrottled) as exc:
        headers = (
            {"Retry-After": str(exc.retry_after)} if exc.retry_after is not None else {}
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(exc),
            headers=headers,
        ) from None
    except FoundryConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from None
    except FoundryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    return ChatResponse(message=answer)
