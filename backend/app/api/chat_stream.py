"""Authenticated POST/SSE; the response owns admission and terminal persistence."""

import asyncio
import json
import logging

import anyio
from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool

from app.foundry import (
    FoundryConfigurationError,
    FoundryError,
    FoundryThrottled,
    FoundryTimeout,
)
from app.protection import ChatThrottled
from app.storage.contracts import StorageError

logger = logging.getLogger(__name__)


def event(name, data):
    return (
        "event: "
        + name
        + "\ndata: "
        + json.dumps(jsonable_encoder(data), ensure_ascii=False)
        + "\n\n"
    )


async def protected_thread(function, *args):
    # Starlette cancels a scope on disconnect; await persistence before releasing
    # admission. Plain asyncio cancellation is also shielded for shutdown/tests.
    with anyio.CancelScope(shield=True):
        task = asyncio.create_task(run_in_threadpool(function, *args))
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            return await task


async def streaming_response(
    http_request,
    user,
    store,
    service,
    conversation_id,
    content=None,
    attachment_ids=(),
    edit_id=None,
):
    admission = http_request.app.state.chat_admission.admit(user)
    try:
        admission.__enter__()
    except ChatThrottled as e:
        raise HTTPException(
            429, str(e), headers={"Retry-After": str(e.retry_after)}
        ) from None
    try:
        args = (conversation_id, user, content)
        if attachment_ids or edit_id:
            args += (attachment_ids, edit_id)
        attempt, context, prompt, assistant = await protected_thread(
            store.start_stream, *args
        )
    except BaseException:
        admission.__exit__(None, None, None)
        raise
    pieces = []
    terminal = False
    unfinished_status = "cancelled"
    upstream = None
    output_bytes = 0

    async def finish(status):
        nonlocal terminal
        if terminal:
            return None
        result = await protected_thread(
            store.end_stream, conversation_id, user, attempt, "".join(pieces), status
        )
        terminal = True
        return result

    async def events():
        nonlocal upstream, output_bytes, unfinished_status
        yield event("start", {"user": prompt, "assistant": assistant})
        try:
            upstream = service.stream(context, conversation_id)
            async for text in upstream:
                if output_bytes + len(text.encode("utf-8")) > 65_536:
                    raise FoundryError("Response exceeded its safety limit.")
                output_bytes += len(text.encode("utf-8"))
                pieces.append(text)
                yield event("delta", {"id": attempt, "text": text})
            if not "".join(pieces).strip():
                raise FoundryError("Microsoft Foundry returned an empty response.")
            result = await finish("completed")
            yield event("done", {"assistant": result})
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001 - sanitize all failures after SSE headers
            unfinished_status = "failed"
            code, status, detail, retry = (
                "upstream",
                502,
                "Microsoft Foundry request failed.",
                None,
            )
            if isinstance(e, FoundryTimeout):
                code, status, detail = "timeout", 504, str(e)
            elif isinstance(e, FoundryThrottled):
                code, status, detail, retry = "rate_limit", 429, str(e), e.retry_after
            elif isinstance(e, FoundryConfigurationError):
                code, status, detail = (
                    "configuration",
                    503,
                    "Microsoft Foundry is not configured.",
                )
            elif isinstance(e, StorageError):
                code, status, detail = (
                    "storage",
                    503,
                    "Conversation storage is unavailable.",
                )
            elif isinstance(e, HTTPException):
                code, status, detail = (
                    "conflict",
                    409,
                    "Message attempt is no longer active.",
                )
            try:
                await finish("failed")
            except (StorageError, HTTPException):
                # No error objects, prompts or credentials in logs. Lease recovers
                # storage outages/process death; never invent a completed answer.
                logger.warning("Unable to finalize message attempt.")
            yield event(
                "error",
                {
                    "code": code,
                    "status": status,
                    "detail": detail,
                    "retry_after": retry,
                },
            )
        finally:
            if upstream is not None:
                with anyio.CancelScope(shield=True):
                    await upstream.aclose()

    body = events()

    class OwnedResponse(StreamingResponse):
        async def __call__(self, scope, receive, send):
            try:
                await super().__call__(scope, receive, send)
            finally:
                with anyio.CancelScope(shield=True):
                    try:
                        await body.aclose()
                    finally:
                        try:
                            if not terminal:
                                try:
                                    await finish(unfinished_status)
                                except (StorageError, HTTPException):
                                    logger.warning(
                                        "Unable to finalize interrupted message attempt."
                                    )
                        finally:
                            admission.__exit__(None, None, None)

    return OwnedResponse(
        body,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )
