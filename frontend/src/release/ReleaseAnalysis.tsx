// LEGACY / HISTORICAL / NOT CURRENT ARCHITECTURE: disconnected release-intelligence experiment.
import { InterfaceIcon } from "../components/InterfaceIcon";
import { useState } from "react";

import type { AnalysisReport } from "../domain/releaseTypes";

type ReleaseAnalysisProps = {
  onAskAI?: () => void;
  report: AnalysisReport;
};

export function ReleaseAnalysis({ onAskAI, report }: ReleaseAnalysisProps): React.JSX.Element {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <section className="release-analysis" aria-labelledby="analysis-title">
      <div className="release-section-heading">
        <div>
          <p className="release-eyebrow">Automatic report</p>
          <h2 id="analysis-title">AI Analysis</h2>
        </div>
        <span className="release-analysis__confidence">{report.confidence}</span>
      </div>

      <div className="release-analysis__summary">
        <p>{report.summary}</p>
      </div>

      <div className="release-analysis__compact-meta">
        <div><span>Impact</span><strong>{report.impact}</strong></div>
        <div><span>Possible area</span><strong>{report.probableCategory}</strong></div>
      </div>

      <div className="release-analysis__actions">
        <button
          aria-controls="full-release-analysis"
          aria-expanded={isExpanded}
          className="text-button"
          onClick={() => setIsExpanded((current) => !current)}
          type="button"
        >
          {isExpanded ? "Hide full analysis" : "View full analysis"} <span aria-hidden="true"><InterfaceIcon name={isExpanded ? "up" : "down"} /></span>
        </button>
        {onAskAI && <button className="release-button" onClick={onAskAI} type="button">Investigate with AI <span aria-hidden="true"><InterfaceIcon name="up-right" /></span></button>}
      </div>

      {isExpanded && (
        <div className="release-analysis__details" id="full-release-analysis">
          <div className="release-analysis__grid">
            <article className="analysis-block analysis-block--confirmed">
              <p className="analysis-block__label">Confirmed facts</p>
              <h3>Evidence observed</h3>
              <ul>
                {report.confirmedEvidence.map((item) => <li key={item}>{item}</li>)}
              </ul>
            </article>

            <article className="analysis-block analysis-block--probable">
              <p className="analysis-block__label">Probable interpretation</p>
              <h3>{report.detectedCondition}</h3>
              <p><strong>Category:</strong> {report.probableCategory}</p>
              <p><strong>Impact:</strong> {report.impact}</p>
            </article>

            <article className="analysis-block analysis-block--hypotheses">
              <p className="analysis-block__label">Hypotheses / possible causes</p>
              <h3>What may explain it</h3>
              <ul>
                {report.possibleCauses.map((item) => <li key={item}>{item}</li>)}
              </ul>
            </article>
          </div>

          <div className="release-analysis__footer">
            <div>
              <p className="analysis-block__label">Recommended next steps</p>
              <ol>
                {report.recommendedActions.map((item) => <li key={item}>{item}</li>)}
              </ol>
            </div>
            <div className="release-analysis__limitations">
              <p className="analysis-block__label">Uncertainty / limitations</p>
              <p>{report.limitations}</p>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
