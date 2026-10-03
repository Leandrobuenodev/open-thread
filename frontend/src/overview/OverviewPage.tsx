// LEGACY / HISTORICAL / NOT CURRENT ARCHITECTURE: disconnected release-intelligence experiment.
import { InterfaceIcon } from "../components/InterfaceIcon";
import type { Incident, Project, Release } from "../domain/releaseTypes";

type OverviewPageProps = {
  incidents: Incident[];
  onOpenRelease: (releaseId: string, detectionId?: string) => void;
  project: Project;
  releases: Release[];
};

function environmentVerdict(status: Release["status"]): string {
  return status === "healthy" ? "HEALTHY" : status === "mismatch" ? "WARNING" : "FAILED";
}

export function OverviewPage({ incidents, onOpenRelease, project, releases }: OverviewPageProps): React.JSX.Element {
  const currentRelease = releases.find((release) => release.id === project.currentReleaseId) ?? releases[0];
  const recentDetections = incidents.slice(0, 2);
  const recentReleases = releases.slice(0, 3);
  const currentComparison = currentRelease.expectedVersion === currentRelease.servingVersion ? "=" : "≠";

  return (
    <div className="overview-page">
      <header className="overview-page__heading">
        <div>
          <p className="release-eyebrow">Release intelligence / {project.environment.name}</p>
          <h1>Is {project.environment.name} healthy right now?</h1>
          <p>A focused answer about the release currently serving traffic.</p>
        </div>
      </header>

      <section className={`overview-current overview-current--${currentRelease.status}`} aria-labelledby="current-release-title">
        <div className="overview-current__intro">
          <div className="overview-current__verdict">
            <p className="release-eyebrow">{project.environment.name}</p>
            <strong className={`overview-current__verdict--${currentRelease.status}`}>{environmentVerdict(currentRelease.status)}</strong>
            <p>{currentRelease.expectedVersion} {currentComparison} {currentRelease.servingVersion}</p>
          </div>
          <div className="overview-current__release">
            <span>Current release</span>
            <h2 id="current-release-title">{currentRelease.build}</h2>
            <button className="text-button" onClick={() => onOpenRelease(currentRelease.id)} type="button">Open release detail <InterfaceIcon name="right" /></button>
          </div>
        </div>
      </section>

      <section className="overview-signals" aria-labelledby="signals-title">
        <div className="section-heading-row">
          <div>
            <p className="release-eyebrow">Active detections</p>
            <h2 id="signals-title">Needs attention</h2>
          </div>
          <span>{incidents.length} detected problems</span>
        </div>
        <div className="overview-signal-grid">
          {recentDetections.map((incident) => {
            const affectedRelease = releases.find((release) => release.id === incident.releaseId);
            return (
              <button className="overview-signal" key={incident.id} onClick={() => onOpenRelease(incident.releaseId, incident.id)} type="button">
                <span className={`overview-signal__marker overview-signal__marker--${incident.severity}`} aria-hidden="true" />
                <span className="overview-signal__body"><strong>{incident.title}</strong><span>{affectedRelease?.build} · {incident.impact}</span></span>
                <span className="overview-signal__meta">{incident.detectedAt}</span>
                <span aria-hidden="true"><InterfaceIcon name="up-right" /></span>
              </button>
            );
          })}
        </div>
      </section>

      <section className="recent-releases" aria-labelledby="recent-releases-title">
        <div className="section-heading-row">
          <div>
            <p className="release-eyebrow">Release history</p>
            <h2 id="recent-releases-title">Recent releases</h2>
          </div>
          <span>Latest three releases</span>
        </div>
        <div className="recent-release-list">
          {recentReleases.map((release) => (
            <button className="recent-release" key={release.id} onClick={() => onOpenRelease(release.id)} type="button">
              <span className={`recent-release__status recent-release__status--${release.status}`} aria-hidden="true" />
              <span className="recent-release__main"><strong>{release.build}</strong><span>{release.statusLabel}</span></span>
              <span className="recent-release__signal">{release.expectedVersion === release.servingVersion ? "Expected = serving" : `${release.servingVersion} serving`}</span>
              <span className="recent-release__arrow" aria-hidden="true"><InterfaceIcon name="up-right" /></span>
            </button>
          ))}
        </div>
      </section>
    </div>
  );
}
