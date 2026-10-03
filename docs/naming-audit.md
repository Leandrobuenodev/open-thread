# LEGACY / HISTORICAL / NOT CURRENT ARCHITECTURE

This is a dated process record. Its targets, planned work, and product direction
do not describe current runtime or deployment status. See [current architecture](architecture.md)
and [DEV verification](dev-full-e2e-validation.md).

# Open Thread naming audit

Audit date: 2026-10-01. Definitive display name: **Open Thread**.
Local identifiers use the existing `openthread` convention from the backend
image example and Foundry resources; the existing `open-thread` tag convention
also remains valid. No commit, push or external mutation was performed.

Publication follow-up on 2026-10-01: the local origin now points to
`https://dev.azure.com/<AZURE_DEVOPS_ORGANIZATION>/Open%20Thread/_git/Open%20Thread` for
fetch and push, on branch `develop`. The external-name inventory below records
the earlier audit state; it does not describe the current project/repository URL.
The later delivery preparation also changed the local infrastructure candidate
and image repository convention; see [DEV delivery readiness](dev-delivery.md).

## Scope and classification before edits

The working tree was clean. Searches covered tracked and hidden local files,
including ignored environment files and generated package metadata. Git remote
configuration was inspected separately. Dependency trees, virtual environments,
binary assets, build output and caches are generated artifacts rather than
project source; Git history was not rewritten. No project AGENTS.md was found.
No additional legacy pivot brand was found beyond the three known names.

| Category | Original occurrence(s) | Decision |
| --- | --- | --- |
| A | `backend/pyproject.toml`: distribution name and description | Local distribution becomes `openthread-backend`; imports remain `app`. No published-package dependency was found. |
| A | `backend/app/main.py`: API title; `backend/app/__init__.py`: docstring | Use Open Thread. |
| A | `frontend/package.json` and both root names in `frontend/package-lock.json` | Private package becomes `openthread-frontend`; dependency versions stay unchanged. |
| A | `frontend/src/app/AuthenticatedShell.tsx`: brand | Use Open Thread. |
| A | `frontend/src/domain/mockReleaseData.ts`: project display name | Use Open Thread; dated release evidence stays intact. |
| A | `frontend/src/collections/CollectionPages.tsx`: introductory copy and fictional DevOps project/repository/pipeline labels | Use Open Thread / openthread / openthread-ci. These labels belong to the explicitly mocked `contoso-engineering` integration, not the real remote. |
| A | `infra/README.md`: heading and introduction; `infra/main.bicep`: product wording in parameter description | Use Open Thread; image repository example stays unchanged. |
| A + C | `docs/archive/product-direction.md`: current product statement and original pivot | Current statement uses Open Thread; explicitly record the historical EvidenceOps pivot and preserve Azure AI Assist origin. |
| B | `infra/dev.bicepparam`: `evidenceops-dev-web`, `evidenceops-dev-cae`, `evidenceopsdevacr` | Preserve resource base names, including their deterministic suffix behavior. |
| B | `infra/budget.dev.bicepparam`: `budget-evidenceops-dev` | Preserve budget resource identity. |
| B | `infra/main.bicep`: `project: 'evidenceops'` | Preserve deployed tag contract; consumers of tags were not externally audited. It is metadata, not a resource rename. |
| B | `infra/main.bicep` image example and `infra/README.md` image repository: `evidenceops-backend` | Preserve technical image path; changing package metadata does not rename an ACR repository. |
| B | `infra/README.md`: future target `rg-evidenceops-dev` | Preserve configured/documented deployment target; not evidence of a live group. |
| B | `infra/foundry.README.md`: `<DEV_RESOURCE_GROUP>` in inventory and two CLI examples | Preserve actual resource-group reference, including validation/what-if command targets. |
| B | `frontend/src/collections/CollectionPages.tsx`: mocked `rg-evidenceops-dev` and `evidenceops-dev-api-<unique>` | Preserve examples aligned with the legacy infrastructure naming; not proof of live resources. |
| B | Git origin fetch/push URL | Preserve remote and organization/project/repository URL components. |
| C | `frontend/src/domain/mockReleaseData.ts`: all three `evidenceops-ci` pipeline strings, three CI stage details, three `evidenceops-backend:20260922.*` artifacts and three `evidenceops-dev-api--0000*` revisions | Preserve dated mock release evidence and incident correlation. These are historical identifiers, not current product branding. |
| C | `backend/tests/test_foundry.py`: negative assertion against `EvidenceOps/0.1.0` | Preserve regression coverage rejecting the historical custom User-Agent. |
| C | `docs/overnight-progress.md`: original repository name `Azure-AI-Assist` | Preserve provenance of the dated review. |
| A, generated | Ignored `backend/evidenceops_backend.egg-info/` and `backend/azure_ai_assist_backend.egg-info/` | Obsolete local generated metadata removed after successfully building the renamed wheel; regenerated as `backend/openthread_backend.egg-info/`. Not distributed by Git. |

## Remaining occurrences after local changes

All remaining source occurrences are the B/C entries above. The two explicit
legacy names in the product direction document now describe past transitions.
This audit document deliberately repeats legacy names to explain retained
references and external migration actions. The obsolete ignored egg-info directories were removed and the new package
metadata was regenerated from the updated manifest. Rebuilt frontend output can still contain the retained mock
technical/historical strings. The local checkout directory is still named
`Azure-AI-Assist`; moving it is outside the source changes and may affect tooling.

## External inventory and required actions (not executed)

Only repository evidence and local Git configuration were inspected. No live
Azure, Entra or DevOps inventory query was performed; undocumented external
names and IDs are unknown.

| Service | Current evidence | Rename implications |
| --- | --- | --- |
| Azure DevOps organization | Origin uses `Azure-AI-Assist` | Organization rename is an external settings action affecting URLs and integrations; not merely a display label. |
| Azure DevOps project | Origin uses `EvidenceOps` | Rename the existing project in Project settings > Overview > Name > Save. Keeps the existing project rather than creating another; project URLs and name-based references need review. |
| Azure DevOps repository | Origin uses `EvidenceOps` | Rename the existing repository with `az repos update` or repository settings, preserving Git history and repository identity. Its clone URL changes. |
| Azure DevOps pipeline | External definition name/ID unknown; YAML has no legacy display names | Query the definition before proposing a rename. Historical mock `evidenceops-ci` is not a live inventory result. Rename an existing definition by ID to preserve run history. |
| Azure resources | Legacy base names and budget in Bicep; documented Foundry group `<DEV_RESOURCE_GROUP>` | Resource names are technical identities, not display names. Resource group rename requires a new group and supported resource moves; other resource names require a service-specific migration/new resource, not a string replacement. Changing Bicep base names may create different resources. |
| Azure image repository | Documented `evidenceops-backend` path | Requires publishing/copying images under a new repository path and updating consumers/digests; not a display-name change. |
| Azure project tag | Bicep has `project: evidenceops` | Metadata can be updated without recreating resources, after checking tag-based automation/cost queries. No tag change was applied. |
| Foundry | Documented account `<FOUNDRY_ACCOUNT_NAME>` and deployment `openthread-chat` | Already follows current naming; enclosing legacy group stays intact. |
| Entra | No legacy registration display names found in local files | Live registration names are unknown. An existing application's displayName can be changed independently; preserve client/object/tenant IDs, scopes, identifier URIs and redirects. Enterprise application display name is a separate service-principal property to inspect. |

Suggested commands for a separately authorized external task, after verifying
IDs and the current live state (placeholders are intentional):

```bash
# Read-only discovery; no pipeline name is inferred from the mock data.
az devops project show --org "https://dev.azure.com/<AZURE_DEVOPS_ORGANIZATION>" --project EvidenceOps
az repos show --org "https://dev.azure.com/<AZURE_DEVOPS_ORGANIZATION>" --project EvidenceOps --repository EvidenceOps
az pipelines list --org "https://dev.azure.com/<AZURE_DEVOPS_ORGANIZATION>" --project EvidenceOps --query '[].{id:id,name:name}'

# Rename project through Project settings > Overview first.
# Reuse the existing repository and pipeline IDs; do not create replacements.
az repos update --org "https://dev.azure.com/<AZURE_DEVOPS_ORGANIZATION>" --project 'Open Thread' --repository '<existing-repository-id>' --name openthread
az pipelines update --org "https://dev.azure.com/<AZURE_DEVOPS_ORGANIZATION>" --project 'Open Thread' --id '<existing-pipeline-id>' --new-name 'Open Thread CI'

# Only after the server-side renames; organization remains unchanged here.
git remote set-url origin 'https://dev.azure.com/<AZURE_DEVOPS_ORGANIZATION>/Open%20Thread/_git/openthread'

# Only after inspecting the existing Entra registration and authorizing its label.
az ad app update --id '<existing-application-id>' --display-name 'Open Thread'
```

Project/repository rename guidance: [project rename](https://learn.microsoft.com/en-us/azure/devops/organizations/projects/rename-project?view=azure-devops)
and [repository rename](https://learn.microsoft.com/en-us/azure/devops/repos/git/repo-rename?view=azure-devops).
CLI references: [pipeline update](https://learn.microsoft.com/en-us/cli/azure/pipelines?view=azure-cli-latest#az-pipelines-update)
and [Entra application update](https://learn.microsoft.com/en-us/cli/azure/ad/app?view=azure-cli-latest#az-ad-app-update).
Resource group migration: [move resources](https://learn.microsoft.com/en-us/azure/azure-resource-manager/management/move-resource-group-and-subscription).

## Validation

- Frontend: `npm test -- --run`: 54 tests passed in five files.
- Frontend: `npm exec tsc -- --noEmit -p tsconfig.app.json`: passed.
- Frontend: `npm run build` (`tsc -b && vite build`): passed.
- Backend: `/tmp/openthread-mini-venv/bin/python -m pytest -q` from backend:
  90 passed on Python 3.11.15; one existing Starlette/httpx deprecation warning.
  The repository backend `.venv` has no pytest; the prepared Python 3.11
  environment was used instead, without changing dependencies.
- Bicep CLI 0.47.16: build and lint passed for main, budget and foundry templates;
  build-params passed for all three parameter files. Foundry capacity was set
  to 1 only for local compilation of its environment-dependent parameters.
  No deployment, provider validation, what-if or resource mutation was run.
- Backend packaging: `uv build backend --wheel --out-dir /tmp/openthread-naming-dist`: passed; produced `openthread_backend-0.1.0-py3-none-any.whl`. Temporary source build output was removed.
- Post-change legacy-name search and `git diff --check`: passed review.
