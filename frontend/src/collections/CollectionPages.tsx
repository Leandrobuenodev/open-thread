// LEGACY / HISTORICAL / NOT CURRENT ARCHITECTURE: disconnected release-intelligence experiment.
import { InterfaceIcon } from "../components/InterfaceIcon";
import type { Incident, Release } from "../domain/releaseTypes";

type CollectionPageProps = {
  onOpenRelease: (releaseId: string) => void;
  releases: Release[];
};

function StatusPill({ release }: { release: Release }): React.JSX.Element {
  return <span className={`collection-status collection-status--${release.status}`}><span aria-hidden="true" />{release.statusLabel}</span>;
}

export function ReleasesPage({ onOpenRelease, releases }: CollectionPageProps): React.JSX.Element {
  return (
    <div className="collection-page">
      <header className="collection-page__heading">
        <div>
          <p className="release-eyebrow">Release history / DEV</p>
          <h1>Releases</h1>
          <p>Every release keeps its full path from merged source to the version serving traffic.</p>
        </div>
        <span className="collection-page__count">{releases.length} mock releases</span>
      </header>
      <section className="collection-list" aria-label="Release history">
        <div className="collection-list__header"><span>Release</span><span>Expected <InterfaceIcon name="right" /> serving</span><span>Status</span><span /></div>
        {releases.map((release) => (
          <button className="collection-row" key={release.id} onClick={() => onOpenRelease(release.id)} type="button">
            <span className="collection-row__name"><strong>{release.build}</strong><small>{release.pullRequest} · {release.createdAt}</small></span>
            <span className="collection-row__version"><strong>{release.expectedVersion}</strong><small><InterfaceIcon name="right" /> {release.servingVersion}</small></span>
            <StatusPill release={release} />
            <span aria-hidden="true"><InterfaceIcon name="up-right" /></span>
          </button>
        ))}
      </section>
    </div>
  );
}

type IncidentsPageProps = {
  incidents: Incident[];
  onOpenDetection: (releaseId: string, detectionId: string) => void;
  releases: Release[];
};

export function IncidentsPage({ incidents, onOpenDetection, releases }: IncidentsPageProps): React.JSX.Element {
  const releaseById = new Map(releases.map((release) => [release.id, release]));

  return (
    <div className="collection-page">
      <header className="collection-page__heading">
        <div>
          <p className="release-eyebrow">Detections / DEV</p>
          <h1>Incidents</h1>
          <p>Detected problems linked directly to the release where they occurred.</p>
        </div>
        <span className="collection-page__count">{incidents.length} active detections</span>
      </header>
      <section className="incident-list" aria-label="Release incidents">
        <div className="incident-list__header"><span /><span>Detection</span><span>Affected release</span><span>Severity</span><span>Detected</span><span /></div>
        {incidents.map((incident) => {
          const release = releaseById.get(incident.releaseId);
          if (!release) return null;
          return (
          <button className="incident-row" key={incident.id} onClick={() => onOpenDetection(incident.releaseId, incident.id)} type="button">
            <span className={`incident-row__marker incident-row__marker--${release.status}`} aria-hidden="true" />
            <span className="incident-row__body"><strong>{incident.title}</strong><span>{incident.category}</span><small>{incident.impact}</small></span>
            <span className="incident-row__release"><strong>{release.build}</strong><small>{incident.affectedEnvironment}</small></span>
            <span className="incident-row__severity"><strong>{incident.severity === "high" ? "High" : "Warning"}</strong><small>{incident.status}</small></span>
            <span className="incident-row__detected">{incident.detectedAt}</span>
            <span aria-hidden="true"><InterfaceIcon name="up-right" /></span>
          </button>
          );
        })}
      </section>
    </div>
  );
}

export function IntegrationsPage(): React.JSX.Element {
  return (
    <div className="collection-page">
      <header className="collection-page__heading">
        <div>
          <p className="release-eyebrow">Settings / evidence sources</p>
          <h1>Integrations</h1>
          <p>Where should Open Thread collect release evidence from? These mocked settings define the future evidence boundary.</p>
        </div>
      </header>
      <section className="integration-grid" aria-label="Evidence integrations">
        <article className="integration-card">
          <div className="integration-card__heading"><span className="integration-card__index">01</span><span className="integration-card__status integration-card__status--mock">Mock connected</span></div>
          <h2>Azure DevOps</h2>
          <p>Pull requests, commits, pipeline runs, and artifacts.</p>
          <dl><div><dt>Organization</dt><dd>contoso-engineering</dd></div><div><dt>Project</dt><dd>Open Thread</dd></div><div><dt>Repository / pipeline</dt><dd>openthread / openthread-ci</dd></div></dl>
        </article>
        <article className="integration-card">
          <div className="integration-card__heading"><span className="integration-card__index">02</span><span className="integration-card__status integration-card__status--mock">Mock connected</span></div>
          <h2>Azure</h2>
          <p>Revisions, readiness, replica counts, and traffic allocation.</p>
          <dl><div><dt>Subscription</dt><dd>Engineering Sandbox</dd></div><div><dt>Resource group</dt><dd>rg-evidenceops-dev</dd></div><div><dt>Container App</dt><dd>evidenceops-dev-api-&lt;unique&gt;</dd></div></dl>
        </article>
        <article className="integration-card">
          <div className="integration-card__heading"><span className="integration-card__index">03</span><span className="integration-card__status">Not configured</span></div>
          <h2>Application Version Endpoint</h2>
          <p>Future application evidence for serving commit, build, image digest, and migration version.</p>
          <dl><div><dt>Endpoint</dt><dd><code>/health/version</code></dd></div><div><dt>Purpose</dt><dd>Expected vs. serving version check</dd></div></dl>
        </article>
      </section>
    </div>
  );
}
