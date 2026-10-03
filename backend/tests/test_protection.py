import asyncio
import json

import httpx
import pytest
import pytest_asyncio
from app.api.chat import MESSAGE_MAX_BYTES
from app.auth import AuthenticatedUser, get_current_user
from app.body_limit import ChatBodyLimitMiddleware
from app.dependencies import get_chat_service
from app.foundry import (
    FoundryClient,
    FoundrySettings,
    FoundryThrottled,
    throttling_delay,
)
from app.main import create_app
from app.protection import ChatAdmission, ChatLimits, ChatThrottled

USER = AuthenticatedUser("user", "tenant")
PAYLOAD = {"message": "Hello", "conversation_id": "test"}


class Clock:
    now = 0.0

    def __call__(self):
        return self.now


class Service:
    def __init__(self):
        self.calls = 0

    async def reply(self, message, conversation_id):
        self.calls += 1
        return "Reply"


@pytest_asyncio.fixture
async def api(storage_config):
    app = create_app()
    service = Service()
    app.dependency_overrides[get_current_user] = lambda: USER
    app.dependency_overrides[get_chat_service] = lambda: service
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client,
    ):
        app.state.conversation_store.create(USER, "test")
        yield app, client, service


@pytest.mark.asyncio
async def test_user_rate_limit_and_expiry(api):
    app, client, service = api
    clock = Clock()
    app.state.chat_admission = ChatAdmission(ChatLimits(), clock=clock)
    for _ in range(5):
        assert (await client.post("/api/chat", json=PAYLOAD)).status_code == 200
    clock.now = 0.5
    response = await client.post("/api/chat", json=PAYLOAD)
    assert response.status_code == 429
    assert response.headers["retry-after"] == "60"
    assert response.json() == {"detail": "Too many requests. Please try again later."}
    assert service.calls == 5
    clock.now = 60
    assert (await client.post("/api/chat", json=PAYLOAD)).status_code == 200


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "other", [AuthenticatedUser("other", "tenant"), AuthenticatedUser("user", "other")]
)
async def test_users_have_independent_counters(api, other):
    app, client, _ = api
    app.state.chat_admission = ChatAdmission(ChatLimits(requests_per_window=1))
    assert (await client.post("/api/chat", json=PAYLOAD)).status_code == 200
    assert (await client.post("/api/chat", json=PAYLOAD)).status_code == 429
    app.dependency_overrides[get_current_user] = lambda: other
    cid = (await client.post("/api/conversations")).json()["id"]
    assert (
        await client.post("/api/chat", json={**PAYLOAD, "conversation_id": cid})
    ).status_code == 200


@pytest.mark.asyncio
@pytest.mark.parametrize("fails", [False, True])
async def test_concurrent_request_rejected_without_queue_and_slot_released(api, fails):
    app, client, _ = api
    entered, release = asyncio.Event(), asyncio.Event()
    calls = 0

    class BlockingService:
        async def reply(self, message, conversation_id):
            nonlocal calls
            calls += 1
            if calls == 1:
                entered.set()
                await release.wait()
                if fails:
                    from app.foundry import FoundryError

                    raise FoundryError("Microsoft Foundry request failed.")
            return "Reply"

    app.dependency_overrides[get_chat_service] = BlockingService
    first = asyncio.create_task(client.post("/api/chat", json=PAYLOAD))
    try:
        await asyncio.wait_for(entered.wait(), 1)
        # Same user and a different user are both refused while the first is active.
        response = await asyncio.wait_for(client.post("/api/chat", json=PAYLOAD), 1)
        assert response.status_code == 429
        assert response.headers["retry-after"] == "1"
        app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
            "other", "tenant"
        )
        assert (
            await asyncio.wait_for(client.post("/api/chat", json=PAYLOAD), 1)
        ).status_code == 429
        assert calls == 1
    finally:
        release.set()
        result = await first
    assert result.status_code == (502 if fails else 200)
    app.dependency_overrides[get_current_user] = lambda: USER
    assert (await client.post("/api/chat", json=PAYLOAD)).status_code == 200
    assert calls == 2


def test_per_user_concurrency_when_global_capacity_is_greater():
    admission = ChatAdmission(ChatLimits(max_concurrency=2))
    with admission.admit(USER):
        with pytest.raises(ChatThrottled), admission.admit(USER):
            pytest.fail("same user must not enter twice")
        with admission.admit(AuthenticatedUser("other", "tenant")):
            pass
    with admission.admit(USER):
        pass


@pytest.mark.asyncio
async def test_cancellation_releases_slot():
    admission = ChatAdmission(ChatLimits())
    entered = asyncio.Event()

    async def work():
        with admission.admit(USER):
            entered.set()
            await asyncio.Event().wait()

    task = asyncio.create_task(work())
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    with admission.admit(USER):
        pass


def test_bounded_counters_do_not_evict_live_users():
    clock = Clock()
    admission = ChatAdmission(ChatLimits(requests_per_window=1), clock=clock)
    admission.MAX_TRACKED_USERS = 1
    with admission.admit(USER):
        pass
    with (
        pytest.raises(ChatThrottled),
        admission.admit(AuthenticatedUser("other", "tenant")),
    ):
        pass
    with pytest.raises(ChatThrottled), admission.admit(USER):
        pass
    clock.now = 60
    with admission.admit(AuthenticatedUser("other", "tenant")):
        pass


@pytest.mark.asyncio
async def test_body_limit_small_large_and_cors(api):
    _, client, service = api
    assert (await client.post("/api/chat", json=PAYLOAD)).status_code == 200
    response = await client.post(
        "/api/chat", content=b"x" * 65537, headers={"Origin": "http://localhost:5173"}
    )
    assert response.status_code == 413
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert service.calls == 1
    assert (await client.get("/health")).status_code == 200
    assert (await client.get("/health/version")).status_code == 200
    assert (
        await client.options(
            "/api/chat",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
            },
        )
    ).status_code == 200


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "headers", [[], [(b"content-length", b"1")], [(b"content-length", b"invalid")]]
)
async def test_body_limit_counts_chunks_without_trusting_content_length(headers):
    downstream_called = False
    sent = []
    chunks = iter(
        [
            {"type": "http.request", "body": b"a" * 32768, "more_body": True},
            {"type": "http.request", "body": b"b" * 32769, "more_body": True},
        ]
    )

    async def downstream(scope, receive, send):
        nonlocal downstream_called
        downstream_called = True

    async def receive():
        return next(chunks)  # fails if middleware continues reading after overflow

    async def send(message):
        sent.append(message)

    await ChatBodyLimitMiddleware(downstream, 65536)(
        {"type": "http", "method": "POST", "path": "/api/chat", "headers": headers},
        receive,
        send,
    )
    assert not downstream_called
    assert sent[0]["status"] == 413


@pytest.mark.asyncio
async def test_valid_chunked_json_replayed_without_content_length(api):
    _, client, service = api
    body = json.dumps(PAYLOAD).encode()

    async def chunks():
        yield body[:5]
        yield body[5:]

    assert (
        await client.post(
            "/api/chat", content=chunks(), headers={"Content-Type": "application/json"}
        )
    ).status_code == 200
    assert service.calls == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "message,status",
    [
        ("x" * MESSAGE_MAX_BYTES, 200),
        ("x" * (MESSAGE_MAX_BYTES + 1), 422),
        ("é" * (MESSAGE_MAX_BYTES // 2), 200),
        ("é" * (MESSAGE_MAX_BYTES // 2 + 1), 422),
    ],
)
async def test_message_utf8_boundary(api, message, status):
    _, client, service = api
    response = await client.post("/api/chat", json={**PAYLOAD, "message": message})
    assert response.status_code == status
    assert service.calls == (1 if status == 200 else 0)


@pytest.mark.asyncio
async def test_foundry_throttling_reaches_api_sanitized(api):
    app, client, _ = api
    requests = []

    def handler(request):
        requests.append(json.loads(request.content))
        return httpx.Response(
            429,
            headers={"retry-after-ms": "1501", "apim-request-id": "private-id"},
            text="private-secret upstream-body",
        )

    from app.services.chat import ChatService

    foundry = FoundryClient(
        FoundrySettings("https://test.services.ai.azure.com", "test", "fake-key"),
        transport=httpx.MockTransport(handler),
    )
    app.dependency_overrides[get_chat_service] = lambda: ChatService(foundry)
    try:
        response = await client.post("/api/chat", json=PAYLOAD)
        assert response.status_code == 429
        assert response.headers["retry-after"] == "2"
        assert response.json() == {
            "detail": "Too many requests. Please try again later."
        }
        assert "apim-request-id" not in response.headers
        assert requests[0]["max_completion_tokens"] == 256
        assert len(requests) == 1
    finally:
        await foundry.close()


@pytest.mark.parametrize(
    "headers,expected",
    [
        ({"Retry-After": "60"}, 60),
        ({"Retry-After": "0"}, 1),
        ({"retry-after-ms": "1001"}, 2),
        ({"Retry-After": "private-key"}, None),
        ({"Retry-After": "-1"}, None),
        ({}, None),
        ({"Retry-After": "bad", "retry-after-ms": "2000"}, 2),
        ({"Retry-After": "Wed, 21 Oct 2015 07:28:00 GMT"}, 1),
    ],
)
def test_retry_after_is_normalized(headers, expected):
    assert throttling_delay(httpx.Headers(headers)) == expected


@pytest.mark.asyncio
async def test_foundry_output_limit_override_and_429_without_delay():
    requests = []

    def handler(request):
        requests.append(json.loads(request.content))
        return httpx.Response(429)

    client = FoundryClient(
        FoundrySettings("https://test.services.ai.azure.com", "test", "fake-key"),
        transport=httpx.MockTransport(handler),
        max_output_tokens=128,
    )
    try:
        with pytest.raises(FoundryThrottled) as error:
            await client.generate_reply("Hello")
        assert error.value.retry_after is None
        assert requests[0]["max_completion_tokens"] == 128
    finally:
        await client.close()


def test_environment_overrides_and_invalid_limits(monkeypatch):
    monkeypatch.setenv("CHAT_RATE_LIMIT_REQUESTS", "2")
    monkeypatch.setenv("CHAT_RATE_LIMIT_WINDOW_SECONDS", "30")
    monkeypatch.setenv("CHAT_MAX_CONCURRENCY", "2")
    monkeypatch.setenv("CHAT_MAX_BODY_BYTES", "1024")
    monkeypatch.setenv("CHAT_MAX_MESSAGE_BYTES", "256")
    monkeypatch.setenv("FOUNDRY_MAX_OUTPUT_TOKENS", "128")
    limits = ChatLimits.from_environment()
    assert limits == ChatLimits(2, 30, 2, 1024, 256, 128)
    monkeypatch.setenv("CHAT_RATE_LIMIT_REQUESTS", "0")
    with pytest.raises(ValueError, match="CHAT_RATE_LIMIT_REQUESTS"):
        ChatLimits.from_environment()


@pytest.mark.asyncio
async def test_invalid_and_unauthenticated_requests_do_not_consume_counter(api):
    app, client, service = api
    app.state.chat_admission = ChatAdmission(ChatLimits(requests_per_window=1))
    assert (
        await client.post("/api/chat", json={**PAYLOAD, "message": ""})
    ).status_code == 422
    app.dependency_overrides.pop(get_current_user)
    assert (await client.post("/api/chat", json=PAYLOAD)).status_code == 401
    app.dependency_overrides[get_current_user] = lambda: USER
    assert (await client.post("/api/chat", json=PAYLOAD)).status_code == 200
    assert service.calls == 1


@pytest.mark.asyncio
async def test_body_exact_limit_and_disconnect():
    received = []

    async def downstream(scope, receive, send):
        received.append(await receive())

    async def send(message):
        pytest.fail("no rejection is expected")

    async def receive():
        return {"type": "http.request", "body": b"x" * 65536, "more_body": False}

    scope = {"type": "http", "method": "POST", "path": "/api/chat", "headers": []}
    middleware = ChatBodyLimitMiddleware(downstream, 65536)
    await middleware(scope, receive, send)
    assert len(received[0]["body"]) == 65536
    received.clear()

    async def disconnected():
        return {"type": "http.disconnect"}

    await middleware(scope, disconnected, send)
    assert received == []


@pytest.mark.asyncio
async def test_oversized_body_rejected_before_authentication(api):
    app, client, service = api

    def forbidden_auth():
        pytest.fail("body should be rejected before auth")

    app.dependency_overrides[get_current_user] = forbidden_auth
    assert (await client.post("/api/chat", content=b"x" * 65537)).status_code == 413
    assert service.calls == 0


def test_message_limit_environment_applies_at_process_start(monkeypatch):
    import subprocess
    import sys

    monkeypatch.setenv("CHAT_MAX_MESSAGE_BYTES", "64")
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            """
from app.api.chat import ChatRequest
from pydantic import ValidationError
ChatRequest(message='x' * 64, conversation_id='test')
try:
    ChatRequest(message='é' * 33, conversation_id='test')
except ValidationError:
    pass
else:
    raise AssertionError('UTF-8 message cap must follow environment')
""",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.asyncio
async def test_lifespan_uses_configured_output_limit(monkeypatch):
    monkeypatch.setenv("FOUNDRY_MAX_OUTPUT_TOKENS", "128")
    app = create_app()
    async with app.router.lifespan_context(app):
        assert app.state.foundry_client._max_output_tokens == 128
