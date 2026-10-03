// LEGACY / HISTORICAL / NOT CURRENT ARCHITECTURE: disconnected release-intelligence experiment.
import { useEffect, useState } from "react";

import type { ChatMessage as ChatMessageData } from "../chat/types";
import { ChatComposer } from "../chat/ChatComposer";
import { ChatMessage } from "../chat/ChatMessage";
import type { Incident, Release } from "../domain/releaseTypes";
import "../chat/chat.css";
import "./investigator.css";

export type InvestigatorContextId = "general" | "release-20260922-12" | "release-20260922-11" | "release-20260922-10" | "incidents";

type InvestigatorContext = {
  id: InvestigatorContextId;
  label: string;
  title: string;
  status: string;
  evidence: string[];
};

type InvestigatorPageProps = {
  contextId?: string;
  error: string | null;
  incidents: Incident[];
  isLoading: boolean;
  messages: ChatMessageData[];
  onContextChange: (contextId: InvestigatorContextId) => void;
  onNewConversation: () => void;
  onSendMessage: (message: string) => Promise<void>;
  releases: Release[];
};

function buildContexts(releases: Release[], incidents: Incident[]): InvestigatorContext[] {
  const releaseContexts = releases.map((release) => ({
    id: release.id.replace("release-", "release-") as InvestigatorContextId,
    label: `Release ${release.build.replace("Build ", "")}`,
    title: release.build,
    status: release.statusLabel,
    evidence: [
      `${release.replicaCount} ${release.replicaCount === 1 ? "replica" : "replicas"}`,
      release.expectedVersion === release.servingVersion ? "expected version serving" : `${release.servingVersion} serving`,
    ],
  }));

  return [
    { id: "general", label: "General", title: "General Azure questions", status: "No release selected", evidence: ["No release context selected"] },
    ...releaseContexts,
    {
      id: "incidents",
      label: "Mock incidents",
      title: "Mock incident investigation",
      status: `${incidents.length} open incidents`,
      evidence: incidents.map((incident) => `${incident.id} · ${incident.title}`),
    },
  ];
}

export function InvestigatorPage({
  contextId,
  error,
  incidents,
  isLoading,
  messages,
  onContextChange,
  onNewConversation,
  onSendMessage,
  releases,
}: InvestigatorPageProps): React.JSX.Element {
  const contexts = buildContexts(releases, incidents);
  const requestedContext = contexts.find((context) => context.id === contextId);
  const [selectedContextId, setSelectedContextId] = useState<InvestigatorContextId>(requestedContext?.id ?? "general");
  const [input, setInput] = useState("");
  const context = contexts.find((item) => item.id === selectedContextId) ?? contexts[0];

  useEffect(() => {
    if (requestedContext) setSelectedContextId(requestedContext.id);
  }, [requestedContext?.id]);

  function handleContextChange(nextContextId: InvestigatorContextId) {
    setSelectedContextId(nextContextId);
    setInput("");
    onContextChange(nextContextId);
  }

  function handleSubmit() {
    const message = input.trim();
    if (!message || isLoading) return;
    setInput("");
    void onSendMessage(message);
  }

  return (
    <div className="investigator-page">
      <header className="investigator-heading">
        <div>
          <p className="release-eyebrow">Conversational investigation</p>
          <h1>AI Investigator</h1>
          <p>Ask deeper questions after the release evidence and automatic analysis give you a starting point.</p>
        </div>
        <button className="investigator-new" onClick={onNewConversation} type="button">New investigation</button>
      </header>

      <section className="investigator-contextbar" aria-live="polite">
        <div className="investigator-contextbar__copy">
          <span>Investigating</span>
          <strong>{context.title} · {context.status}</strong>
          <small>{context.evidence.join(" · ")}</small>
        </div>
        <details className="investigator-contextbar__change">
          <summary>Change context</summary>
          <select aria-label="Investigation context" id="investigator-context" onChange={(event) => handleContextChange(event.target.value as InvestigatorContextId)} value={selectedContextId}>
            {contexts.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
          </select>
        </details>
      </section>

      <section className="investigator-conversation" aria-label="AI Investigator conversation" aria-busy={isLoading}>
        {messages.length === 0 ? (
          <div className="investigator-empty">
            <span className="investigator-empty__index">Ready when you are</span>
            <h2>What do you want to understand about this context?</h2>
            <p>{context.id === "general" ? "Ask about Azure, cloud architecture, deployments, or engineering." : "The selected context is available as background for your next question."}</p>
          </div>
        ) : (
          <div className="investigator-messages" aria-live="polite">
            {messages.map((message) => <ChatMessage key={message.id} message={message} />)}
            {isLoading && <p className="investigator-thinking" role="status">Assistant is thinking…</p>}
          </div>
        )}

        {error && <p className="investigator-error" role="alert">{error}</p>}

        <div className="investigator-composer">
          <ChatComposer
            input={input}
            isLoading={isLoading}
            onChange={setInput}
            onSubmit={handleSubmit}
            placeholder={context.id === "general" ? "Ask a general Azure question…" : `Ask about ${context.title}…`}
          />
          <p>Context selection is local mock state; live evidence injection will come with the integrations.</p>
        </div>
      </section>
    </div>
  );
}
