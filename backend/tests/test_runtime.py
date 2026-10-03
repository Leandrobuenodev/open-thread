import httpx
import pytest
import pytest_asyncio

from app.main import app


_RUNTIME_VARIABLES = (
    "APP_GIT_SHA",
    "APP_BUILD_ID",
    "APP_RELEASE_ID",
    "APP_ENVIRONMENT",
    "APP_IMAGE_DIGEST",
    "APP_MIGRATION_REVISION",
    "CONTAINER_APP_REVISION",
    "CONTAINER_APP_REPLICA_NAME",
    "CONTAINER_APP_HOSTNAME",
)


@pytest_asyncio.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as test_client:
        yield test_client


@pytest.mark.asyncio
async def test_health_version_returns_null_for_unavailable_identity(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    for variable in _RUNTIME_VARIABLES:
        monkeypatch.delenv(variable, raising=False)

    response = await client.get("/health/version")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "commit": None,
        "build": None,
        "release_id": None,
        "environment": None,
        "image_digest": None,
        "migration_revision": None,
        "container_app_revision": None,
        "container_app_replica": None,
        "container_app_hostname": None,
    }


@pytest.mark.asyncio
async def test_health_version_returns_configured_safe_identity(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    values = {
        "APP_GIT_SHA": "abc123",
        "APP_BUILD_ID": "build-42",
        "APP_RELEASE_ID": "release-42",
        "APP_ENVIRONMENT": "dev",
        "APP_IMAGE_DIGEST": "sha256:abc",
        "APP_MIGRATION_REVISION": "migration-7",
        "CONTAINER_APP_REVISION": "revision-42",
        "CONTAINER_APP_REPLICA_NAME": "replica-7",
        "CONTAINER_APP_HOSTNAME": "app.example.internal",
    }
    for variable, value in values.items():
        monkeypatch.setenv(variable, value)

    response = await client.get("/health/version")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "commit": "abc123",
        "build": "build-42",
        "release_id": "release-42",
        "environment": "dev",
        "image_digest": "sha256:abc",
        "migration_revision": "migration-7",
        "container_app_revision": "revision-42",
        "container_app_replica": "replica-7",
        "container_app_hostname": "app.example.internal",
    }
