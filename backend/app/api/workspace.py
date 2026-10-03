from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from app.attachments import MAX_FILE_BYTES
from app.auth import AuthenticatedUser, get_current_user
from app.persistence import ConversationStore, get_store
from app.protection import ChatThrottled

router = APIRouter(prefix="/api", tags=["workspace"])
User = Annotated[AuthenticatedUser, Depends(get_current_user)]
Store = Annotated[ConversationStore, Depends(get_store)]


class ProjectName(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=80)


class ConversationMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: UUID | None = None
    is_pinned: bool | None = None


@router.get("/projects")
def projects(user: User, store: Store):
    return store.projects(user)


@router.post("/projects", status_code=201)
def create_project(body: ProjectName, user: User, store: Store):
    return store.create_project(user, body.name)


@router.patch("/projects/{project_id}")
def rename_project(project_id: UUID, body: ProjectName, user: User, store: Store):
    return store.change_project(str(project_id), user, body.name)


@router.delete("/projects/{project_id}", status_code=204)
def delete_project(project_id: UUID, user: User, store: Store):
    store.change_project(str(project_id), user)
    return Response(status_code=204)


@router.patch("/conversations/{conversation_id}")
def metadata(
    conversation_id: UUID, body: ConversationMetadata, user: User, store: Store
):
    values = body.model_dump(exclude_unset=True, mode="json")
    if "is_pinned" in values and values["is_pinned"] is None:
        raise HTTPException(422, "Pin must be true or false.")
    return store.metadata(str(conversation_id), user, values)


@router.post("/conversations/{conversation_id}/attachments", status_code=201)
async def upload_image(
    conversation_id: UUID,
    request: Request,
    user: User,
    store: Store,
    filename: str = Query("image", max_length=240),
):
    try:
        with request.app.state.chat_admission.admit(user):
            # Authenticate/ownership before accepting bytes; hard cap while consuming ASGI.
            await run_in_threadpool(store.owned, str(conversation_id), user)
            raw = bytearray()
            async for chunk in request.stream():
                if len(raw) + len(chunk) > MAX_FILE_BYTES:
                    raise HTTPException(413, "Image exceeds the 2 MiB limit.")
                raw.extend(chunk)
            return await run_in_threadpool(
                store.upload,
                str(conversation_id),
                user,
                bytes(raw),
                request.headers.get("content-type", ""),
                filename,
            )
    except ChatThrottled as exc:
        raise HTTPException(
            429, str(exc), headers={"Retry-After": str(exc.retry_after)}
        ) from None


@router.get("/conversations/{conversation_id}/attachments/{attachment_id}")
def get_image(conversation_id: UUID, attachment_id: UUID, user: User, store: Store):
    a = store.attachment(str(conversation_id), str(attachment_id), user)
    return Response(
        store.storage.read(a["storage_reference"]),
        media_type=a["media_type"],
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.delete(
    "/conversations/{conversation_id}/attachments/{attachment_id}", status_code=204
)
def discard_image(conversation_id: UUID, attachment_id: UUID, user: User, store: Store):
    store.discard(str(conversation_id), str(attachment_id), user)
    return Response(status_code=204)


@router.get("/library")
def library(user: User, store: Store, offset: int = Query(0, ge=0)):
    return store.library(user, offset)
