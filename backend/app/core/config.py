import os
from dataclasses import dataclass
from datetime import timedelta


def _optional_environment_value(name: str) -> str | None:
    value = os.getenv(name)
    if value is None:
        return None

    value = value.strip()
    return value or None


@dataclass(frozen=True)
class RuntimeIdentity:
    commit: str | None = None
    build: str | None = None
    release_id: str | None = None
    environment: str | None = None
    image_digest: str | None = None
    migration_revision: str | None = None
    container_app_revision: str | None = None
    container_app_replica: str | None = None
    container_app_hostname: str | None = None


def get_runtime_identity() -> RuntimeIdentity:
    return RuntimeIdentity(
        commit=_optional_environment_value("APP_GIT_SHA"),
        build=_optional_environment_value("APP_BUILD_ID"),
        release_id=_optional_environment_value("APP_RELEASE_ID"),
        environment=_optional_environment_value("APP_ENVIRONMENT"),
        image_digest=_optional_environment_value("APP_IMAGE_DIGEST"),
        migration_revision=_optional_environment_value("APP_MIGRATION_REVISION"),
        container_app_revision=_optional_environment_value("CONTAINER_APP_REVISION"),
        container_app_replica=_optional_environment_value("CONTAINER_APP_REPLICA_NAME"),
        container_app_hostname=_optional_environment_value("CONTAINER_APP_HOSTNAME"),
    )


def get_frontend_origin() -> str:
    return os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")


def get_detection_grace_period() -> timedelta:
    """Return the configurable rollout grace period, defaulting to five minutes."""

    raw_minutes = os.getenv("RELEASE_DETECTION_GRACE_MINUTES", "5").strip()
    try:
        minutes = float(raw_minutes)
    except ValueError as error:
        raise ValueError("RELEASE_DETECTION_GRACE_MINUTES must be a number") from error
    if minutes < 0:
        raise ValueError("RELEASE_DETECTION_GRACE_MINUTES cannot be negative")
    return timedelta(minutes=minutes)
