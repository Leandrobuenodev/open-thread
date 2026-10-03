import httpx
import pytest
import pytest_asyncio
from app.auth import AuthenticatedUser, get_current_user
from app.dependencies import get_foundry_client
from app.foundry import FoundryClient, FoundrySettings
from app.main import app


@pytest_asyncio.fixture
async def client(storage_config):
    transport = httpx.ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        from app.auth import AuthenticatedUser

        for cid, oid, tid in [
            ("conversation-123", "user-object-id", "tenant-id"),
            ("test", "user", "tenant"),
        ]:
            app.state.conversation_store.create(AuthenticatedUser(oid, tid), cid)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as test_client:
            try:
                yield test_client
            finally:
                app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_health(client: httpx.AsyncClient) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_chat_rejects_unauthenticated_requests(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/chat",
        json={"message": "Hello", "conversation_id": "conversation-123"},
    )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.asyncio
async def test_chat_uses_injected_foundry_client(client: httpx.AsyncClient) -> None:
    requests = []

    def handler(request):
        import json

        requests.append(json.loads(request.content))
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "Hello from Foundry"}}]}
        )

    foundry = FoundryClient(
        FoundrySettings(
            "https://test-resource.services.ai.azure.com",
            "test-deployment",
            "test-secret",
        ),
        transport=httpx.MockTransport(handler),
    )
    app.dependency_overrides[get_foundry_client] = lambda: foundry
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        object_id="user-object-id",
        tenant_id="tenant-id",
    )
    try:
        response = await client.post(
            "/api/chat",
            json={"message": "Hello", "conversation_id": "conversation-123"},
        )
        assert response.status_code == 200
        assert response.json() == {"message": "Hello from Foundry"}
        assert requests == [
            {
                "model": "test-deployment",
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": False,
                "max_completion_tokens": 256,
            }
        ]
    finally:
        await foundry.close()


@pytest.mark.asyncio
async def test_chat_rejects_blank_messages(client: httpx.AsyncClient) -> None:
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        object_id="user-object-id",
        tenant_id="tenant-id",
    )

    response = await client.post(
        "/api/chat",
        json={"message": "   ", "conversation_id": "conversation-123"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_chat_rejects_invalid_conversation_id(
    client: httpx.AsyncClient,
) -> None:
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        object_id="user-object-id",
        tenant_id="tenant-id",
    )

    response = await client.post(
        "/api/chat",
        json={"message": "Hello", "conversation_id": "bad id"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_cors_allows_only_local_frontend(client: httpx.AsyncClient) -> None:
    headers = {
        "Origin": "http://localhost:5173",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "authorization, content-type",
    }

    allowed = await client.options("/api/chat", headers=headers)
    denied = await client.options(
        "/api/chat", headers={**headers, "Origin": "https://example.com"}
    )

    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "authorization" in allowed.headers["access-control-allow-headers"].lower()
    assert "access-control-allow-origin" not in denied.headers


@pytest.mark.asyncio
async def test_chat_reports_missing_foundry_configuration(client, monkeypatch):
    for name in ["FOUNDRY_ENDPOINT", "FOUNDRY_DEPLOYMENT", "FOUNDRY_API_KEY"]:
        monkeypatch.delenv(name, raising=False)
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        "user", "tenant"
    )
    response = await client.post(
        "/api/chat", json={"message": "Hello", "conversation_id": "test"}
    )
    assert response.status_code == 503
    assert "FOUNDRY_ENDPOINT" in response.json()["detail"]


@pytest.mark.asyncio
async def test_chat_translates_foundry_failure_safely(client):
    foundry = FoundryClient(
        FoundrySettings(
            "https://test-resource.services.ai.azure.com",
            "test-deployment",
            "test-secret",
        ),
        transport=httpx.MockTransport(
            lambda request: httpx.Response(500, text="private test-secret")
        ),
    )
    app.dependency_overrides[get_foundry_client] = lambda: foundry
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        "user", "tenant"
    )
    try:
        response = await client.post(
            "/api/chat", json={"message": "Hello", "conversation_id": "test"}
        )
        assert response.status_code == 502
        assert response.json() == {"detail": "Microsoft Foundry request failed."}
    finally:
        await foundry.close()


@pytest.mark.asyncio
async def test_chat_rejects_invalid_bearer_without_model_call(client, monkeypatch):
    from app import auth

    class InvalidTokenValidator:
        def validate(self, token):
            raise auth.TokenValidationError("invalid")

    monkeypatch.setattr(
        auth, "get_entra_token_validator", lambda: InvalidTokenValidator()
    )
    response = await client.post(
        "/api/chat",
        headers={"Authorization": "Bearer invalid"},
        json={"message": "Hello", "conversation_id": "test"},
    )
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {"message": "Hello"},
        {"message": "Hello", "conversation_id": "test", "extra": True},
        {"message": "x" * 10001, "conversation_id": "test"},
        {"message": "Hello", "conversation_id": "x" * 129},
    ],
)
async def test_chat_preserves_request_validation(client, payload):
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        "user", "tenant"
    )
    response = await client.post("/api/chat", json=payload)
    assert response.status_code == 422


def test_lifespan_closes_concrete_foundry_client():
    from app.main import create_app
    from fastapi.testclient import TestClient

    application = create_app()
    with TestClient(application) as client:
        foundry = application.state.foundry_client
        assert isinstance(foundry, FoundryClient)
        assert not foundry._http.is_closed
        assert client.get("/health").status_code == 200
        assert client.get("/health/version").status_code == 200
    assert foundry._http.is_closed
