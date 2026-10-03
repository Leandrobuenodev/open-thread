# Current Open Thread architecture

Open Thread is an AI-enabled web application running on Microsoft Azure.
Its conversational workspace connects user identity, a protected API, persistent
data, model integration, infrastructure, and automated DEV delivery.

```text
React + TypeScript on Azure Static Web Apps
  ↔ MSAL / Microsoft Entra ID: delegated API access token
  → FastAPI on Azure Container Apps: JWT validation and ownership checks
  → ConversationStore: Azure Table persistence and bounded context
  → ChatService
  → FoundryClient
  → Microsoft Foundry / Azure OpenAI v1 Chat Completions

ConversationStore → private Azure Blob Storage: normalized image attachments
Foundry deltas → FastAPI POST/SSE → React
Terminal attempt → Azure Table Storage
```

`ChatService` delegates to one concrete `FoundryClient`. There is no provider
selection, generic provider interface, registry or fallback. FastAPI lifespan owns
its asynchronous HTTP pool. Inference uses a backend API key, a 30-second total
deadline, 5-second connection timeout and zero automatic retries.

The API validates signature, issuer, audience, expiry and delegated scope. Data
ownership derives from validated tenant/user identity. User tokens are not
forwarded to Foundry or Storage.

Conversations, messages, Projects and pins are persisted in Azure Table Storage.
Private Blob Storage holds validated images. ETags, same-partition transactions
and leases protect operations; resumable cleanup handles the Table/Blob boundary.
React display state and drafts remain in memory. Reload retrieves saved state.
The backend reconstructs bounded history; Foundry has no application session store.

The Container App system-assigned Managed Identity has AcrPull and Storage
Table/Blob Data Contributor access. It is separate from user identity and the
federated Azure DevOps delivery identity. Foundry inference does not currently use
Managed Identity.

Docker packages the backend; ACR stores tagged releases; Container Apps deploys
by digest. Bicep defines bootstrap, backend, Storage and model infrastructure.
SWA and the Container Apps Environment are existing references in current Bicep.
Azure DevOps validates PRs and automatically delivers successful develop CI to DEV.
Routine CD updates backend configuration and frontend assets, not all infrastructure.

DEV infrastructure/delivery and non-interactive smokes are verified. The configured
model is GPT-4.1 mini. Authenticated cloud product behavior remains partially
verified; see [verification](dev-full-e2e-validation.md).

Earlier release-intelligence code is disconnected from this runtime. See
[legacy inventory](legacy-inventory.md) and [historical product direction](archive/product-direction.md).
