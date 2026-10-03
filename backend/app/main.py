from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.chat import router as chat_router
from app.api.conversations import router as conversations_router
from app.api.runtime import router as runtime_router
from app.api.workspace import router as workspace_router
from app.body_limit import ChatBodyLimitMiddleware
from app.core.config import get_frontend_origin
from app.foundry import FoundryClient
from app.persistence import ConversationStore
from app.protection import ChatAdmission, ChatLimits
from app.storage.azure import configured_storage
from app.storage.contracts import StorageConflict, StorageError


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    resources = configured_storage()
    app.state.conversation_store = (
        ConversationStore(resources[0], resources[1]) if resources else None
    )
    app.state.chat_admission = ChatAdmission(app.state.chat_limits)
    client = FoundryClient(max_output_tokens=app.state.chat_limits.output_tokens)
    app.state.foundry_client = client
    try:
        yield
    finally:
        await client.close()
        if resources:
            resources[0].close()
            resources[1].close()
            if resources[2]:
                resources[2].close()


def create_app() -> FastAPI:
    app = FastAPI(title="Open Thread API", version="0.1.0", lifespan=lifespan)
    limits = ChatLimits.from_environment()
    app.state.chat_limits = limits
    app.add_middleware(ChatBodyLimitMiddleware, max_bytes=limits.body_bytes)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[get_frontend_origin()],
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.exception_handler(StorageError)
    async def database_error(request: Request, exc: StorageError):
        return JSONResponse(
            {"detail": "Conversation storage is unavailable."},
            status_code=409 if isinstance(exc, StorageConflict) else 503,
        )

    app.include_router(workspace_router)
    app.include_router(conversations_router)
    app.include_router(chat_router)
    app.include_router(runtime_router)
    return app


app = create_app()
