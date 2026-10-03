from typing import Annotated

from fastapi import Depends, Request

from app.foundry import FoundryClient
from app.services.chat import ChatService


def get_foundry_client(request: Request) -> FoundryClient:
    return request.app.state.foundry_client


def get_chat_service(
    client: Annotated[FoundryClient, Depends(get_foundry_client)],
) -> ChatService:
    return ChatService(client)
