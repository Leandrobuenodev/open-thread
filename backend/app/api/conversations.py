from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from app.api.chat_stream import streaming_response
from app.auth import AuthenticatedUser, get_current_user
from app.dependencies import get_chat_service
from app.persistence import ConversationStore, get_store
from app.services.chat import ChatService

router = APIRouter(prefix="/api/conversations", tags=["conversations"])
User = Annotated[AuthenticatedUser, Depends(get_current_user)]
Store = Annotated[ConversationStore, Depends(get_store)]


class ConversationView(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    project_id: str | None = None
    is_pinned: bool = False


class MessageView(BaseModel):
    id: str
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime
    sequence: int
    replaces_id: str | None = None
    attachments: list[dict] = Field(default_factory=list)
    reply_to_id: str | None
    status: Literal["pending", "completed", "failed", "cancelled", "superseded"]


class ConversationDetail(ConversationView):
    messages: list[MessageView]
    next_before: int | None


@router.post("", status_code=201, response_model=ConversationView)
def create_conversation(user: User, store: Store):
    return store.create(user)


@router.get("", response_model=list[ConversationView])
def list_conversations(user: User, store: Store, offset: int = Query(0, ge=0)):
    return store.list(user, offset)


@router.get("/{conversation_id}", response_model=ConversationDetail)
def get_conversation(
    conversation_id: UUID,
    user: User,
    store: Store,
    before: int | None = Query(None, ge=1),
):
    return store.get(str(conversation_id), user, before)


@router.delete("/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: UUID, user: User, store: Store):
    store.delete(str(conversation_id), user)
    return Response(status_code=204)


@router.post("/{conversation_id}/regenerate")
async def regenerate(
    conversation_id: UUID,
    user: User,
    store: Store,
    request: Request,
    service: Annotated[ChatService, Depends(get_chat_service)],
):
    return await streaming_response(request, user, store, service, str(conversation_id))


class EditMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(default="", max_length=512)


@router.post("/{conversation_id}/messages/{message_id}/edit")
async def edit_message(
    conversation_id: UUID,
    message_id: UUID,
    body: EditMessage,
    user: User,
    store: Store,
    request: Request,
    service: Annotated[ChatService, Depends(get_chat_service)],
):
    from fastapi import HTTPException

    from app.protection import ChatLimits

    content = body.message.strip()
    if (
        not content
        or len(content.encode("utf-8")) > ChatLimits.from_environment().message_bytes
    ):
        raise HTTPException(
            422, "Edited text must be nonempty and within the message limit."
        )
    return await streaming_response(
        request,
        user,
        store,
        service,
        str(conversation_id),
        content,
        (),
        str(message_id),
    )
