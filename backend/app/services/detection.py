# LEGACY / HISTORICAL / NOT CURRENT ARCHITECTURE: not wired into the chat API.
from datetime import datetime, timedelta

from app.core.config import get_detection_grace_period
from app.domain.release_evidence import (
    CIObservation,
    ContainerAppState,
    Detection,
    DetectionCode,
    Release,
    ReleaseState,
)


_READY_PROVISIONING_STATES = frozenset({"Provisioned"})
_READY_RUNNING_STATES = frozenset({"Running"})
_NON_READY_PROVISIONING_STATES = frozenset(
    {"Provisioning", "Deprovisioning", "Deprovisioned"}
)
_NON_READY_RUNNING_STATES = frozenset({"Processing", "Stopped", "Degraded"})
_IDENTITY_FIELDS = ("image_digest", "commit_sha", "build_id")


class DetectionEngine:
    """Pure release checks over already-collected and normalized evidence."""

    DEFAULT_GRACE_PERIOD = timedelta(minutes=5)

    def __init__(self, grace_period: timedelta | None = None) -> None:
        configured_grace_period = (
            get_detection_grace_period()
            if grace_period is None
            else grace_period
        )
        if configured_grace_period < timedelta(0):
            raise ValueError("grace_period cannot be negative")
        self.grace_period = configured_grace_period

    def evaluate(
        self,
        release: Release,
        observation_time: datetime | None = None,
    ) -> list[Detection]:
        observed_at = observation_time or release.observed_at
        return [
            self._deployment_revision_not_ready(release, observed_at),
            self._revision_activation_failed(release),
            self._zero_ready_replicas(release, observed_at),
            self._latest_revision_not_ready(release, observed_at),
            self._deployed_artifact_mismatch(release),
            self._serving_version_mismatch(release),
            self._traffic_not_shifted(release),
            self._previous_release_serving(release),
        ]

    def _deployment_revision_not_ready(
        self, release: Release, observed_at: datetime | None
    ) -> Detection:
        expected = release.expected
        deployed = release.deployed
        if not expected.revision_name or not deployed.revision_name:
            return _insufficient(
                "deployment_revision_not_ready",
                "Expected and deployed revision names are required.",
            )
        if expected.revision_name != deployed.revision_name:
            return _not_applicable(
                "deployment_revision_not_ready",
                "The deployed revision is not the expected revision, so its readiness is not attributed to this release.",
            )
        ci_succeeded = _ci_succeeded(expected)
        if ci_succeeded is None:
            return _insufficient(
                "deployment_revision_not_ready",
                "Normalized CI status and result are required.",
            )
        if not ci_succeeded:
            return _not_applicable(
                "deployment_revision_not_ready",
                "The expected pipeline did not complete successfully, so this release is not evaluated as a failed deployment.",
                _ci_evidence(expected),
            )

        container = _container_state(deployed)
        readiness = _readiness_status(container)
        if readiness is None:
            return _insufficient(
                "deployment_revision_not_ready",
                "Normalized Container Apps readiness evidence is unavailable or inconclusive.",
            )
        if readiness:
            return _pass(
                "deployment_revision_not_ready",
                "The expected deployed revision reports a ready state.",
                _container_evidence(container),
            )
        if _scale_to_zero_without_serving_traffic(release, container):
            return _not_applicable(
                "deployment_revision_not_ready",
                "The revision is compatible with scale-to-zero and is not confirmed as expected to serve traffic.",
                _container_evidence(container),
            )
        return self._readiness_detection(
            code="deployment_revision_not_ready",
            release=release,
            observed_at=observed_at,
            reason="The expected deployed revision is not ready.",
            evidence=_container_evidence(container),
        )

    def _revision_activation_failed(self, release: Release) -> Detection:
        container = _container_state(release.deployed)
        failure_evidence = _activation_failure_evidence(container)
        if failure_evidence:
            return _detected(
                "revision_activation_failed",
                "Normalized Container Apps provisioning or runtime evidence reports an activation failure.",
                failure_evidence,
            )
        if not _has_activation_evidence(container):
            return _insufficient(
                "revision_activation_failed",
                "Normalized provisioning, running, health, error, or positive replica evidence is required.",
            )
        return _pass(
            "revision_activation_failed",
            "The normalized Container Apps evidence does not report an activation failure.",
            _container_evidence(container),
        )

    def _zero_ready_replicas(
        self, release: Release, observed_at: datetime | None
    ) -> Detection:
        container = _container_state(release.deployed)
        replicas = container.ready_replicas
        if replicas is None:
            return _insufficient(
                "zero_ready_replicas",
                "The deployed ready replica count is unavailable.",
            )
        if replicas > 0:
            return _pass(
                "zero_ready_replicas",
                "The deployed revision has ready replicas.",
                [f"ready_replicas={replicas}"],
            )
        if container.min_replicas == 0 and not _expected_to_serve(release):
            return _not_applicable(
                "zero_ready_replicas",
                "Zero ready replicas are compatible with the configured scale-to-zero minimum.",
                ["ready_replicas=0", "min_replicas=0"],
            )
        if not _expected_to_serve(release):
            return _insufficient(
                "zero_ready_replicas",
                "Zero replicas alone do not establish that this revision was expected to be active or serving.",
                ["ready_replicas=0"],
            )
        return self._readiness_detection(
            code="zero_ready_replicas",
            release=release,
            observed_at=observed_at,
            reason="The revision expected to serve traffic has zero ready replicas.",
            evidence=["ready_replicas=0"],
        )

    def _latest_revision_not_ready(
        self, release: Release, observed_at: datetime | None
    ) -> Detection:
        deployed = release.deployed
        latest = deployed.latest_revision_name
        latest_ready = deployed.latest_ready_revision_name
        if not latest or not latest_ready:
            return _insufficient(
                "latest_revision_not_ready",
                "Latest and latest ready revision names are required.",
            )
        if latest == latest_ready:
            return _pass(
                "latest_revision_not_ready",
                "The latest revision is also the latest ready revision.",
                [f"latest_revision={latest}"],
            )
        container = _container_state(deployed)
        if _scale_to_zero_without_serving_traffic(release, container):
            return _not_applicable(
                "latest_revision_not_ready",
                "The revision is compatible with scale-to-zero and is not confirmed as expected to serve traffic.",
                [f"latest_revision={latest}", f"latest_ready_revision={latest_ready}"],
            )
        return self._readiness_detection(
            code="latest_revision_not_ready",
            release=release,
            observed_at=observed_at,
            reason="The latest revision is not the latest ready revision.",
            evidence=[
                f"latest_revision={latest}",
                f"latest_ready_revision={latest_ready}",
            ],
        )

    def _deployed_artifact_mismatch(self, release: Release) -> Detection:
        expected_digest = release.expected.image_digest
        deployed_digest = release.deployed.image_digest
        if not expected_digest or not deployed_digest:
            return _insufficient(
                "deployed_artifact_mismatch",
                "Expected and deployed image digests are required.",
            )
        if expected_digest == deployed_digest:
            return _pass(
                "deployed_artifact_mismatch",
                "Expected and deployed image digests match.",
                [f"image_digest={expected_digest}"],
            )
        return _detected(
            "deployed_artifact_mismatch",
            "The deployed image digest differs from the expected artifact.",
            [
                f"expected_image_digest={expected_digest}",
                f"deployed_image_digest={deployed_digest}",
            ],
        )

    def _serving_version_mismatch(self, release: Release) -> Detection:
        comparisons = [
            (
                field,
                getattr(release.expected, field),
                getattr(release.serving, field),
            )
            for field in _IDENTITY_FIELDS
            if getattr(release.expected, field) is not None
            and getattr(release.serving, field) is not None
        ]
        if not comparisons:
            return _insufficient(
                "serving_version_mismatch",
                "A comparable serving identity requires an image digest, commit, or build value on both sides.",
            )
        mismatches = [
            f"{field}: expected={expected}, serving={serving}"
            for field, expected, serving in comparisons
            if expected != serving
        ]
        strength = _identity_strength(comparisons)
        if mismatches:
            return _detected(
                "serving_version_mismatch",
                "The serving runtime identity differs from the expected release.",
                [f"identity_strength={strength}", *mismatches],
            )
        return _pass(
            "serving_version_mismatch",
            "The comparable serving runtime identity fields match the expected release.",
            [f"identity_strength={strength}"]
            + [f"{field}={expected}" for field, expected, _ in comparisons],
        )

    def _traffic_not_shifted(self, release: Release) -> Detection:
        expected_revision = release.expected.revision_name
        traffic = release.serving.traffic_weights
        if not expected_revision or not traffic:
            return _insufficient(
                "traffic_not_shifted",
                "Expected revision and serving traffic allocation are required.",
            )
        ci_succeeded = _ci_succeeded(release.expected)
        if ci_succeeded is None:
            return _insufficient(
                "traffic_not_shifted",
                "Normalized CI status and result are required.",
            )
        if not ci_succeeded:
            return _not_applicable(
                "traffic_not_shifted",
                "The expected pipeline did not complete successfully, so traffic shift is not evaluated for this release.",
                _ci_evidence(release.expected),
            )
        expected_weight = traffic.get(expected_revision)
        if expected_weight is None:
            previous_weight = sum(traffic.values())
            if previous_weight <= 0:
                return _insufficient(
                    "traffic_not_shifted",
                    "The expected revision is absent from the serving traffic allocation, but no other traffic is confirmed.",
                    [f"expected_revision={expected_revision}"],
                )
            return _detected(
                "traffic_not_shifted",
                "The expected revision is absent from the serving traffic allocation while another revision receives traffic.",
                [
                    f"expected_revision={expected_revision}",
                    f"previous_revision_weight={previous_weight}",
                ],
            )
        previous_weight = sum(
            weight for revision, weight in traffic.items() if revision != expected_revision
        )
        if expected_weight > 0:
            return _pass(
                "traffic_not_shifted",
                "The expected revision receives traffic.",
                [f"expected_revision_weight={expected_weight}"],
            )
        if previous_weight <= 0:
            return _insufficient(
                "traffic_not_shifted",
                "The expected revision receives no traffic, but no previous traffic is confirmed.",
                [f"expected_revision_weight={expected_weight}"],
            )
        return _detected(
            "traffic_not_shifted",
            "Traffic remains allocated to a different revision.",
            [
                f"expected_revision={expected_revision}",
                f"expected_revision_weight={expected_weight}",
                f"previous_revision_weight={previous_weight}",
            ],
        )

    def _previous_release_serving(self, release: Release) -> Detection:
        expected_revision = release.expected.revision_name
        serving_revision = release.serving.revision_name
        if not expected_revision or not serving_revision:
            return _insufficient(
                "previous_release_serving",
                "Expected and serving revision names are required.",
            )
        ci_succeeded = _ci_succeeded(release.expected)
        if ci_succeeded is None:
            return _insufficient(
                "previous_release_serving",
                "Normalized CI status and result are required.",
            )
        if not ci_succeeded:
            return _not_applicable(
                "previous_release_serving",
                "The expected pipeline did not complete successfully, so a previous serving revision is not evaluated for this release.",
                _ci_evidence(release.expected),
            )
        if expected_revision == serving_revision:
            return _pass(
                "previous_release_serving",
                "The expected revision is serving.",
                [f"serving_revision={serving_revision}"],
            )
        return _detected(
            "previous_release_serving",
            "A different revision is serving instead of the expected release.",
            [
                f"expected_revision={expected_revision}",
                f"serving_revision={serving_revision}",
            ],
        )

    def _readiness_detection(
        self,
        code: DetectionCode,
        release: Release,
        observed_at: datetime | None,
        reason: str,
        evidence: list[str],
    ) -> Detection:
        within_grace = _within_grace_period(
            release.revision_created_at,
            observed_at,
            self.grace_period,
        )
        if within_grace is None:
            return _insufficient(
                code,
                f"{reason} The revision creation and observation times are required to evaluate the grace period.",
                evidence,
            )
        if within_grace:
            return _pass(
                code,
                f"{reason} The observation is still inside the configured rollout grace period.",
                evidence,
            )
        return _detected(code, reason, evidence)


def _ci_observation(expected: ReleaseState) -> CIObservation | None:
    if expected.ci is not None:
        return expected.ci
    if any(
        value is not None
        for value in (
            expected.ci_status,
            expected.ci_result,
            expected.ci_raw_status,
            expected.ci_raw_result,
        )
    ):
        return CIObservation(
            status=expected.ci_status,
            result=expected.ci_result,
            raw_status=expected.ci_raw_status,
            raw_result=expected.ci_raw_result,
        )
    return None


def _ci_succeeded(expected: ReleaseState) -> bool | None:
    observation = _ci_observation(expected)
    if observation is None or observation.status is None or observation.result is None:
        return None
    return observation.status == "completed" and observation.result == "succeeded"


def _ci_evidence(expected: ReleaseState) -> list[str]:
    observation = _ci_observation(expected)
    if observation is None:
        return []
    return [
        f"ci_status={observation.status}",
        f"ci_result={observation.result}",
    ]


def _container_state(state: ReleaseState) -> ContainerAppState:
    if state.container_app is not None:
        return state.container_app
    return ContainerAppState(
        provisioning_state=state.provisioning_state,
        running_state=state.running_state,
        health_state=state.health_state,
        provisioning_error=state.provisioning_error,
        ready_replicas=state.ready_replicas,
        min_replicas=state.min_replicas,
        raw_provider_state=state.raw_provider_state,
    )


def _activation_failure_evidence(container: ContainerAppState) -> list[str]:
    evidence: list[str] = []
    if container.provisioning_state == "Failed":
        evidence.append("provisioning_state=Failed")
    if container.running_state == "Failed":
        evidence.append("running_state=Failed")
    if container.health_state == "Unhealthy":
        evidence.append("health_state=Unhealthy")
    if container.provisioning_error:
        evidence.append(f"provisioning_error={container.provisioning_error}")
    return evidence


def _has_activation_evidence(container: ContainerAppState) -> bool:
    return bool(
        container.provisioning_state
        or container.running_state
        or container.health_state
        or container.provisioning_error
        or (container.ready_replicas is not None and container.ready_replicas > 0)
    )


def _readiness_status(container: ContainerAppState) -> bool | None:
    if _activation_failure_evidence(container):
        return False
    if container.ready_replicas is not None and container.ready_replicas > 0:
        return True
    if container.provisioning_state in _NON_READY_PROVISIONING_STATES:
        return False
    if container.running_state in _NON_READY_RUNNING_STATES:
        return False
    if container.health_state == "Unhealthy":
        return False
    if (
        container.provisioning_state in _READY_PROVISIONING_STATES
        and container.running_state in (None, *_READY_RUNNING_STATES)
        and container.health_state in (None, "Healthy", "None")
    ):
        return True
    if (
        container.running_state in _READY_RUNNING_STATES
        and container.health_state in (None, "Healthy", "None")
    ):
        return True
    if container.health_state == "Healthy":
        return True
    return None


def _container_evidence(container: ContainerAppState) -> list[str]:
    evidence: list[str] = []
    for name in (
        "provisioning_state",
        "running_state",
        "health_state",
        "provisioning_error",
        "ready_replicas",
        "min_replicas",
    ):
        value = getattr(container, name)
        if value is not None:
            evidence.append(f"{name}={value}")
    return evidence


def _expected_to_serve(release: Release) -> bool:
    expected_revision = release.expected.revision_name
    if not expected_revision or release.deployed.revision_name != expected_revision:
        return False
    return release.serving.traffic_weights.get(expected_revision, 0) > 0


def _scale_to_zero_without_serving_traffic(
    release: Release, container: ContainerAppState
) -> bool:
    return container.min_replicas == 0 and not _expected_to_serve(release)


def _identity_strength(
    comparisons: list[tuple[str, str, str]],
) -> str:
    compared_fields = {field for field, _, _ in comparisons}
    if "image_digest" in compared_fields:
        return "image_digest"
    if {"commit_sha", "build_id"}.issubset(compared_fields):
        return "commit+build"
    if "commit_sha" in compared_fields:
        return "commit-only"
    return "build-only"


def _within_grace_period(
    revision_created_at: datetime | None,
    observed_at: datetime | None,
    grace_period: timedelta,
) -> bool | None:
    if revision_created_at is None or observed_at is None:
        return None
    return observed_at - revision_created_at < grace_period


def _detected(
    code: DetectionCode, reason: str, evidence: list[str] | None = None
) -> Detection:
    return Detection(
        code=code,
        status="DETECTED",
        reason=reason,
        evidence=evidence or [],
    )


def _pass(
    code: DetectionCode, reason: str, evidence: list[str] | None = None
) -> Detection:
    return Detection(
        code=code,
        status="PASS",
        reason=reason,
        evidence=evidence or [],
    )


def _not_applicable(
    code: DetectionCode, reason: str, evidence: list[str] | None = None
) -> Detection:
    return Detection(
        code=code,
        status="NOT_APPLICABLE",
        reason=reason,
        evidence=evidence or [],
    )


def _insufficient(
    code: DetectionCode, reason: str, evidence: list[str] | None = None
) -> Detection:
    return Detection(
        code=code,
        status="INSUFFICIENT_EVIDENCE",
        reason=reason,
        evidence=evidence or [],
    )
