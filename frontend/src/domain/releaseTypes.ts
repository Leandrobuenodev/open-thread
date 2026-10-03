// LEGACY / HISTORICAL / NOT CURRENT ARCHITECTURE: disconnected release-intelligence experiment.
export type ReleaseStatus = "healthy" | "mismatch" | "failed";

export type Environment = {
  name: "DEV" | "STAGE" | "PROD";
  platform: "Azure Container Apps";
};

export type ReleaseStageStatus = "pending" | "succeeded" | "warning" | "failed";

export type ReleaseStageKey =
  | "source"
  | "ci"
  | "artifact"
  | "deployment"
  | "runtime"
  | "traffic";

export type ReleaseStage = {
  key: ReleaseStageKey;
  label: string;
  status: ReleaseStageStatus;
  summary: string;
  detail: string;
};

export type AnalysisReport = {
  summary: string;
  detectedCondition: string;
  impact: string;
  confirmedEvidence: string[];
  probableCategory: string;
  confidence: string;
  possibleCauses: string[];
  recommendedActions: string[];
  limitations: string;
};

export type Evidence = {
  label: string;
  value: string;
};

export type Incident = {
  id: string;
  releaseId: string;
  title: string;
  category: string;
  severity: "warning" | "high";
  status: "open";
  affectedEnvironment: Environment["name"];
  detectedAt: string;
  impact: string;
  evidence: Evidence[];
  analysis: AnalysisReport;
};

export type Release = {
  id: string;
  build: string;
  status: ReleaseStatus;
  statusLabel: string;
  pullRequest: string;
  commitSha: string;
  pipeline: string;
  artifact: string;
  image: string;
  revision: string;
  readiness: string;
  replicaCount: number;
  expectedVersion: string;
  servingVersion: string;
  createdAt: string;
  stages: ReleaseStage[];
  analysis?: AnalysisReport;
};

export type Project = {
  name: string;
  environment: Environment;
  currentReleaseId: string;
  integrationTarget: string;
};
