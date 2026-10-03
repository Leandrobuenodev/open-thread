import asyncio
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from app.auth import AuthenticatedUser, get_current_user
from app.dependencies import get_foundry_client
from app.foundry import FoundryClient, FoundrySettings
from app.main import create_app
from app.persistence import CONTEXT_BYTES, CONTEXT_MESSAGES, identity
from app.protection import ChatAdmission, ChatLimits

A = AuthenticatedUser("user-a", "tenant")
B = AuthenticatedUser("user-b", "tenant")


@pytest_asyncio.fixture
async def api(storage_config):
    app = create_app()
    calls = []
    responses = [200]

    def upstream(request):
        import json

        calls.append(json.loads(request.content))
        return httpx.Response(
            responses[0], json={"choices": [{"message": {"content": "Answer"}}]}
        )

    foundry = FoundryClient(
        FoundrySettings("https://fake.openai.azure.com", "openthread-chat", "fake"),
        transport=httpx.MockTransport(upstream),
    )
    app.dependency_overrides[get_current_user] = lambda: A
    app.dependency_overrides[get_foundry_client] = lambda: foundry
    async with app.router.lifespan_context(app):
        app.state.chat_admission = ChatAdmission(ChatLimits(requests_per_window=100))
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            yield app, client, calls, responses
    await foundry.close()


async def create(client):
    result = await client.post("/api/conversations")
    assert result.status_code == 201
    return result.json()["id"]


async def send(client, cid, prompt="Hello"):
    return await client.post(
        "/api/chat", json={"conversation_id": cid, "message": prompt}
    )


@pytest.mark.asyncio
async def test_create_list_retrieve_context_and_restart(api):
    _app, client, calls, _ = api
    cid = await create(client)
    assert (await client.get("/api/conversations")).json()[0]["title"] == "New chat"
    assert (await send(client, cid, "Remember blue")).status_code == 200
    assert (await send(client, cid, "Which color?")).json() == {"message": "Answer"}
    detail = (await client.get(f"/api/conversations/{cid}")).json()
    assert detail["title"] == "Remember blue"
    assert [m["sequence"] for m in detail["messages"]] == [1, 2, 3, 4]
    assert [m["role"] for m in detail["messages"]] == [
        "user",
        "assistant",
        "user",
        "assistant",
    ]
    assert all(m["status"] == "completed" for m in detail["messages"])
    assert calls[1]["messages"] == [
        {"role": "user", "content": "Remember blue"},
        {"role": "assistant", "content": "Answer"},
        {"role": "user", "content": "Which color?"},
    ]
    assert calls[1]["model"] == "openthread-chat"
    # New app/client simulates a process restart and login; only validated claims return.
    restarted = create_app()
    restarted.dependency_overrides[get_current_user] = lambda: A
    async with (
        restarted.router.lifespan_context(restarted),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(restarted), base_url="http://test"
        ) as reload,
    ):
        assert (await reload.get(f"/api/conversations/{cid}")).json() == detail
    assert "object_id" not in detail and "tenant_id" not in detail


@pytest.mark.asyncio
@pytest.mark.parametrize("other", [B, AuthenticatedUser(A.object_id, "other-tenant")])
async def test_ownership_every_route_and_nonexistent(api, other):
    app, client, calls, _ = api
    cid = await create(client)
    app.dependency_overrides[get_current_user] = lambda: other
    assert (await client.get("/api/conversations")).json() == []
    for target in [cid, str(uuid4())]:
        assert (await client.get(f"/api/conversations/{target}")).status_code == 404
        assert (await client.delete(f"/api/conversations/{target}")).status_code == 404
        assert (await send(client, target)).status_code == 404
    assert calls == []
    app.dependency_overrides[get_current_user] = lambda: A
    assert (await client.get(f"/api/conversations/{cid}")).status_code == 200
    assert (await client.delete(f"/api/conversations/{cid}")).status_code == 204
    assert (await client.get(f"/api/conversations/{cid}")).status_code == 404


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [429, 500, 401])
async def test_failed_foundry_prompt_is_saved_but_excluded_from_next_context(
    api, status
):
    _app, client, calls, responses = api
    cid = await create(client)
    await send(client, cid, "Good turn")
    responses[0] = status
    assert (await send(client, cid, "Failed turn")).status_code == (
        429 if status == 429 else 502
    )
    detail = (await client.get(f"/api/conversations/{cid}")).json()
    assert [m["status"] for m in detail["messages"]] == [
        "completed",
        "completed",
        "failed",
    ]
    responses[0] = 200
    assert (await send(client, cid, "Continue")).status_code == 200
    assert calls[-1]["messages"] == [
        {"role": "user", "content": "Good turn"},
        {"role": "assistant", "content": "Answer"},
        {"role": "user", "content": "Continue"},
    ]
    assert [
        m["sequence"]
        for m in (await client.get(f"/api/conversations/{cid}")).json()["messages"]
    ] == [1, 2, 3, 4, 5]


@pytest.mark.asyncio
async def test_bounded_context_and_history_pagination(api):
    app, client, calls, _ = api
    cid = await create(client)
    store = app.state.conversation_store
    for i in range(55):
        attempt, _ = store.begin_turn(cid, A, f"Turn {i}")
        store.finish_turn(cid, A, attempt, "é" * 2000)
    assert (await send(client, cid, "Last")).status_code == 200
    context = calls[-1]["messages"]
    assert len(context) <= CONTEXT_MESSAGES
    assert sum(len(m["content"].encode()) for m in context) <= CONTEXT_BYTES
    assert context[0]["role"] == "user" and context[-1] == {
        "role": "user",
        "content": "Last",
    }
    latest = (await client.get(f"/api/conversations/{cid}")).json()
    assert len(latest["messages"]) == 100
    older = (
        await client.get(f"/api/conversations/{cid}?before={latest['next_before']}")
    ).json()
    assert older["next_before"] is None
    sequences = [m["sequence"] for m in older["messages"] + latest["messages"]]
    assert sequences == list(range(1, 113))
    assert (await client.delete(f"/api/conversations/{cid}")).status_code == 204
    assert store.repository.query(identity(A), "m:" + cid + ":") == []


@pytest.mark.asyncio
async def test_cancellation_saves_failure_and_releases_database_lease(api):
    app, client, _, _ = api
    from app.dependencies import get_chat_service

    entered = asyncio.Event()

    class Blocking:
        async def reply(self, context, cid):
            entered.set()
            await asyncio.Event().wait()

    app.dependency_overrides[get_chat_service] = Blocking
    cid = await create(client)
    task = asyncio.create_task(send(client, cid))
    await asyncio.wait_for(entered.wait(), 2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert (await client.get(f"/api/conversations/{cid}")).json()["messages"][0][
        "status"
    ] == "failed"
    app.dependency_overrides.pop(get_chat_service)
    assert (await send(client, cid)).status_code == 200


@pytest.mark.asyncio
async def test_conversation_auth_and_database_errors_are_safe(api, monkeypatch):
    app, client, _, _ = api
    app.dependency_overrides.pop(get_current_user)
    assert (await client.get("/api/conversations")).status_code == 401
    assert (await client.post("/api/conversations")).status_code == 401
    app.dependency_overrides[get_current_user] = lambda: A
    app.state.conversation_store = None
    assert (await client.get("/api/conversations")).status_code == 503


@pytest.mark.asyncio
async def test_recent_order_offset_and_title_truncation(api):
    _app, client, _, _ = api
    first, last = await create(client), await create(client)
    assert [c["id"] for c in (await client.get("/api/conversations")).json()] == [
        last,
        first,
    ]
    await send(client, first, "x" * 100)
    rows = (await client.get("/api/conversations")).json()
    assert rows[0]["id"] == first and rows[0]["title"] == "x" * 80
    assert (await client.get("/api/conversations?offset=1")).json()[0]["id"] == last


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["timeout", "invalid-response"])
async def test_foundry_transport_or_payload_failure_preserves_saved_prompt(
    api, failure
):
    app, client, _, _ = api

    def upstream(request):
        if failure == "timeout":
            raise httpx.ReadTimeout("private transport detail", request=request)
        return httpx.Response(200, json={"private": "upstream payload"})

    foundry = FoundryClient(
        FoundrySettings("https://fake.openai.azure.com", "chat", "fake"),
        transport=httpx.MockTransport(upstream),
    )
    app.dependency_overrides[get_foundry_client] = lambda: foundry
    cid = await create(client)
    try:
        response = await send(client, cid)
        assert response.status_code == 502 and "private" not in response.text
        messages = (await client.get(f"/api/conversations/{cid}")).json()["messages"]
        assert len(messages) == 1 and messages[0]["status"] == "failed"
    finally:
        await foundry.close()


@pytest.mark.asyncio
async def test_missing_storage_configuration_keeps_health_but_disables_storage(
    monkeypatch,
):
    monkeypatch.delenv("STORAGE_AUTH_MODE")
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: A
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client,
    ):
        assert (await client.get("/health")).status_code == 200
        assert (await client.post("/api/conversations")).status_code == 503
        assert (await send(client, str(uuid4()))).status_code == 503
