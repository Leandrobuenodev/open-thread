# LEGACY / HISTORICAL / NOT CURRENT ARCHITECTURE: not wired into the chat API.
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


ProvisioningState = Literal[
    "Provisioning",
    "Provisioned",
    "Failed",
    "Deprovisioning",
    "Deprovisioned",
]
RunningState = Literal[
    "Running",
    "Processing",
    "Stopped",
    "Degraded",
    "Failed",
    "Unknown",
]
HealthState = Literal["Healthy", "Unhealthy", "None"]
CIStatus = Literal[
    "notStarted",
    "inProgress",
    "completed",
    "cancelling",
    "postponed",
    "none",
]
CIResult = Literal[
    "succeeded",
    "partiallySucceeded",
    "failed",
    "canceled",
    "none",
]

DetectionCode = Literal[
    "deployment_revision_not_ready",
    "revision_activation_failed",
    "zero_ready_replicas",
    "latest_revision_not_ready",
    "deployed_artifact_mismatch",
    "serving_version_mismatch",
    "traffic_not_shifted",
    "previous_release_serving",
]

DetectionStatus = Literal[
    "PASS",
    "DETECTED",
    "INSUFFICIENT_EVIDENCE",
    "NOT_APPLICABLE",
]


class CIObservation(BaseModel):
    """Normalized CI status/result with the provider values retained."""

    status: CIStatus | None = None
    result: CIResult | None = None
    raw_status: str | None = None
    raw_result: str | None = None


def normalize_ci_observation(
    raw_status: str | None,
    raw_result: str | None,
) -> CIObservation:
    """Map provider CI values while retaining both raw fields."""

    statuses = {
        "notstarted": "notStarted",
        "inprogress": "inProgress",
        "completed": "completed",
        "cancelling": "cancelling",
        "postponed": "postponed",
        "none": "none",
    }
    results = {
        "succeeded": "succeeded",
        "partiallysucceeded": "partiallySucceeded",
        "failed": "failed",
        "canceled": "canceled",
        "none": "none",
    }
    return CIObservation(
        status=statuses.get(raw_status.strip().casefold()) if raw_status else None,
        result=results.get(raw_result.strip().casefold()) if raw_result else None,
        raw_status=raw_status,
        raw_result=raw_result,
    )


class ContainerAppState(BaseModel):
    """Normalized Azure Container Apps revision evidence.

    Provider responses are intentionally not modeled as if they already used
    these names. Adapters can retain the original response in
    ``raw_provider_state`` while mapping its values into these product-facing
    concepts.
    """

    provisioning_state: ProvisioningState | None = None
    running_state: RunningState | None = None
    health_state: HealthState | None = None
    provisioning_error: str | None = None
    ready_replicas: int | None = Field(default=None, ge=0)
    min_replicas: int | None = Field(default=None, ge=0)
    raw_provider_state: dict[str, Any] = Field(default_factory=dict)


def normalize_container_app_state(
    *,
    provisioning_state: str | None = None,
    running_state: str | None = None,
    health_state: str | None = None,
    provisioning_error: str | None = None,
    ready_replicas: int | None = None,
    min_replicas: int | None = None,
    raw_provider_state: dict[str, Any] | None = None,
) -> ContainerAppState:
    """Normalize Container Apps concepts without discarding provider values."""

    provisioning_states = {
        value.casefold(): value
        for value in ("Provisioning", "Provisioned", "Failed", "Deprovisioning", "Deprovisioned")
    }
    running_states = {
        value.casefold(): value
        for value in ("Running", "Processing", "Stopped", "Degraded", "Failed", "Unknown")
    }
    health_states = {value.casefold(): value for value in ("Healthy", "Unhealthy", "None")}
    raw = dict(raw_provider_state or {})
    for name, value in (
        ("provisioning_state", provisioning_state),
        ("running_state", running_state),
        ("health_state", health_state),
        ("provisioning_error", provisioning_error),
        ("ready_replicas", ready_replicas),
        ("min_replicas", min_replicas),
    ):
        if value is not None:
            raw.setdefault(name, value)
    return ContainerAppState(
        provisioning_state=(
            provisioning_states.get(provisioning_state.strip().casefold())
            if provisioning_state
            else None
        ),
        running_state=(
            running_states.get(running_state.strip().casefold())
            if running_state
            else None
        ),
        health_state=(
            health_states.get(health_state.strip().casefold()) if health_state else None
        ),
        provisioning_error=provisioning_error,
        ready_replicas=ready_replicas,
        min_replicas=min_replicas,
        raw_provider_state=raw,
    )


class Evidence(BaseModel):
    """One evidence item and the timestamps needed to keep observations ordered."""

    kind: str = Field(min_length=1)
    value: str | None = None
    payload: dict[str, Any] | None = None
    source_system: str = Field(min_length=1)
    source_reference: str | None = None
    observed_at: datetime | None = None
    platform_observed_at: datetime | None = None
    runtime_probe_requested_at: datetime | None = None
    runtime_response_observed_at: datetime | None = None


class ReleaseState(BaseModel):
    """A state snapshot for one side of EXPECTED, DEPLOYED, or SERVING."""

    revision_name: str | None = None
    image_digest: str | None = None
    commit_sha: str | None = None
    build_id: str | None = None
    release_id: str | None = None
    migration_revision: str | None = None

    # Expected CI evidence is kept as separate status and result concepts.
    # The flat fields are convenient when building a snapshot; ``ci`` provides
    # the same structure with provider values retained for adapter output.
    ci: CIObservation | None = None
    ci_status: CIStatus | None = None
    ci_result: CIResult | None = None
    ci_raw_status: str | None = None
    ci_raw_result: str | None = None

    # ``container_app`` is the canonical normalized platform evidence. The
    # flattened fields are accepted as a small compatibility seam for callers
    # that already construct ReleaseState snapshots directly.
    container_app: ContainerAppState | None = None
    provisioning_state: ProvisioningState | None = None
    running_state: RunningState | None = None
    health_state: HealthState | None = None
    provisioning_error: str | None = None
    ready_replicas: int | None = Field(default=None, ge=0)
    min_replicas: int | None = Field(default=None, ge=0)
    raw_provider_state: dict[str, Any] = Field(default_factory=dict)

    latest_revision_name: str | None = None
    latest_ready_revision_name: str | None = None
    traffic_weights: dict[str, int] = Field(default_factory=dict)


class Release(BaseModel):
    """Correlated evidence with expected, deployed, and serving kept apart."""

    release_id: str = Field(min_length=1)
    environment: str = Field(min_length=1)
    expected: ReleaseState = Field(default_factory=ReleaseState)
    deployed: ReleaseState = Field(default_factory=ReleaseState)
    serving: ReleaseState = Field(default_factory=ReleaseState)
    evidence: list[Evidence] = Field(default_factory=list)
    revision_created_at: datetime | None = None
    observed_at: datetime | None = None


class Detection(BaseModel):
    code: DetectionCode
    status: DetectionStatus
    reason: str
    evidence: list[str] = Field(default_factory=list)
