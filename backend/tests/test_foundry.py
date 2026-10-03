import asyncio
import json

import httpx
import pytest

import app.foundry as foundry
from app.foundry import (
    FoundryClient,
    FoundryConfigurationError,
    FoundryError,
    FoundrySettings,
)

SETTINGS = FoundrySettings(
    "https://test-resource.services.ai.azure.com", "test-deployment", "test-secret"
)


@pytest.mark.asyncio
async def test_calls_foundry_and_extracts_response():
    async def handler(request):
        assert str(request.url) == SETTINGS.endpoint + "/openai/v1/chat/completions"
        assert request.headers["api-key"] == "test-secret"
        assert "authorization" not in request.headers
        assert not any("opencode" in key.lower() for key in request.headers)
        assert request.headers["user-agent"] != "EvidenceOps/0.1.0"
        assert json.loads(request.content) == {
            "model": "test-deployment",
            "messages": [{"role": "user", "content": "Hello"}],
            "stream": False,
            "max_completion_tokens": 256,
        }
        assert request.extensions["timeout"]["connect"] == 5.0
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "  Hello back  "}}]}
        )

    client = FoundryClient(SETTINGS, transport=httpx.MockTransport(handler))
    try:
        assert await client.generate_reply("Hello") == "Hello back"
    finally:
        await client.close()
    assert client._http.is_closed


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [301, 400, 401, 429, 500, 503])
async def test_upstream_errors_are_safe_and_not_retried(status, caplog):
    calls = 0

    async def handler(request):
        nonlocal calls
        calls += 1
        return httpx.Response(
            status,
            headers={"location": "https://another-host.test/"},
            json={"error": "test-secret private-prompt private-upstream-body"},
        )

    client = FoundryClient(SETTINGS, transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(FoundryError) as error:
            await client.generate_reply("private-prompt")
        assert str(error.value) == (
            "Too many requests. Please try again later."
            if status == 429 else "Microsoft Foundry request failed."
        )
    finally:
        await client.close()
    assert calls == 1
    for sensitive in ["test-secret", "private-prompt", "private-upstream-body"]:
        assert sensitive not in caplog.text
        assert sensitive not in str(error.value)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error_type", [httpx.ReadTimeout, httpx.ConnectTimeout, httpx.ConnectError]
)
async def test_transport_failure_is_safe_and_not_retried(error_type, caplog):
    calls = 0

    async def handler(request):
        nonlocal calls
        calls += 1
        raise error_type("test-secret private-prompt")

    client = FoundryClient(SETTINGS, transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(FoundryError) as error:
            await client.generate_reply("private-prompt")
        expected = (
            "timed out"
            if issubclass(error_type, httpx.TimeoutException)
            else "connection failed"
        )
        assert expected in str(error.value)
    finally:
        await client.close()
    assert calls == 1
    assert "test-secret" not in caplog.text + str(error.value)
    assert "private-prompt" not in caplog.text + str(error.value)


@pytest.mark.asyncio
async def test_total_deadline_cancels_slow_request(monkeypatch):
    monkeypatch.setattr(foundry, "REQUEST_TIMEOUT_SECONDS", 0.01)

    async def handler(request):
        await asyncio.sleep(1)
        raise AssertionError("request should have been cancelled")

    client = FoundryClient(SETTINGS, transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(FoundryError, match="timed out"):
            await client.generate_reply("Hello")
    finally:
        await client.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body",
    [
        None,
        [],
        {},
        {"choices": []},
        {"choices": None},
        {"choices": [{"message": {}}]},
        {"choices": [{"message": {"content": None}}]},
        {"choices": [{"message": {"content": "   "}}]},
        {"choices": [{"message": {"content": 123}}]},
        {"choices": [{"message": {"content": [{"text": "unsupported"}]}}]},
    ],
)
async def test_invalid_response(body):
    client = FoundryClient(
        SETTINGS,
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, content=json.dumps(body))
        ),
    )
    try:
        with pytest.raises(FoundryError, match="invalid text response"):
            await client.generate_reply("Hello")
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_invalid_json_response():
    client = FoundryClient(
        SETTINGS,
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, text="not-json test-secret")
        ),
    )
    try:
        with pytest.raises(FoundryError, match="invalid text response"):
            await client.generate_reply("Hello")
    finally:
        await client.close()


@pytest.mark.parametrize(
    "missing", ["FOUNDRY_ENDPOINT", "FOUNDRY_DEPLOYMENT", "FOUNDRY_API_KEY"]
)
def test_each_required_configuration_is_checked(missing, monkeypatch):
    for name, value in [
        ("FOUNDRY_ENDPOINT", SETTINGS.endpoint),
        ("FOUNDRY_DEPLOYMENT", SETTINGS.deployment),
        ("FOUNDRY_API_KEY", SETTINGS.api_key),
    ]:
        monkeypatch.setenv(name, value)
    monkeypatch.setenv(missing, "  ")
    with pytest.raises(FoundryConfigurationError, match=missing):
        FoundrySettings.from_environment()


@pytest.mark.asyncio
async def test_missing_settings_do_not_fall_back_to_legacy_configuration(monkeypatch):
    for name in ["FOUNDRY_ENDPOINT", "FOUNDRY_DEPLOYMENT", "FOUNDRY_API_KEY"]:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("OPENCODE_GO_API_KEY", "legacy-secret")
    monkeypatch.setenv("OPENCODE_GO_MODEL", "legacy-model")
    monkeypatch.setenv("OPENAI_API_KEY", "another-secret")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://another-host.test")

    def handler(request):
        raise AssertionError("no HTTP call or fallback is allowed")

    client = FoundryClient(transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(FoundryConfigurationError, match="FOUNDRY_ENDPOINT"):
            await client.generate_reply("Hello")
    finally:
        await client.close()


@pytest.mark.parametrize(
    "endpoint",
    [
        "",
        "http://test-resource.services.ai.azure.com",
        "https://another-host.test",
        "https://test-resource.services.ai.azure.com/api/projects/test",
        "https://test-resource.services.ai.azure.com/openai/v1",
        "https://test-resource.services.ai.azure.com?api-key=test-secret",
        "https://test-secret@test-resource.services.ai.azure.com",
        "https://test-resource.services.ai.azure.com:8080",
        "https://test-resource.services.ai.azure.com#fragment",
    ],
)
def test_rejects_invalid_endpoint_without_exposing_value(endpoint):
    with pytest.raises(FoundryConfigurationError) as error:
        FoundrySettings(endpoint, "test-deployment", "test-secret")
    assert "test-secret" not in str(error.value)


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://test-resource.services.ai.azure.com/",
        "https://test-resource.openai.azure.com",
    ],
)
def test_accepts_supported_resource_roots(endpoint):
    settings = FoundrySettings(endpoint, "test-deployment", "test-secret")
    assert settings.endpoint == endpoint
    assert "test-secret" not in repr(settings)


@pytest.mark.parametrize("control", ["\n", "\r", "\t", " ", "\x00", "\x7f"])
def test_endpoint_rejects_control_characters(control):
    endpoint = "https://test-resource" + control + ".openai.azure.com"
    with pytest.raises(FoundryConfigurationError, match="FOUNDRY_ENDPOINT"):
        FoundrySettings(endpoint, "test-deployment", "test-secret")


@pytest.mark.parametrize(
    "key", ["sécret", "test\nsecret", "test\tsecret", "test secret", "test\x7fsecret"]
)
def test_invalid_header_credentials_are_reported_safely(key):
    with pytest.raises(FoundryConfigurationError) as error:
        FoundrySettings(SETTINGS.endpoint, "test-deployment", key)
    assert "FOUNDRY_API_KEY" in str(error.value)
    assert key not in str(error.value)
