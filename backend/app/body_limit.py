"""Bound only the chat body before FastAPI's JSON parsing and dependencies."""

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send


class ChatBodyLimitMiddleware:
    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] != "http"
            or scope["method"] not in ("POST", "PATCH")
            or not (
                scope["path"].rstrip("/") == "/api/chat"
                or scope["path"].startswith("/api/projects")
                or (
                    scope["path"].startswith("/api/conversations/")
                    and not scope["path"].rstrip("/").endswith("/attachments")
                )
            )
        ):
            await self.app(scope, receive, send)
            return

        async def reject() -> None:
            await JSONResponse(
                {"detail": "Request body is too large."}, status_code=413
            )(scope, receive, send)

        # Content-Length is only a fast rejection; actual bytes are always counted.
        for name, value in scope.get("headers", []):
            if name.lower() == b"content-length":
                try:
                    if int(value) > self.max_bytes:
                        await reject()
                        return
                except ValueError:
                    pass
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            if len(body) + len(chunk) > self.max_bytes:
                await reject()
                return
            body.extend(chunk)
            if not message.get("more_body", False):
                break

        delivered = False

        async def replay() -> dict:
            nonlocal delivered
            if delivered:
                return await receive()
            delivered = True
            return {"type": "http.request", "body": bytes(body), "more_body": False}

        await self.app(scope, replay, send)
