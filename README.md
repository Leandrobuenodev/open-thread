# Open Thread

Open Thread is an AI-enabled web application running on Microsoft Azure.
It combines an authenticated conversational interface with persistent
workspace data, model integration, cloud infrastructure, and automated
delivery.

## What is Open Thread?

Open Thread is a conversational AI application built around a real cloud
architecture: an authenticated frontend, a protected API, persistent
workspace data, model integration, containerized backend services, and
automated DEV delivery on Azure.

The conversational experience connects these layers into a single application,
from user identity and API access to inference, persistence, infrastructure,
and deployment.

## Engineering Scope

Open Thread brings together:

- Authenticated web applications and server-side ownership checks.
- Backend/API engineering and persistent workspace data.
- LLM integration, streaming, multimodal input, and bounded context.
- Cloud infrastructure and secure Azure resource access.
- Containerization and Infrastructure as Code.
- CI/CD, automated testing, and deployment traceability.

## Architecture

```text
Browser
├── React + TypeScript
├── MSAL ↔ Microsoft Entra ID
│         delegated API access token
└── Authenticated request
    ↓
FastAPI: JWT validation and ownership checks
    ↓
ChatService
    ↓
FoundryClient
    ↓
Microsoft Foundry / Azure OpenAI v1 Chat Completions
```

The API uses `ConversationStore` to persist workspace data and construct bounded conversation context before invoking the model. Responses stream back through authenticated POST/SSE; terminal attempt state is saved separately.

```text
ConversationStore
├── Azure Table Storage: conversations, messages, workspace metadata
└── private Azure Blob Storage: image attachments

Azure Container Apps system-assigned Managed Identity
├── AcrPull → Azure Container Registry
├── Storage Table Data Contributor → Azure Storage
└── Storage Blob Data Contributor → Azure Storage
```

`ChatService` delegates to one concrete `FoundryClient`. Foundry inference currently uses a backend API key, separate from both the user's access token and the Container App's Managed Identity.

See [architecture details](docs/architecture.md).

## Application Experience

Implemented capabilities include:

- Microsoft sign-in, sign-out, and access-token renewal.
- Conversational chat with streamed responses and Stop.
- Persistent conversations, Projects, pinned conversations, and a Library.
- Regenerate and edit/resend actions.
- Markdown, highlighted code blocks, and copy actions.
- Image attachments and multimodal request handling.
- Browser speech-to-text where the speech recognition API is supported.
- Responsive layout and loading/error states.

> **Verification status:** Azure infrastructure, CI/CD, runtime identity,
> RBAC, and non-interactive smoke checks are verified. Some authenticated
> DEV flows remain under final manual validation.

See the [detailed verification report](docs/dev-full-e2e-validation.md).

## Tech Stack

### Frontend

React · TypeScript · Vite · MSAL · React Markdown

### Backend

Python 3.11 · FastAPI · Pydantic · httpx

### AI

Microsoft Foundry · Azure OpenAI v1 Chat Completions · GPT-4.1 mini

### Azure

Azure Static Web Apps · Azure Container Apps · Azure Container Registry · Azure Table Storage · Azure Blob Storage · Microsoft Entra ID · Managed Identity · RBAC

### Engineering

Docker · Bicep · Azure DevOps · CI/CD · Pytest · Vitest · Azurite · Playwright smoke checks

## Identity & Security

**User identity:** MSAL and Microsoft Entra ID obtain a delegated API access token. FastAPI validates its signature, issuer, audience, expiration, and required scope, then uses validated tenant/user identity for owner-scoped data access.

**Azure resource identity:** the Container App's system-assigned Managed Identity has `AcrPull`, `Storage Table Data Contributor`, and `Storage Blob Data Contributor`. The Azure DevOps ARM service connection uses a separate federated delivery identity.

Image attachments live in a private Blob container and are retrieved through authenticated API endpoints. The container runs as a non-root user, and CORS permits one configured frontend origin. Foundry's key is backend-only and injected through a Container Apps secret reference; credentials are not shipped to the frontend. Markdown rendering skips raw HTML.

## Persistence

Azure Table Storage holds conversations, messages and attempt status, workspace metadata, Projects, pins, and attachment metadata. Private Azure Blob Storage holds validated, normalized image attachments.

`ConversationStore` derives an owner partition from validated tenant/user identity. ETags, same-partition transactions, and operation leases protect concurrent changes. Conversation deletion supports resumable Table/Blob cleanup; deleting a Project preserves its conversations.

The partition hash is a keying strategy, not encryption or anonymization. See [persistence design](docs/conversation-persistence.md).

## Infrastructure as Code

Bicep defines declarative infrastructure and configuration:

| Template | Responsibility |
| --- | --- |
| `infra/main.bicep` | Registry/identity bootstrap, backend module, existing hosting references |
| `infra/backend.bicep` | Container image, ingress, secrets, identity, probes, resources, and scale |
| `infra/storage.bicep` | Storage Account, Table, private Blob container, and data-access RBAC |
| `infra/foundry.bicep` | Inference account and versioned GPT-4.1 mini deployment |
| `infra/budget.bicep` | Separate cost-notification budget definition |

Environment parameter files supply configuration without publishing actual environment identifiers. Static Web Apps and the Container Apps Environment are referenced as existing resources; Entra registrations and delivery permissions require separate setup. Routine CD applies the backend template and publishes frontend assets, rather than deploying every dependency from one command.

See [infrastructure notes](infra/README.md).

## CI/CD

Azure DevOps separates PR validation from DEV delivery.

```text
Feature branch → Pull Request → Validation
```

Validation includes backend and delivery tests, frontend tests, TypeScript checking, a production build, Bicep compilation/linting, Docker build/smoke, and a whitespace check. Azure Repos PR validation depends on the configured branch build policy. **PR runs do not deploy.**

Successful `develop` branch CI follows:

```text
develop → validation → Docker build and smoke
        → Azure Container Registry → immutable image digest
        → Azure Container Apps
        → frontend build → Azure Static Web Apps
        → HTTP/configuration and browser smoke checks
```

Delivery accepts successful `IndividualCI` or `BatchedCI` events on `develop`; PR, manual, feature-branch, and `main` events do not enter DEV delivery. Backend images use commit/build tags and are deployed by SHA256 digest. `/health/version` exposes commit, build, and image identity for verification.

The sanitized pipeline requires environment inputs and protected secrets to be configured before delivery. See [delivery configuration](docs/dev-delivery.md). There is no production deployment pipeline.

## Testing & Quality

Latest local validation (2026-10-03):

| Suite | Result |
| --- | --- |
| Backend | 185 passed |
| Delivery/pipeline | 28 passed |
| Frontend | 92 passed |

Tests cover token validation, ownership, persistence conflicts/recovery, context limits, stream interruption/cancellation, image validation, Markdown safety, and workspace interactions. Backend integration tests use isolated Azurite services; inference tests use simulated HTTP transports rather than paid model calls.

TypeScript checking, the production build, Bicep compilation/linting, and `git diff --check` passed in local validation. Docker health/unauthenticated-access smoke is configured in CI/CD; cloud delivery evidence includes HTTP/configuration and browser smokes. These checks do not establish full authenticated product behavior or LLM response quality.

## Repository Structure

```text
frontend/             React UI, MSAL integration, API client, and tests
backend/              FastAPI, authentication, persistence, Foundry client, and tests
infra/                Bicep templates and environment parameters
scripts/              DEV delivery, smoke checks, and delivery tests
docs/                 Architecture, verification, and historical records
azure-pipelines.yml   Validation and DEV delivery
```

Historical disconnected modules are identified in the [legacy inventory](docs/legacy-inventory.md); they are outside the current application flow.

## Running Locally

Prerequisites: Python 3.11, Node.js 22.12+, npm, and Docker or the npm-based Azurite launcher. Chat also requires your own compatible Foundry deployment and Entra SPA/API registrations with a delegated scope and appropriate consent.

Start persistence from the repository root:

```bash
docker compose -f compose.azurite.yml up -d
```

Alternatively, run `bash scripts/dev/azurite.sh`.

Set up the backend:

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --require-hashes -r requirements.lock
python -m pip install -e '.[dev]'
test -f .env || cp .env.example .env
```

Configure `backend/.env` using the [backend example](backend/.env.example), then start:

```bash
python -m uvicorn app.main:app --reload --port 8000 --env-file .env
```

In another terminal, from the repository root:

```bash
cd frontend
npm ci
test -f .env.local || cp .env.example .env.local
```

Configure `frontend/.env.local` using the [frontend example](frontend/.env.example), then run:

```bash
npm run dev -- --port 5173 --strictPort
```

Open `http://localhost:5173`. Register `http://localhost:5173/redirect.html` as the SPA redirect URI. Keep the frontend origin and backend CORS configuration aligned.

| Configuration | Required inputs |
| --- | --- |
| Backend identity | `ENTRA_AUTHORITY`, `ENTRA_API_AUDIENCE`, `ENTRA_REQUIRED_SCOPE` |
| Backend inference | `FOUNDRY_ENDPOINT`, `FOUNDRY_DEPLOYMENT`, `FOUNDRY_API_KEY` |
| Local persistence | `STORAGE_AUTH_MODE=azurite`; Table/Blob defaults in the example |
| Frontend | `VITE_API_BASE_URL`, `VITE_ENTRA_CLIENT_ID`, `VITE_ENTRA_AUTHORITY`, `VITE_ENTRA_REDIRECT_URI`, `VITE_ENTRA_API_SCOPE` |

Replace example placeholders with your own values. The backend expects the scope name; MSAL requests the full delegated scope URI. Never place keys in `VITE_*` variables or commit local environment files.

Run backend tests from `backend/` with `python -m pytest`, and delivery tests from the repository root with `python -m pytest scripts/tests`. Backend integration tests require npm/Azurite availability. From `frontend/`, run:

```bash
npm test
npm exec tsc -- --noEmit -p tsconfig.app.json
npm run build
```

## Deployment

The project targets an Azure **DEV** environment: frontend on Static Web Apps, backend on Container Apps, images in ACR, persistence in Azure Storage, and inference through Microsoft Foundry.

The backend uses a digest-pinned Python base image, hash-locked runtime dependencies, HTTPS ingress, and startup/readiness/liveness probes. Container Apps is configured for zero to two replicas. Health probes check the application endpoint, not downstream identity, Storage, or model readiness.

Existing DEV delivery is recorded as successful. Delivery requires the environment inputs to be populated with the existing DEV values before a develop CI run. No private deployment identifiers are needed in this README; configuration requirements are in the [delivery guide](docs/dev-delivery.md).

## Current Scope

Open Thread focuses on AI application engineering and cloud delivery in DEV. Request/context budgets and process-local rate/concurrency controls suit the current small workload; they are not distributed admission controls. Speech input depends on browser support.

The project does not currently include:

- RAG or vector search.
- AI agents or tool/function calling.
- Model training or fine-tuning.
- A formal LLM evaluation framework.
- A production environment.

## Engineering Decisions

- **Table + Blob persistence:** structured workspace records and image bytes have separate stores, avoiding dedicated database compute for the low-volume DEV workload. Cross-service cleanup requires explicit recovery logic.
- **Separate identity boundaries:** user tokens govern API access and ownership; Managed Identity governs runtime ACR/Storage access. Foundry inference retains a separate backend key.
- **Deployment by digest:** commit/build tags identify releases, while SHA256 references fix the actual backend artifact deployed to Container Apps.
- **One concrete model integration:** the current workload uses one Foundry client, keeping integration responsibilities visible without an unused provider-selection layer.
- **Bounded inference:** context trimming, output limits, deadlines, and zero automatic retries constrain requests and avoid implicitly repeating inference.
- **Scale-to-zero DEV:** zero minimum replicas limit idle runtime usage, with cold-start latency as a tradeoff. Application health and release metadata support basic delivery verification.

## Author

**Leandro Bueno**

AI Engineer | Python • Microsoft Azure • LLMs • Cloud Engineering

[LinkedIn](https://www.linkedin.com/in/leandrosfbueno) ·
[GitHub](https://github.com/Leandrobuenodev)
