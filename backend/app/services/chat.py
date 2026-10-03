from app.foundry import FoundryClient


class ChatService:
    def __init__(self, client: FoundryClient) -> None:
        self._client = client

    async def reply(
        self, message: str | list[dict[str, str]], conversation_id: str
    ) -> str:
        # Persistence supplies a bounded, ordered context; this layer invokes Foundry.
        return await self._client.generate_reply(message)

    def stream(self, context, conversation_id):
        return self._client.stream_reply(context)
