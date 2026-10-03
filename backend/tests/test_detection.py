from datetime import datetime, timedelta, timezone

from app.domain.release_evidence import (
    CIObservation,
    ContainerAppState,
    Evidence,
    Release,
    ReleaseState,
    normalize_ci_observation,
    normalize_container_app_state,
)
from app.services.detection import DetectionEngine


CREATED_AT = datetime(2026, 9, 22, 9, 0, tzinfo=timezone.utc)
OBSERVED_AT = datetime(2026, 9, 22, 9, 10, tzinfo=timezone.utc)


def release_with_new_revision(**overrides: object) -> Release:
    values: dict[str, object] = {
        "release_id": "release-2",
        "environment": "dev",
        "expected": ReleaseState(
            revision_name="revision-2",
            image_digest="sha256:new",
            commit_sha="commit-2",
            build_id="build-2",
            release_id="release-2",
            ci=CIObservation(status="completed", result="succeeded"),
        ),
        "deployed": ReleaseState(
            revision_name="revision-2",
            image_digest="sha256:new",
            container_app=ContainerAppState(
                provisioning_state="Provisioned",
                running_state="Running",
                health_state="Healthy",
                ready_replicas=2,
            ),
            latest_revision_name="revision-2",
            latest_ready_revision_name="revision-2",
        ),
        "serving": ReleaseState(
            revision_name="revision-2",
            image_digest="sha256:new",
            commit_sha="commit-2",
            build_id="build-2",
            release_id="release-2",
            traffic_weights={"revision-2": 100},
        ),
        "revision_created_at": CREATED_AT,
        "observed_at": OBSERVED_AT,
    }
    values.update(overrides)
    return Release(**values)


def detection_by_code(release: Release) -> dict[str, str]:
    return {
        detection.code: detection.status
        for detection in DetectionEngine().evaluate(release)
    }


def test_healthy_release_has_no_failure_detections() -> None:
    statuses = detection_by_code(release_with_new_revision())

    assert all(status == "PASS" for status in statuses.values())


def test_activation_failure_reports_definitive_runtime_failures() -> None:
    release = release_with_new_revision(
        deployed=ReleaseState(
            revision_name="revision-2",
            image_digest="sha256:new",
            container_app=ContainerAppState(
                provisioning_state="Failed",
                running_state="Failed",
                health_state="Unhealthy",
                provisioning_error="revision could not start",
                ready_replicas=0,
            ),
            latest_revision_name="revision-2",
            latest_ready_revision_name="revision-1",
        ),
        serving=ReleaseState(
            revision_name="revision-1",
            commit_sha="commit-1",
            release_id="release-1",
            traffic_weights={"revision-1": 100},
        ),
    )

    statuses = detection_by_code(release)

    assert statuses["revision_activation_failed"] == "DETECTED"
    assert statuses["deployment_revision_not_ready"] == "DETECTED"
    assert statuses["zero_ready_replicas"] == "INSUFFICIENT_EVIDENCE"
    assert statuses["latest_revision_not_ready"] == "DETECTED"
    assert statuses["traffic_not_shifted"] == "DETECTED"
    assert statuses["previous_release_serving"] == "DETECTED"
    assert statuses["serving_version_mismatch"] == "DETECTED"


def test_old_release_serving_is_detected_after_new_release_is_ready() -> None:
    release = release_with_new_revision(
        serving=ReleaseState(
            revision_name="revision-1",
            image_digest="sha256:old",
            commit_sha="commit-1",
            build_id="build-1",
            release_id="release-1",
            traffic_weights={"revision-1": 100},
        )
    )

    statuses = detection_by_code(release)

    assert statuses["serving_version_mismatch"] == "DETECTED"
    assert statuses["traffic_not_shifted"] == "DETECTED"
    assert statuses["previous_release_serving"] == "DETECTED"
    assert statuses["deployment_revision_not_ready"] == "PASS"


def test_rollout_inside_grace_period_is_not_reported_as_broken() -> None:
    release = release_with_new_revision(
        deployed=ReleaseState(
            revision_name="revision-2",
            image_digest="sha256:new",
            container_app=ContainerAppState(
                provisioning_state="Provisioning",
                ready_replicas=0,
            ),
            latest_revision_name="revision-2",
            latest_ready_revision_name="revision-1",
        ),
        observed_at=datetime(2026, 9, 22, 9, 2, tzinfo=timezone.utc),
    )

    statuses = detection_by_code(release)

    assert statuses["deployment_revision_not_ready"] == "PASS"
    assert statuses["zero_ready_replicas"] == "PASS"
    assert statuses["latest_revision_not_ready"] == "PASS"


def test_zero_replicas_with_insufficient_context_does_not_imply_failure() -> None:
    release = release_with_new_revision(
        deployed=ReleaseState(
            revision_name="revision-2",
            container_app=ContainerAppState(ready_replicas=0),
            latest_revision_name="revision-2",
            latest_ready_revision_name="revision-2",
        ),
        serving=ReleaseState(),
    )

    statuses = detection_by_code(release)

    assert statuses["zero_ready_replicas"] == "INSUFFICIENT_EVIDENCE"
    assert statuses["revision_activation_failed"] != "DETECTED"


def test_scale_to_zero_compatible_state_is_not_a_false_positive() -> None:
    release = release_with_new_revision(
        deployed=ReleaseState(
            revision_name="revision-2",
            container_app=ContainerAppState(
                running_state="Stopped",
                ready_replicas=0,
                min_replicas=0,
            ),
            latest_revision_name="revision-2",
            latest_ready_revision_name="revision-1",
        ),
        serving=ReleaseState(),
    )

    statuses = detection_by_code(release)

    assert statuses["zero_ready_replicas"] == "NOT_APPLICABLE"
    assert statuses["deployment_revision_not_ready"] == "NOT_APPLICABLE"
    assert statuses["latest_revision_not_ready"] == "NOT_APPLICABLE"


def test_zero_replicas_can_detect_when_scale_to_zero_revision_should_serve() -> None:
    release = release_with_new_revision(
        deployed=ReleaseState(
            revision_name="revision-2",
            container_app=ContainerAppState(
                ready_replicas=0,
                min_replicas=0,
            ),
            latest_revision_name="revision-2",
            latest_ready_revision_name="revision-1",
        )
    )

    statuses = detection_by_code(release)

    assert statuses["zero_ready_replicas"] == "DETECTED"


def test_rollout_after_grace_period_can_detect_not_ready_state() -> None:
    release = release_with_new_revision(
        deployed=ReleaseState(
            revision_name="revision-2",
            container_app=ContainerAppState(
                provisioning_state="Provisioning",
                ready_replicas=0,
            ),
            latest_revision_name="revision-2",
            latest_ready_revision_name="revision-1",
        )
    )

    statuses = detection_by_code(release)

    assert statuses["deployment_revision_not_ready"] == "DETECTED"
    assert statuses["zero_ready_replicas"] == "DETECTED"
    assert statuses["latest_revision_not_ready"] == "DETECTED"


def test_missing_digest_does_not_create_artifact_or_serving_mismatch() -> None:
    release = release_with_new_revision(
        expected=ReleaseState(
            revision_name="revision-2",
            commit_sha="commit-2",
            build_id="build-2",
            release_id="release-2",
            ci=CIObservation(status="completed", result="succeeded"),
        ),
        deployed=ReleaseState(
            revision_name="revision-2",
            container_app=ContainerAppState(
                provisioning_state="Provisioned",
                running_state="Running",
                health_state="Healthy",
                ready_replicas=2,
            ),
            latest_revision_name="revision-2",
            latest_ready_revision_name="revision-2",
        ),
        serving=ReleaseState(
            revision_name="revision-2",
            commit_sha="commit-2",
            build_id="build-2",
            release_id="release-2",
            traffic_weights={"revision-2": 100},
        ),
    )

    statuses = detection_by_code(release)

    assert statuses["deployed_artifact_mismatch"] == "INSUFFICIENT_EVIDENCE"
    assert statuses["serving_version_mismatch"] == "PASS"
    assert not any(status == "DETECTED" for status in statuses.values())


def test_serving_digest_match_is_a_strong_pass() -> None:
    detection = next(
        detection
        for detection in DetectionEngine().evaluate(release_with_new_revision())
        if detection.code == "serving_version_mismatch"
    )

    assert detection.status == "PASS"
    assert "identity_strength=image_digest" in detection.evidence


def test_missing_serving_identity_is_insufficient_evidence() -> None:
    release = release_with_new_revision(
        serving=ReleaseState(
            revision_name="revision-2",
            traffic_weights={"revision-2": 100},
        )
    )

    statuses = detection_by_code(release)

    assert statuses["serving_version_mismatch"] == "INSUFFICIENT_EVIDENCE"


def test_commit_mismatch_is_detected_when_digest_is_unavailable() -> None:
    release = release_with_new_revision(
        expected=ReleaseState(
            revision_name="revision-2",
            commit_sha="commit-expected",
            ci=CIObservation(status="completed", result="succeeded"),
        ),
        serving=ReleaseState(
            revision_name="revision-2",
            commit_sha="commit-serving",
            traffic_weights={"revision-2": 100},
        ),
    )

    statuses = detection_by_code(release)

    assert statuses["serving_version_mismatch"] == "DETECTED"


def test_ci_success_requires_completed_and_succeeded() -> None:
    normalized = normalize_ci_observation("completed", "partiallySucceeded")
    assert normalized.status == "completed"
    assert normalized.result == "partiallySucceeded"
    assert normalized.raw_status == "completed"
    assert normalized.raw_result == "partiallySucceeded"

    release = release_with_new_revision(
        expected=ReleaseState(
            revision_name="revision-2",
            ci=normalized,
        ),
        deployed=ReleaseState(
            revision_name="revision-2",
            container_app=ContainerAppState(provisioning_state="Failed"),
            latest_revision_name="revision-2",
            latest_ready_revision_name="revision-1",
        ),
    )

    statuses = detection_by_code(release)

    assert statuses["deployment_revision_not_ready"] == "NOT_APPLICABLE"


def test_container_state_normalization_preserves_provider_values() -> None:
    normalized = normalize_container_app_state(
        provisioning_state="provisioned",
        running_state="running",
        health_state="none",
        raw_provider_state={"providerStatus": "Provisioned"},
    )

    assert normalized.provisioning_state == "Provisioned"
    assert normalized.running_state == "Running"
    assert normalized.health_state == "None"
    assert normalized.raw_provider_state == {
        "providerStatus": "Provisioned",
        "provisioning_state": "provisioned",
        "running_state": "running",
        "health_state": "none",
    }


def test_runtime_probe_timestamps_preserve_observation_order() -> None:
    platform_observed_at = datetime(2026, 9, 22, 9, 0, tzinfo=timezone.utc)
    runtime_probe_requested_at = datetime(2026, 9, 22, 9, 1, tzinfo=timezone.utc)
    runtime_response_observed_at = datetime(2026, 9, 22, 9, 2, tzinfo=timezone.utc)

    evidence = Evidence(
        kind="runtime_probe_sequence",
        source_system="release-evidence",
        platform_observed_at=platform_observed_at,
        runtime_probe_requested_at=runtime_probe_requested_at,
        runtime_response_observed_at=runtime_response_observed_at,
    )

    assert (
        evidence.platform_observed_at
        < evidence.runtime_probe_requested_at
        < evidence.runtime_response_observed_at
    )


def test_detection_engine_accepts_a_configured_grace_period() -> None:
    engine = DetectionEngine(grace_period=timedelta(minutes=15))
    release = release_with_new_revision(
        deployed=ReleaseState(
            revision_name="revision-2",
            container_app=ContainerAppState(
                provisioning_state="Provisioning",
                ready_replicas=0,
            ),
            latest_revision_name="revision-2",
            latest_ready_revision_name="revision-1",
        ),
        observed_at=datetime(2026, 9, 22, 9, 10, tzinfo=timezone.utc),
    )

    statuses = {
        detection.code: detection.status
        for detection in engine.evaluate(release)
    }

    assert statuses["latest_revision_not_ready"] == "PASS"
