import { InterfaceIcon } from "../components/InterfaceIcon";
import { useEffect, useRef, useState } from "react";
import "@fontsource-variable/instrument-sans";
import { HomeHeader } from "./HomeHeader";
import "./home.css";

type HomePageProps = {
  authError: string | null;
  authStatus?: string | null;
  onCancelSignIn?: () => void;
  isBusy: boolean;
  onSignIn: () => Promise<void>;
};

const systemSteps = [
  {
    name: "The interface",
    technology: "React + TypeScript",
    route: "01 / BROWSER STATE",
    title: "A message begins in the client.",
    description:
      "The interface captures the prompt and sends it through an authenticated flow. Saved conversations are retrieved from the backend, with Azure Table Storage preserving history and private Blob Storage holding image attachments.",
  },
  {
    name: "The identity",
    technology: "MSAL + Microsoft Entra ID",
    route: "02 / AUTHENTICATION",
    title: "An authenticated request.",
    description:
      "MSAL handles sign-in and token acquisition. Before processing a message, the API validates the bearer token's signature, issuer, audience, expiration, and required scope.",
  },
  {
    name: "The application",
    technology: "FastAPI + Python",
    route: "03 / POST /API/CHAT",
    title: "A clear application boundary.",
    description:
      "The protected chat endpoint passes the request to ChatService. HTTP handling stays separate from model integration, keeping the application easier to test, evolve, and extend.",
  },
  {
    name: "The model",
    technology: "Microsoft Foundry",
    route: "04 / MODEL INTEGRATION",
    title: "From prompt to model response.",
    description:
      "ChatService calls a concrete Microsoft Foundry client. This layer contains model request and response handling, keeping integration details separate from HTTP handling and the browser experience.",
  },
];

const architectureSteps = [
  {
    name: "React + TypeScript",
    role: "Browser interface",
    context: "Azure Static Web Apps",
  },
  { name: "MSAL", role: "Sign-in and token acquisition" },
  {
    name: "Microsoft Entra ID",
    role: "Authenticates the user and request",
  },
  {
    name: "FastAPI",
    role: "Protected application API",
    context: "Azure Container Apps",
  },
  { name: "ChatService", role: "Application orchestration" },
  { name: "FoundryClient", role: "Concrete model integration" },
  { name: "Microsoft Foundry", role: "Provides model inference" },
];

const deliverySteps = [
  "Feature branch",
  "Pull Request",
  "CI",
  "Tests & validation",
  "Docker build",
  "Azure Container Registry",
  "Azure Container Apps",
  "DEV",
];

export function HomePage({
  authError,
  authStatus,
  onCancelSignIn,
  isBusy,
  onSignIn,
}: HomePageProps): React.JSX.Element {
  const [activeStep, setActiveStep] = useState(0);
  const [isExperienceVisible, setIsExperienceVisible] = useState(false);
  const experienceRef = useRef<HTMLElement | null>(null);
  const step = systemSteps[activeStep];

  useEffect(() => {
    const section = experienceRef.current;
    if (!section) return;

    if (
      window.matchMedia("(prefers-reduced-motion: reduce)").matches ||
      !("IntersectionObserver" in window)
    ) {
      setIsExperienceVisible(true);
      return;
    }

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsExperienceVisible(true);
          observer.disconnect();
        }
      },
      { rootMargin: "0px 0px -8% 0px", threshold: 0.08 },
    );
    observer.observe(section);

    return () => observer.disconnect();
  }, []);

  return (
    <main className="home-page" id="home">
      {authStatus && (
        <div className="home-auth-overlay">
          <div className="home-auth-status" role="status" aria-live="polite">
            <span className="home-auth-spinner" aria-hidden="true" />
            <span>{authStatus}</span>
            {onCancelSignIn && (
              <button type="button" className="home-auth-cancel" onClick={onCancelSignIn}>
                Cancel sign-in
              </button>
            )}
          </div>
        </div>
      )}
      {authError && !authStatus && (
        <p className="home-auth-notice" role="alert">{authError}</p>
      )}
      <a className="home-skip" href="#start">
        Skip to sign in
      </a>
      <div className="home-light">
        <HomeHeader isBusy={isBusy} onSignIn={onSignIn} />
        <section
          className="home-hero home-container"
          aria-labelledby="home-title"
        >
          <div className="home-hero__guide" aria-hidden="true" />
          <div className="home-hero__copy">
            <p className="home-eyebrow">AI-ENABLED CLOUD APPLICATION</p>
            <h1 id="home-title">
              <span className="home-hero__line">THINK</span>
              <span className="home-hero__line">OUT LOUD</span>
            </h1>
            <p className="home-hero__description">
              A conversational AI experience built with LLMs and cloud
              engineering on Microsoft Azure.
            </p>
          </div>
          <p className="home-hero__techline">
            Microsoft Foundry · FastAPI · Microsoft Entra ID · Azure Container Apps · CI/CD
          </p>
          <a
            className="home-scroll"
            href="#experience"
            aria-label="Explore the experience"
            title="Explore the experience"
          >
            <span className="home-scroll__label">Explore the experience</span>
            <span className="home-scroll__arrow" aria-hidden="true">
              <InterfaceIcon name="down" />
            </span>
          </a>
        </section>
      </div>
      <section
        ref={experienceRef}
        className={`home-experience${isExperienceVisible ? " is-visible" : ""}`}
        id="experience"
        aria-labelledby="experience-title"
      >
        <div className="home-section-bar home-container">
          <span>02 — THE EXPERIENCE</span>
          <span aria-hidden="true">[ SCROLL TO EXPLORE ]</span>
        </div>
        <div className="home-experience__grid home-container">
          <div className="home-experience__visual">
          </div>
          <div className="home-experience__copy">
            <p className="home-eyebrow">BEYOND THE CHAT</p>
            <h2 id="experience-title">
              THE ENGINEERING
              <br />
              BEHIND THE
              <br />
              <span>CONVERSATION</span>
            </h2>
            <p>
              Open Thread runs on Microsoft Azure, with a React interface
              authenticated through Microsoft Entra ID and a containerized
              FastAPI backend.
            </p>
            <p>
              Persistent workspace data, Microsoft Foundry integration, Bicep
              infrastructure, and automated DEV delivery connect the
              conversational experience to its cloud runtime.
            </p>
            <p className="home-experience__techline">
              FastAPI · Microsoft Entra ID · Docker · Bicep · Azure Container
              Apps · CI/CD
            </p>
            <a className="home-text-link" href="#system">
              Explore the architecture <InterfaceIcon name="right" />
            </a>
          </div>
        </div>
        <div
          className="home-pillars home-container"
          role="group"
          aria-label="Engineering pillars"
        >
          <article className="home-pillar">
            <h3>AI APPLICATION</h3>
            <p>Python · FastAPI · LLM integration · REST APIs</p>
          </article>
          <article className="home-pillar">
            <h3>IDENTITY &amp; SECURITY</h3>
            <p>Microsoft Entra ID · OAuth/OIDC · Managed Identity · RBAC</p>
          </article>
          <article className="home-pillar">
            <h3>CLOUD &amp; INFRASTRUCTURE</h3>
            <p>
              Microsoft Azure · Container Apps · ACR · Static Web Apps · Bicep
            </p>
          </article>
          <article className="home-pillar">
            <h3>DELIVERY &amp; QUALITY</h3>
            <p>Azure DevOps · Docker · CI/CD · Automated Tests · Pull Requests</p>
          </article>
        </div>
      </section>
      <section
        className="home-system home-container"
        id="system"
        aria-labelledby="system-title"
      >
        <p className="home-eyebrow">03 — BENEATH THE SURFACE</p>
        <div className="home-section-heading">
          <h2 id="system-title">
            SIMPLE TO USE.
            <br />
            CONSIDERED INSIDE.
          </h2>
          <p>
            One message travels through a clear sequence. Explore the layers
            that turn an interaction into a response.
          </p>
        </div>
        <div className="home-flow" aria-label="Explore the request flow">
          {systemSteps.map((item, index) => (
            <button
              key={item.name}
              type="button"
              className={activeStep === index ? "is-active" : ""}
              aria-pressed={activeStep === index}
              aria-controls="system-detail"
              onClick={() => setActiveStep(index)}
            >
              <span className="home-flow__number">
                0{index + 1}
                <InterfaceIcon name={index === 3 ? "down-left" : "right"} />
              </span>
              <strong>{item.name}</strong>
              <span>{item.technology}</span>
            </button>
          ))}
        </div>
        <div
          className="home-system__detail"
          id="system-detail"
          aria-live="polite"
          aria-atomic="true"
        >
          <span className="home-eyebrow">{step.route}</span>
          <div>
            <h3>{step.title}</h3>
            <p>{step.description}</p>
          </div>
          <span className="home-system__counter" aria-hidden="true">
            0{activeStep + 1}
            <small>/ 04</small>
          </span>
        </div>
      </section>
      <section
        className="home-engineering"
        id="engineering"
        aria-labelledby="engineering-title"
      >
        <div className="home-container">
          <p className="home-eyebrow">04 — ENGINEERING CHOICES</p>
          <div className="home-section-heading">
            <h2 id="engineering-title">
              PURPOSE IN
              <br />
              EVERY LAYER.
            </h2>
            <p>
              A compact AI application with deliberate boundaries between
              experience, identity, application logic, model integration,
              infrastructure, and delivery.
            </p>
          </div>
          <div className="home-decisions">
            <article>
              <span>01 / PERSISTENT WORKSPACE</span>
              <h3>Conversation history that persists.</h3>
              <p>
                The client manages display state while the backend persists
                conversations, Projects, and pins in Azure Table Storage.
                Reloading retrieves saved history through the authenticated API.
              </p>
            </article>
            <article>
              <span>02 / APPLICATION BOUNDARIES</span>
              <h3>One concrete model integration.</h3>
              <p>
                ChatService calls a concrete Microsoft Foundry client. Model
                requests and response handling stay separate from the protected
                API and the browser experience.
              </p>
            </article>
            <article>
              <span>03 / IDENTITY &amp; SECURITY</span>
              <h3>Identity as a system boundary.</h3>
              <p>
                Microsoft Entra ID and MSAL handle user identity while the
                FastAPI backend enforces protected access through bearer-token
                validation. Managed Identity and RBAC are used for Azure
                image pulls and Storage access. Foundry inference uses a
                backend-only API key supplied through a secret reference.
              </p>
            </article>
            <article>
              <span>04 / DELIVERY</span>
              <h3>A repeatable delivery path.</h3>
              <p>
                Docker packages the backend, Bicep defines Azure infrastructure,
                and Azure DevOps validates application and infrastructure
                changes before automated delivery to the DEV environment.
              </p>
            </article>
          </div>
          <div className="home-stack">
            <span className="home-eyebrow">BUILT WITH</span>
            <p>
              React / TypeScript / FastAPI / Python / Microsoft Entra ID / Docker
              / Azure Container Apps / Bicep / Azure DevOps / Microsoft Foundry
            </p>
          </div>
        </div>
      </section>
      <section
        className="home-architecture"
        id="architecture"
        aria-labelledby="architecture-title"
      >
        <div className="home-container">
          <p className="home-eyebrow">05 — SYSTEM ARCHITECTURE</p>
          <div className="home-section-heading">
            <h2 id="architecture-title">
              FROM INTERFACE
              <br />
              TO CLOUD RUNTIME.
            </h2>
            <p>
              Open Thread connects a browser experience, identity, protected
              API, model integration, and Azure infrastructure through a
              deliberately small end-to-end architecture.
            </p>
          </div>

          <div className="home-architecture__diagram">
            <div className="home-architecture__label">
              <span>PRIMARY REQUEST FLOW</span>
              <span>AUTHENTICATED REQUEST <InterfaceIcon name="right" /> MODEL INFERENCE</span>
            </div>
            <ol className="home-architecture__flow">
              {architectureSteps.map((item, index) => (
                <li key={item.name}>
                  <span className="home-architecture__index">
                    0{index + 1}
                  </span>
                  <InterfaceIcon name="right" className="home-flow-connector" />
                  <h3>{item.name}</h3>
                  <p>{item.role}</p>
                  {item.context && (
                    <span className="home-architecture__host">
                      {item.context}
                    </span>
                  )}
                </li>
              ))}
            </ol>

            <div className="home-architecture__context">
              <p className="home-architecture__context-title">
                AZURE RUNTIME &amp; INFRASTRUCTURE CONTEXT
              </p>
              <div className="home-architecture__context-grid">
                <article>
                  <span>CONTAINER IMAGE</span>
                  <strong>Azure Container Registry</strong>
                  <p>Stores the backend image deployed to Azure Container Apps.</p>
                </article>
                <article>
                  <span>AZURE RESOURCE ACCESS</span>
                  <strong>Managed Identity + RBAC</strong>
                  <p>Authenticates application access to Azure resources.</p>
                </article>
                <article>
                  <span>INFRASTRUCTURE AS CODE</span>
                  <strong>Bicep</strong>
                  <p>Defines the Azure infrastructure for repeatable deployment.</p>
                </article>
              </div>
            </div>
          </div>

          <div className="home-delivery">
            <div className="home-architecture__label">
              <span>DELIVERY FLOW</span>
              <span>AZURE DEVOPS · AUTOMATED DEV DELIVERY</span>
            </div>
            <ol className="home-delivery__flow">
              {deliverySteps.map((item, index) => (
                <li key={item}>
                  <span>0{index + 1}</span>
                  <InterfaceIcon name="right" className="home-flow-connector" />
                  <strong>{item}</strong>
                </li>
              ))}
            </ol>
            <p className="home-delivery__checks">
              <span>CI CHECKS</span>
              <strong>
                Frontend validation · Backend tests · Bicep validation
              </strong>
            </p>
            <p className="home-delivery__frontend">
              <span>FRONTEND DELIVERY</span>
              <strong>Validated frontend <InterfaceIcon name="right" /> Azure Static Web Apps</strong>
            </p>
          </div>
        </div>
      </section>
      <section className="home-cta" id="closing" aria-labelledby="closing-title">
        <div className="home-container">
          <p className="home-eyebrow">06 — OPEN THREAD</p>
          <div className="home-cta__content">
            <div>
              <h2 id="closing-title">
                WHAT'S ON
                <br />
                YOUR MIND?
              </h2>
              <p>
                Explore the live experience or take a closer look at the
                engineering behind it.
              </p>
            </div>
            <div className="home-cta__actions">
              <button
                className="home-cta__primary"
                type="button"
                onClick={() => void onSignIn()}
                disabled={isBusy}
              >
                {isBusy ? "Signing in…" : "Sign in with Microsoft"}
                <InterfaceIcon name="up-right" />
              </button>
              <a className="home-cta__secondary" href="#architecture">
                Explore the architecture <InterfaceIcon name="right" />
              </a>
            </div>
          </div>
          <footer className="home-footer">
            <a className="home-brand" href="#home" aria-label="Open Thread home">
              <span className="home-brand__symbol" aria-hidden="true"><InterfaceIcon name="brand" /></span> Open Thread
            </a>
            <span>HUMAN CURIOSITY. MACHINE INTELLIGENCE.</span>
            <a href="#home">Back to top <InterfaceIcon name="up" /></a>
          </footer>
        </div>
      </section>
    </main>
  );
}
