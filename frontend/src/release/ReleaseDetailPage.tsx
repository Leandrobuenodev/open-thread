// LEGACY / HISTORICAL / NOT CURRENT ARCHITECTURE: disconnected release-intelligence experiment.
import { InterfaceIcon } from "../components/InterfaceIcon";
import type { Incident, Release, ReleaseStage } from "../domain/releaseTypes";
import { ReleaseAnalysis } from "./ReleaseAnalysis";

type ReleaseDetailPageProps = {
  detections: Incident[];
  focusedDetectionId?: string;
  onBack: () => void;
  onOpenInvestigator: () => void;
  release: Release;
};

const stageStatusLabel: Record<ReleaseStage["status"], string> = {
  pending: "Pending",
  succeeded: "Complete",
  warning: "Attention",
  failed: "Failed",
};

const verdictLabel: Record<Release["status"], string> = {
  healthy: "HEALTHY",
  mismatch: "NOT SERVING",
  failed: "FAILED",
};

const verdictMessage: Record<Release["status"], string> = {
  healthy: "This release is currently serving in DEV.",
  mismatch: "CI passed, but DEV is still serving the previous release.",
  failed: "The new revision never became ready.",
};

export function ReleaseDetailPage({
  detections,
  focusedDetectionId,
  onBack,
  onOpenInvestigator,
  release,
}: ReleaseDetailPageProps): React.JSX.Element {
  const relatedDetections = detections.filter((detection) => detection.releaseId === release.id);
  const ciSummary = release.pipeline.includes("succeeded") ? "CI passed" : release.pipeline;
  const deployedSummary = release.status === "failed" ? "Not ready" : release.readiness;
  const servingSummary = release.expectedVersion === release.servingVersion ? "Current release" : "Previous release";

  return (
    <div className="release-detail-page">
      <button className="back-link" onClick={onBack} type="button"><InterfaceIcon name="left" /> All releases</button>

      <header className="release-detail-header">
        <div>
          <p className="release-eyebrow">Release detail · DEV</p>
          <h1>{release.build}</h1>
          <p className="release-detail-header__meta">{release.pullRequest} · {release.createdAt}</p>
        </div>
      </header>

      <section className={`release-verdict release-verdict--${release.status}`} aria-labelledby="release-verdict-title">
        <div>
          <p className="release-eyebrow">Runtime verdict</p>
          <strong id="release-verdict-title">{verdictLabel[release.status]}</strong>
          <h2>{verdictMessage[release.status]}</h2>
        </div>
        <div className="release-verdict__status">
          <span className="release-status__dot" aria-hidden="true" />
          <span>{release.statusLabel}</span>
          <small>{release.replicaCount} {release.replicaCount === 1 ? "ready replica" : "ready replicas"}</small>
        </div>
      </section>

      <section className="release-state-comparison" aria-labelledby="release-state-title">
        <div className="release-section-heading">
          <div>
            <p className="release-eyebrow">Release state</p>
            <h2 id="release-state-title">Expected · Deployed · Serving</h2>
          </div>
          <span className="release-section-heading__note">The answer this release page is built to show.</span>
        </div>
        <div className="release-state-comparison__grid">
          <article className="release-state release-state--expected">
            <span>Expected</span>
            <strong>{release.expectedVersion}</strong>
            <small>{ciSummary}</small>
          </article>
          <article className="release-state release-state--deployed">
            <span>Deployed</span>
            <strong>{release.revision}</strong>
            <small>{deployedSummary}</small>
          </article>
          <article className={`release-state release-state--serving${release.expectedVersion === release.servingVersion ? " release-state--match" : " release-state--mismatch"}`}>
            <span>Serving</span>
            <strong>{release.servingVersion}</strong>
            <small>{servingSummary}</small>
          </article>
        </div>
      </section>

      <section className="release-lifecycle release-lifecycle--secondary" aria-labelledby="lifecycle-title">
        <div className="release-section-heading">
          <div>
            <p className="release-eyebrow">Supporting evidence</p>
            <h2 id="lifecycle-title">Source <InterfaceIcon name="right" /> CI <InterfaceIcon name="right" /> Artifact <InterfaceIcon name="right" /> Deployment <InterfaceIcon name="right" /> Runtime <InterfaceIcon name="right" /> Traffic</h2>
          </div>
          <span className="release-section-heading__note">Evidence behind the verdict.</span>
        </div>
        <div className="release-lifecycle__grid">
          {release.stages.map((stageItem, index) => (
            <article className={`lifecycle-stage lifecycle-stage--${stageItem.status}`} key={stageItem.key}>
              <div className="lifecycle-stage__topline">
                <span className="lifecycle-stage__index">{String(index + 1).padStart(2, "0")}</span>
                <span>{stageStatusLabel[stageItem.status]}</span>
              </div>
              <h3>{stageItem.label}</h3>
              <p>{stageItem.summary}</p>
              <small>{stageItem.detail}</small>
            </article>
          ))}
        </div>
      </section>

      {relatedDetections.length > 0 && (
        <section className="release-detections" aria-labelledby="release-detections-title">
          <div className="release-section-heading">
            <div>
              <p className="release-eyebrow">Deterministic findings</p>
              <h2 id="release-detections-title">Detected issues</h2>
            </div>
            <span className="release-section-heading__note">{relatedDetections.length} associated detection{relatedDetections.length === 1 ? "" : "s"}</span>
          </div>
          <div className="release-detections__list">
            {relatedDetections.map((detection) => (
              <article className={`release-detection${focusedDetectionId === detection.id ? " release-detection--focused" : ""}`} id={`detection-${detection.id}`} key={detection.id}>
                <div className="release-detection__copy">
                  <div className="release-detection__topline"><span className={`release-detection__severity release-detection__severity--${detection.severity}`}>{detection.severity === "high" ? "High" : "Warning"}</span><span>{detection.detectedAt}</span></div>
                  <h3>{detection.title}</h3>
                  <p>{detection.impact}</p>
                </div>
                <span className="release-detection__category">{detection.category}</span>
              </article>
            ))}
          </div>
        </section>
      )}

      <details className="release-metadata-details">
        <summary>Release metadata <span>{release.commitSha} · {release.revision}</span></summary>
        <div className="release-metadata" aria-label="Release metadata">
          <div><span>Commit</span><strong>{release.commitSha}</strong></div>
          <div><span>Pipeline</span><strong>{release.pipeline.replace(" · succeeded", "")}</strong></div>
          <div><span>Artifact</span><strong>{release.artifact}</strong></div>
          <div><span>Image digest</span><strong>{release.image}</strong></div>
          <div><span>Revision</span><strong>{release.revision}</strong></div>
        </div>
      </details>

      {release.analysis ? (
        <ReleaseAnalysis onAskAI={onOpenInvestigator} report={release.analysis} />
      ) : (
        <section className="release-ai-cta" aria-labelledby="healthy-analysis-title">
          <div>
            <p className="release-eyebrow">Optional investigation</p>
            <h2 id="healthy-analysis-title">No anomaly detected</h2>
            <p>The expected revision is ready and serving traffic. Investigate with AI if you need more context.</p>
          </div>
          <button className="release-button" onClick={onOpenInvestigator} type="button">Investigate with AI <span aria-hidden="true"><InterfaceIcon name="up-right" /></span></button>
        </section>
      )}
    </div>
  );
}
