from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import get_runtime_identity


router = APIRouter(tags=["system"])


class RuntimeVersionResponse(BaseModel):
    status: Literal["ok"] = "ok"
    commit: str | None = None
    build: str | None = None
    release_id: str | None = None
    environment: str | None = None
    image_digest: str | None = None
    migration_revision: str | None = None
    container_app_revision: str | None = None
    container_app_replica: str | None = None
    container_app_hostname: str | None = None


@router.get("/health/version", response_model=RuntimeVersionResponse)
async def health_version() -> RuntimeVersionResponse:
    identity = get_runtime_identity()
    return RuntimeVersionResponse(
        commit=identity.commit,
        build=identity.build,
        release_id=identity.release_id,
        environment=identity.environment,
        image_digest=identity.image_digest,
        migration_revision=identity.migration_revision,
        container_app_revision=identity.container_app_revision,
        container_app_replica=identity.container_app_replica,
        container_app_hostname=identity.container_app_hostname,
    )
