from datetime import datetime, timedelta, timezone

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

import app.auth as auth
from app.auth import (
    AuthenticatedUser,
    EntraAuthSettings,
    EntraTokenValidator,
    TokenValidationError,
    _authenticated_user_from_claims,
    get_current_user,
)


class FakeTokenValidator:
    def validate(self, token: str) -> AuthenticatedUser:
        assert token == "token"
        return AuthenticatedUser(object_id="user-object-id", tenant_id="tenant-id")


class FakeSigningKey:
    def __init__(self, key) -> None:
        self.key = key


class FakeJWKClient:
    def __init__(self, key) -> None:
        self._key = key

    def get_signing_key_from_jwt(self, token: str) -> FakeSigningKey:
        assert token
        return FakeSigningKey(self._key)


def _validator_with_key() -> tuple[EntraTokenValidator, rsa.RSAPrivateKey]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    validator = EntraTokenValidator(
        EntraAuthSettings(
            authority="https://login.microsoftonline.com/tenant-id/v2.0",
            audience="api-client-id",
            required_scope="chat.access",
        )
    )
    validator._issuer = "https://login.microsoftonline.com/tenant-id/v2.0"
    validator._jwks_client = FakeJWKClient(private_key.public_key())
    return validator, private_key


def _token(private_key: rsa.RSAPrivateKey, **overrides: object) -> str:
    claims: dict[str, object] = {
        "iss": "https://login.microsoftonline.com/tenant-id/v2.0",
        "aud": "api-client-id",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        "oid": "user-object-id",
        "tid": "tenant-id",
        "scp": "chat.access",
    }
    claims.update(overrides)
    return jwt.encode(claims, private_key, algorithm="RS256")


def test_validator_checks_jwt_claims_and_extracts_identity() -> None:
    validator, private_key = _validator_with_key()

    user = validator.validate(_token(private_key))

    assert user == AuthenticatedUser(
        object_id="user-object-id",
        tenant_id="tenant-id",
    )


@pytest.mark.parametrize(
    "overrides",
    [
        {"aud": "another-api"},
        {"iss": "https://untrusted-issuer.test"},
        {"exp": datetime.now(timezone.utc) - timedelta(minutes=5)},
        {"scp": "another.scope"},
    ],
)
def test_validator_rejects_incompatible_token_claims(
    overrides: dict[str, object],
) -> None:
    validator, private_key = _validator_with_key()

    with pytest.raises(TokenValidationError):
        validator.validate(_token(private_key, **overrides))


def test_extracts_stable_identity_from_validated_claims() -> None:
    user = _authenticated_user_from_claims(
        {
            "oid": "user-object-id",
            "tid": "tenant-id",
            "scp": "chat.access other.scope",
        },
        required_scope="chat.access",
    )

    assert user == AuthenticatedUser(
        object_id="user-object-id",
        tenant_id="tenant-id",
    )


@pytest.mark.asyncio
async def test_current_user_uses_validated_token_claims(monkeypatch) -> None:
    monkeypatch.setattr(
        auth,
        "get_entra_token_validator",
        lambda: FakeTokenValidator(),
    )

    user = await get_current_user(
        HTTPAuthorizationCredentials(scheme="Bearer", credentials="token")
    )

    assert user == AuthenticatedUser(
        object_id="user-object-id",
        tenant_id="tenant-id",
    )


@pytest.mark.asyncio
async def test_current_user_rejects_missing_credentials() -> None:
    with pytest.raises(HTTPException) as error:
        await get_current_user(None)

    assert error.value.status_code == 401
    assert error.value.headers == {"WWW-Authenticate": "Bearer"}


@pytest.mark.asyncio
async def test_current_user_rejects_invalid_token(monkeypatch) -> None:
    class InvalidTokenValidator:
        def validate(self, token: str) -> AuthenticatedUser:
            raise TokenValidationError("invalid")

    monkeypatch.setattr(
        auth,
        "get_entra_token_validator",
        lambda: InvalidTokenValidator(),
    )

    with pytest.raises(HTTPException) as error:
        await get_current_user(
            HTTPAuthorizationCredentials(
                scheme="Bearer",
                credentials="invalid-token",
            )
        )

    assert error.value.status_code == 401
    assert error.value.headers == {"WWW-Authenticate": "Bearer"}


def test_validator_rejects_wrong_signature():
    validator, _ = _validator_with_key()
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    with pytest.raises(TokenValidationError):
        validator.validate(_token(other_key))
