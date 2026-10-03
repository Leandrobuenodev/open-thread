# LEGACY / HISTORICAL / NOT CURRENT ARCHITECTURE

This records the abandoned release-intelligence direction. Open Thread currently
runs an AI conversational workspace with persistent data and automated DEV delivery on Azure.
See [current architecture](../architecture.md). Statements below describe the historical experiment only.

# Product direction

## Previous direction

Azure AI Assist began as a generic Azure-focused AI chat experience.

## Current direction

The project pivoted to Deployment / Release Intelligence under the name
EvidenceOps, then adopted its definitive name, Open Thread.

Open Thread is a Deployment / Release Intelligence product for
Azure DevOps and Azure Container Apps.

The core product question is:

> Is the version that passed CI actually the version running in DEV?

The initial integration target is Azure DevOps + Azure Container Apps. The
first product shell uses local mock release data; it does not provision Azure
resources or call Azure APIs.

## Core flow

```text
Release data → deterministic detection → automatic AI report → optional conversational investigation
```

The release detail page shows the analysis before the user asks a question.
The existing AI chat remains available as AI Investigator for deeper,
conversational investigation. Future evidence can include an application
`GET /health/version` endpoint that reports the serving commit, build, image
digest, and migration version. Evidence-source configuration lives under the
small Settings → Integrations surface rather than in the primary release
workflow.
