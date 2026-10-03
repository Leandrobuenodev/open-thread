// LEGACY / HISTORICAL / NOT CURRENT ARCHITECTURE: disconnected release-intelligence experiment.
import type { Incident, Project, Release, ReleaseStage } from "./releaseTypes";

const stage = (
  key: ReleaseStage["key"],
  label: string,
  status: ReleaseStage["status"],
  summary: string,
  detail: string,
): ReleaseStage => ({ key, label, status, summary, detail });

export const project: Project = {
  name: "Open Thread",
  environment: { name: "DEV", platform: "Azure Container Apps" },
  currentReleaseId: "release-20260922-12",
  integrationTarget: "Azure DevOps + Azure Container Apps",
};

export const releases: Release[] = [
  {
    id: "release-20260922-12",
    build: "Build 20260922.12",
    status: "healthy",
    statusLabel: "Healthy",
    pullRequest: "PR #184 · Release intelligence shell",
    commitSha: "8f31d2a",
    pipeline: "evidenceops-ci · succeeded",
    artifact: "evidenceops-backend:20260922.12",
    image: "sha256:91b8…c2f4",
    revision: "evidenceops-dev-api--000012",
    readiness: "Ready",
    replicaCount: 2,
    expectedVersion: "Build 20260922.12",
    servingVersion: "Build 20260922.12",
    createdAt: "22 Sep 2026 · 09:42 UTC",
    stages: [
      stage("source", "Source", "succeeded", "PR merged", "commit 8f31d2a"),
      stage("ci", "CI", "succeeded", "Pipeline succeeded", "evidenceops-ci"),
      stage("artifact", "Artifact", "succeeded", "Image built", "20260922.12"),
      stage("deployment", "Deployment", "succeeded", "Revision created", "000012"),
      stage("runtime", "Runtime", "succeeded", "2 healthy replicas", "Ready"),
      stage("traffic", "Traffic", "succeeded", "Expected version serving", "100% to 000012"),
    ],
  },
  {
    id: "release-20260922-11",
    build: "Build 20260922.11",
    status: "mismatch",
    statusLabel: "Deployment mismatch",
    pullRequest: "PR #181 · Add version endpoint",
    commitSha: "6c4ef10",
    pipeline: "evidenceops-ci · succeeded",
    artifact: "evidenceops-backend:20260922.11",
    image: "sha256:4e9a…71d1",
    revision: "evidenceops-dev-api--000011",
    readiness: "Ready, but not serving",
    replicaCount: 1,
    expectedVersion: "Build 20260922.11",
    servingVersion: "Build 20260922.10",
    createdAt: "22 Sep 2026 · 08:17 UTC",
    stages: [
      stage("source", "Source", "succeeded", "PR merged", "commit 6c4ef10"),
      stage("ci", "CI", "succeeded", "Pipeline succeeded", "evidenceops-ci"),
      stage("artifact", "Artifact", "succeeded", "Image built", "20260922.11"),
      stage("deployment", "Deployment", "succeeded", "Revision created", "000011"),
      stage("runtime", "Runtime", "warning", "Replica is ready", "Readiness passed"),
      stage("traffic", "Traffic", "warning", "Previous version serving", "000010 receives traffic"),
    ],
    analysis: {
      summary:
        "The release passed CI and became ready, but the expected revision is not serving traffic in DEV. The environment is still serving an older release.",
      detectedCondition: "Release version mismatch after deployment.",
      impact: "The merged changes are not currently serving requests in DEV.",
      confirmedEvidence: [
        "Pipeline succeeded",
        "Expected revision was created and became ready",
        "Expected version: Build 20260922.11",
        "Serving version: Build 20260922.10",
        "Traffic remains on the previous revision",
      ],
      probableCategory: "Traffic routing or activation mismatch",
      confidence: "High for the version mismatch",
      possibleCauses: [
        "Traffic was not shifted after the revision became ready",
        "A deployment policy retained the previous revision",
        "The serving endpoint has stale version metadata",
      ],
      recommendedActions: [
        "Inspect revision traffic weights and active labels",
        "Verify the serving version at the application endpoint",
        "Compare the revision image digest with the expected artifact",
      ],
      limitations: "The mock data does not include live traffic configuration or endpoint telemetry.",
    },
  },
  {
    id: "release-20260922-10",
    build: "Build 20260922.10",
    status: "failed",
    statusLabel: "Activation failed",
    pullRequest: "PR #179 · Startup configuration update",
    commitSha: "3b7aa29",
    pipeline: "evidenceops-ci · succeeded",
    artifact: "evidenceops-backend:20260922.10",
    image: "sha256:0a32…e8af",
    revision: "evidenceops-dev-api--000010",
    readiness: "ActivationFailed",
    replicaCount: 0,
    expectedVersion: "Build 20260922.10",
    servingVersion: "Build 20260922.09",
    createdAt: "21 Sep 2026 · 16:06 UTC",
    stages: [
      stage("source", "Source", "succeeded", "PR merged", "commit 3b7aa29"),
      stage("ci", "CI", "succeeded", "Pipeline succeeded", "evidenceops-ci"),
      stage("artifact", "Artifact", "succeeded", "Image built", "20260922.10"),
      stage("deployment", "Deployment", "failed", "Revision created", "ActivationFailed"),
      stage("runtime", "Runtime", "failed", "0 replicas", "Revision never became ready"),
      stage("traffic", "Traffic", "warning", "Previous version serving", "000009 receives traffic"),
    ],
    analysis: {
      summary:
        "The pipeline completed successfully, but the new application revision never became ready. The environment appears to still be serving the previous healthy release.",
      detectedCondition: "Deployment failed after CI.",
      impact: "The merged changes are not currently running in DEV.",
      confirmedEvidence: [
        "Pipeline succeeded",
        "Expected revision was created",
        "Revision state: ActivationFailed",
        "Replica count: 0",
        "Latest ready revision is older than the expected revision",
        "Previous release is still serving traffic",
      ],
      probableCategory: "Application startup failure",
      confidence: "High for the deployment mismatch",
      possibleCauses: [
        "Application startup exception",
        "Migration failure",
        "Missing runtime configuration",
        "Dependency or connectivity failure",
      ],
      recommendedActions: [
        "Inspect startup and container logs for the failed revision",
        "Check application startup and migrations",
        "Verify the expected image and revision",
        "Compare the serving version with the expected release",
      ],
      limitations:
        "The available evidence confirms the deployment mismatch, but does not establish an exact root cause. Live logs are required.",
    },
  },
];

export function getRelease(releaseId: string | undefined): Release {
  return releases.find((release) => release.id === releaseId) ?? releases[0];
}

export const incidents: Incident[] = [
  {
    id: "INC-001",
    releaseId: "release-20260922-11",
    title: "Previous release still serving",
    category: "Traffic routing or activation mismatch",
    severity: "warning",
    status: "open",
    affectedEnvironment: "DEV",
    detectedAt: "22 Sep 2026 · 08:24 UTC",
    impact: "The merged changes are not currently serving requests in DEV.",
    evidence: [
      { label: "Expected", value: "Build 20260922.11" },
      { label: "Serving", value: "Build 20260922.10" },
    ],
    analysis: releases[1].analysis!,
  },
  {
    id: "INC-002",
    releaseId: "release-20260922-10",
    title: "Revision activation failed",
    category: "Application startup failure",
    severity: "high",
    status: "open",
    affectedEnvironment: "DEV",
    detectedAt: "21 Sep 2026 · 16:11 UTC",
    impact: "The merged changes are not currently running in DEV; the previous healthy release remains in service.",
    evidence: [
      { label: "Revision", value: "ActivationFailed" },
      { label: "Replicas", value: "0" },
    ],
    analysis: releases[2].analysis!,
  },
];
