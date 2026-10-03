import { describe, expect, it } from "vitest";

import { getRelease, incidents, project } from "../src/domain/mockReleaseData";

describe("release intelligence mock data", () => {
  it("represents a failed deployment separately from a successful pipeline", () => {
    const release = getRelease("release-20260922-10");

    expect(release.stages.find((stage) => stage.key === "ci")?.status).toBe("succeeded");
    expect(release.stages.find((stage) => stage.key === "deployment")?.status).toBe("failed");
    expect(release.readiness).toBe("ActivationFailed");
    expect(release.replicaCount).toBe(0);
    expect(release.expectedVersion).not.toBe(release.servingVersion);
    expect(release.analysis?.confirmedEvidence).toContain("Previous release is still serving traffic");
  });

  it("starts on the healthy DEV release", () => {
    const release = getRelease(project.currentReleaseId);

    expect(project.environment.name).toBe("DEV");
    expect(release.build).toBe("Build 20260922.12");
    expect(release.status).toBe("healthy");
    expect(release.expectedVersion).toBe(release.servingVersion);
  });

  it("keeps detections linked directly to their affected release", () => {
    const incident = incidents.find((item) => item.id === "INC-002");

    expect(incident).toBeDefined();
    if (!incident) return;

    expect(incident.id).toBe("INC-002");
    expect(incident.affectedEnvironment).toBe("DEV");
    expect(incident.detectedAt).toContain("UTC");
    expect(incident.impact).toContain("DEV");
    expect(incident.releaseId).toBe("release-20260922-10");
    expect(incident.analysis.confirmedEvidence).toContain("Replica count: 0");
  });
});
