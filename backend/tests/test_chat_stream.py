import asyncio
import json
import socket
import threading
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
import uvicorn
from app.auth import AuthenticatedUser, get_current_user
from app.dependencies import get_foundry_client
from app.foundry import FoundryClient, FoundrySettings
from app.main import create_app
from app.protection import ChatAdmission, ChatLimits
from app.token_budget import ContextBudget

USER = AuthenticatedUser("stream-user", "tenant")


def chunk(text=None, reason=None):
    return (
        "data: "
        + json.dumps(
            {
                "choices": [
                    {
                        "delta": {"content": text} if text is not None else {},
                        "finish_reason": reason,
                    }
                ]
            }
        )
        + "\n\n"
    ).encode()


class ProviderStream(httpx.AsyncByteStream):
    def __init__(self, parts, gate=None):
        self.parts, self.gate = parts, gate
        self.closed = threading.Event()

    async def __aiter__(self):
        for i, part in enumerate(self.parts):
            if self.gate is not None and i == 1:
                while not self.gate.is_set():
                    await asyncio.sleep(0.01)
            if isinstance(part, Exception):
                raise part
            yield part

    async def aclose(self):
        self.closed.set()


@pytest_asyncio.fixture
async def setup(storage_config):
    app = create_app()
    calls, streams = [], []
    config = {
        "parts": [
            chunk("Hello"),
            chunk(" world"),
            chunk(reason="stop"),
            b"data: [DONE]\n\n",
        ],
        "gate": None,
        "status": 200,
    }

    def provider(request):
        calls.append(json.loads(request.content))
        stream = ProviderStream(config["parts"], config["gate"])
        streams.append(stream)
        return httpx.Response(
            config["status"],
            headers={"content-type": "text/event-stream", "retry-after": "2"},
            stream=stream,
        )

    foundry = FoundryClient(
        FoundrySettings("https://fake.openai.azure.com", "openthread-chat", "fake-key"),
        transport=httpx.MockTransport(provider),
    )
    app.dependency_overrides[get_current_user] = lambda: USER
    app.dependency_overrides[get_foundry_client] = lambda: foundry
    async with app.router.lifespan_context(app):
        app.state.chat_admission = ChatAdmission(ChatLimits(requests_per_window=100))
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            yield app, client, calls, config, streams
    await foundry.close()


async def create(client):
    return (await client.post("/api/conversations")).json()["id"]


async def send(client, cid, message="Remember blue"):
    return await client.post(
        "/api/chat", json={"message": message, "conversation_id": cid, "stream": True}
    )


def events(response):
    result = []
    for frame in response.text.strip().split("\n\n"):
        lines = frame.splitlines()
        result.append(
            (
                lines[0].removeprefix("event: "),
                json.loads(lines[1].removeprefix("data: ")),
            )
        )
    return result


@pytest.mark.asyncio
async def test_stream_order_provider_flags_and_persisted_final(setup):
    _app, client, calls, _, _ = setup
    cid = await create(client)
    # Provider is invoked only after the user/assistant placeholders are committed.
    response = await send(client, cid)
    assert (
        response.status_code == 200
        and "text/event-stream" in response.headers["content-type"]
    )
    frames = events(response)
    assert [name for name, _ in frames] == ["start", "delta", "delta", "done"]
    assert [data["text"] for name, data in frames if name == "delta"] == [
        "Hello",
        " world",
    ]
    messages = (await client.get(f"/api/conversations/{cid}")).json()["messages"]
    assert [m["status"] for m in messages] == ["completed", "completed"]
    assert messages[1]["content"] == "Hello world"
    assert messages[1]["id"] == frames[-1][1]["assistant"]["id"]
    assert messages[1]["reply_to_id"] == messages[0]["id"]
    assert calls[0]["stream"] is True and calls[0]["model"] == "openthread-chat"
    assert calls[0]["max_completion_tokens"] == 256


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["broken", "invalid", "throttled", "timeout"])
async def test_stream_failure_saves_partial_and_sanitizes(setup, kind, monkeypatch):
    _app, client, _, config, _ = setup
    cid = await create(client)
    if kind == "broken":
        config["parts"] = [chunk("Partial"), httpx.ReadError("private key/URL")]
    elif kind == "invalid":
        config["parts"] = [chunk("Partial"), b'data: {"secret":"private"}\n\n']
    elif kind == "throttled":
        config["status"] = 429
    else:
        import app.foundry as module

        monkeypatch.setattr(module, "REQUEST_TIMEOUT_SECONDS", 0.03)
        config["parts"] = [chunk("Partial"), chunk("never")]
        config["gate"] = threading.Event()
    response = await send(client, cid)
    data = events(response)[-1][1]
    assert data["code"] == (
        "timeout"
        if kind == "timeout"
        else "rate_limit"
        if kind == "throttled"
        else "upstream"
    )
    assert "private" not in response.text
    messages = (await client.get(f"/api/conversations/{cid}")).json()["messages"]
    assert [m["status"] for m in messages] == ["failed", "failed"]
    assert messages[1]["content"] == ("" if kind == "throttled" else "Partial")
    config["status"] = 200
    config["gate"] = None
    config["parts"] = [chunk("Retry"), chunk(reason="stop"), b"data: [DONE]\n\n"]
    regenerated = await client.post(f"/api/conversations/{cid}/regenerate")
    assert events(regenerated)[-1][0] == "done"
    messages = (await client.get(f"/api/conversations/{cid}")).json()["messages"]
    assert [m["role"] for m in messages] == ["user", "assistant", "assistant"]
    assert messages[-1]["content"] == "Retry"


@pytest.mark.asyncio
async def test_regenerate_versions_same_context_no_duplicate_prompt(setup):
    _, client, calls, config, _ = setup
    cid = await create(client)
    await send(client, cid)
    original = calls[-1]["messages"]
    config["parts"] = [chunk("New version"), chunk(reason="stop"), b"data: [DONE]\n\n"]
    response = await client.post(f"/api/conversations/{cid}/regenerate")
    assert events(response)[-1][0] == "done"
    assert calls[-1]["messages"] == original
    messages = (await client.get(f"/api/conversations/{cid}")).json()["messages"]
    assert [m["sequence"] for m in messages] == [1, 2, 3]
    assert [m["status"] for m in messages] == ["completed", "superseded", "completed"]
    assert messages[1]["content"] == "Hello world"
    await send(client, cid, "Continue")
    assert calls[-1]["messages"] == [
        {"role": "user", "content": "Remember blue"},
        {"role": "assistant", "content": "New version"},
        {"role": "user", "content": "Continue"},
    ]


@pytest.mark.asyncio
async def test_stream_auth_ownership_limits_and_empty_regenerate(setup):
    app, client, calls, _, _ = setup
    cid = await create(client)
    assert (
        await client.post(f"/api/conversations/{cid}/regenerate")
    ).status_code == 409
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        "other", "tenant"
    )
    assert (await send(client, cid)).status_code == 404
    assert (
        await client.post(f"/api/conversations/{cid}/regenerate")
    ).status_code == 404
    assert (
        await client.post(f"/api/conversations/{uuid4()}/regenerate")
    ).status_code == 404
    assert not calls
    app.dependency_overrides.pop(get_current_user)
    assert (await send(client, cid)).status_code == 401
    assert (
        await client.post(f"/api/conversations/{cid}/regenerate")
    ).status_code == 401
    app.dependency_overrides[get_current_user] = lambda: USER
    assert (await send(client, cid, "x" * 513)).status_code == 422
    assert (
        await client.post(f"/api/conversations/{cid}/regenerate", content=b"x" * 65537)
    ).status_code == 413
    app.state.chat_admission = ChatAdmission(ChatLimits(requests_per_window=1))
    assert (await send(client, cid)).status_code == 200
    assert (
        await client.post(f"/api/conversations/{cid}/regenerate")
    ).status_code == 429


@pytest_asyncio.fixture
async def live(setup):
    app, _, calls, config, streams = setup
    # Real socket/ASGI disconnect semantics: ASGITransport buffers SSE and cannot
    # prove arrival before completion or actual browser-style connection closure.
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(
        uvicorn.Config(app, log_level="critical", access_log=False, lifespan="off")
    )
    thread = threading.Thread(
        target=server.run, kwargs={"sockets": [sock]}, daemon=True
    )
    thread.start()
    for _ in range(200):
        if server.started:
            break
        await asyncio.sleep(0.01)
    assert server.started
    async with httpx.AsyncClient(
        base_url=f"http://127.0.0.1:{port}", timeout=5
    ) as client:
        try:
            yield app, client, calls, config, streams
        finally:
            server.should_exit = True
            await asyncio.to_thread(thread.join, 5)
            sock.close()
            assert not thread.is_alive()


async def through_delta(lines):
    async for line in lines:
        if line.startswith("event: delta"):
            return json.loads((await anext(lines)).removeprefix("data: "))
    pytest.fail("No delta received")


@pytest.mark.asyncio
async def test_live_chunks_arrive_before_provider_finishes(live):
    app, client, _, config, _ = live
    config["gate"] = threading.Event()
    cid = await create(client)
    async with client.stream(
        "POST",
        "/api/chat",
        json={"message": "Hello", "conversation_id": cid, "stream": True},
    ) as response:
        lines = response.aiter_lines()
        assert (await through_delta(lines))["text"] == "Hello"
        assert not config["gate"].is_set()
        detail = app.state.conversation_store.get(cid, USER)
        assert detail["messages"][0]["content"] == "Hello"
        assert detail["messages"][1]["status"] == "pending"
        config["gate"].set()
        rest = [line async for line in lines]
        assert "event: done" in rest
    assert (await client.get(f"/api/conversations/{cid}")).json()["messages"][-1][
        "content"
    ] == "Hello world"


@pytest.mark.asyncio
@pytest.mark.parametrize("regenerate", [False, True])
async def test_live_disconnect_cancels_upstream_and_allows_next_message(
    live, regenerate
):
    _, client, calls, config, streams = live
    cid = await create(client)
    if regenerate:
        await send(client, cid)
    config["gate"] = threading.Event()
    path = f"/api/conversations/{cid}/regenerate" if regenerate else "/api/chat"
    async with client.stream(
        "POST",
        path,
        json=None
        if regenerate
        else {"message": "Hello", "conversation_id": cid, "stream": True},
    ) as response:
        assert (await through_delta(response.aiter_lines()))["text"] == "Hello"
    for _ in range(100):
        data = (await client.get(f"/api/conversations/{cid}")).json()
        if data["messages"][-1]["status"] != "pending":
            break
        await asyncio.sleep(0.01)
    assert data["messages"][-1]["status"] == "cancelled"
    assert data["messages"][-1]["content"] == "Hello"
    assert streams[-1].closed.is_set()
    if regenerate:
        assert data["messages"][1]["status"] == "completed"
        assert len([m for m in data["messages"] if m["role"] == "user"]) == 1
    config["gate"] = None
    assert events(await send(client, cid, "Continue"))[-1][0] == "done"
    assert len(calls) == (3 if regenerate else 2)


def test_token_budget_includes_history_framing_instructions_and_output():
    budget = ContextBudget()
    context = budget.trim(
        [
            {"role": "user", "content": "a" * 512},
            {"role": "assistant", "content": "b" * 512},
            {"role": "user", "content": "c" * 512},
        ],
        16384,
    )
    assert context == [{"role": "user", "content": "c" * 512}]
    assert budget.estimate(context) == 840
    assert (
        budget.estimate([{"role": "system", "content": "instructions"}])
        == 64 + 256 + 8 + 12
    )
    assert budget.estimate(context) + budget.margin <= budget.total


@pytest.mark.asyncio
async def test_failed_regenerate_keeps_previous_completed_response_in_future_context(
    setup,
):
    _, client, calls, config, _ = setup
    cid = await create(client)
    await send(client, cid)
    config["parts"] = [chunk("partial new version"), httpx.ReadError("private")]
    assert (
        events(await client.post(f"/api/conversations/{cid}/regenerate"))[-1][0]
        == "error"
    )
    messages = (await client.get(f"/api/conversations/{cid}")).json()["messages"]
    assert [m["status"] for m in messages] == ["completed", "completed", "failed"]
    config["parts"] = [chunk("Continued"), chunk(reason="stop"), b"data: [DONE]\n\n"]
    await send(client, cid, "Continue")
    assert calls[-1]["messages"] == [
        {"role": "user", "content": "Remember blue"},
        {"role": "assistant", "content": "Hello world"},
        {"role": "user", "content": "Continue"},
    ]
