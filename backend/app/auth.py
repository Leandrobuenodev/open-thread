from dataclasses import dataclass
from functools import lru_cache
import os
from typing import Any

import httpx
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from jwt.exceptions import PyJWTError
from starlette.concurrency import run_in_threadpool


class EntraConfigurationError(RuntimeError):
    """Raised when the backend is missing required Entra configuration."""


class TokenValidationError(RuntimeError):
    """Raised when an access token cannot be trusted for this API."""


@dataclass(frozen=True)
class AuthenticatedUser:
    """The stable Entra identity extracted from a validated access token."""

    object_id: str
    tenant_id: str


@dataclass(frozen=True)
class EntraAuthSettings:
    authority: str
    audience: str
    required_scope: str

    @classmethod
    def from_environment(cls) -> "EntraAuthSettings":
        return cls(
            authority=_required_environment_value("ENTRA_AUTHORITY"),
            audience=_required_environment_value("ENTRA_API_AUDIENCE"),
            required_scope=_required_environment_value("ENTRA_REQUIRED_SCOPE"),
        )


class EntraTokenValidator:
    """Validate Entra access tokens against the authority's OIDC metadata."""

    def __init__(self, settings: EntraAuthSettings) -> None:
        self._settings = settings
        self._issuer: str | None = None
        self._jwks_client: PyJWKClient | None = None

    def validate(self, token: str) -> AuthenticatedUser:
        try:
            issuer, jwks_client = self._get_discovery_configuration()
            signing_key = jwks_client.get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience=self._settings.audience,
                issuer=issuer,
                options={"require": ["exp", "iss", "aud"]},
            )
            return _authenticated_user_from_claims(
                claims,
                required_scope=self._settings.required_scope,
            )
        except (
            PyJWTError,
            httpx.HTTPError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise TokenValidationError("The access token is invalid.") from exc

    def _get_discovery_configuration(self) -> tuple[str, PyJWKClient]:
        if self._issuer is not None and self._jwks_client is not None:
            return self._issuer, self._jwks_client

        discovery_url = (
            f"{self._settings.authority.rstrip('/')}/"
            ".well-known/openid-configuration"
        )
        with httpx.Client(timeout=10.0, follow_redirects=True) as client:
            response = client.get(discovery_url)
            response.raise_for_status()
            metadata = response.json()

        if not isinstance(metadata, dict):
            raise ValueError("OIDC discovery metadata is not an object.")

        issuer = metadata.get("issuer")
        jwks_uri = metadata.get("jwks_uri")
        if not isinstance(issuer, str) or not issuer:
            raise ValueError("OIDC discovery metadata has no issuer.")
        if not isinstance(jwks_uri, str) or not jwks_uri:
            raise ValueError("OIDC discovery metadata has no jwks_uri.")

        self._issuer = issuer
        self._jwks_client = PyJWKClient(jwks_uri)
        return issuer, self._jwks_client


def _authenticated_user_from_claims(
    claims: dict[str, Any],
    *,
    required_scope: str,
) -> AuthenticatedUser:
    scopes = claims.get("scp")
    if not isinstance(scopes, str) or required_scope not in scopes.split():
        raise TokenValidationError("The access token lacks the required scope.")

    object_id = claims.get("oid")
    tenant_id = claims.get("tid")
    if not isinstance(object_id, str) or not object_id:
        raise TokenValidationError("The access token has no user object ID.")
    if not isinstance(tenant_id, str) or not tenant_id:
        raise TokenValidationError("The access token has no tenant ID.")

    return AuthenticatedUser(object_id=object_id, tenant_id=tenant_id)


bearer_scheme = HTTPBearer(auto_error=False)


@lru_cache
def get_entra_token_validator() -> EntraTokenValidator:
    return EntraTokenValidator(EntraAuthSettings.from_environment())


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> AuthenticatedUser:
    if credentials is None:
        raise _unauthorized("Missing bearer token.")

    try:
        validator = get_entra_token_validator()
        return await run_in_threadpool(
            validator.validate,
            credentials.credentials,
        )
    except EntraConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    except TokenValidationError as exc:
        raise _unauthorized("Invalid bearer token.") from exc


def _required_environment_value(name: str) -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        raise EntraConfigurationError(f"{name} is not configured.")
    return value.strip()


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )
