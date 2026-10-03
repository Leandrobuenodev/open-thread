# Open Thread DEV delivery

DEV delivery is implemented and deployed. Successful develop branch CI validates
and updates the existing Container App and Static Web App. PRs validate without
changing Azure. Full authenticated product verification remains partial; see
[recorded DEV verification](dev-full-e2e-validation.md).

## Public configuration

Environment-specific values are supplied through the protected/restricted
`openthread-dev-delivery` Azure DevOps variable group, not committed source.
Before adopting this sanitized configuration, an authorized operator must add the
following variables with the existing DEV values. This cleanup does not change
Azure or Azure DevOps configuration. Do not merge for automatic delivery until
these inputs are populated; missing inputs fail before Docker or Azure commands.

| Variable | Purpose |
| --- | --- |
| `OPENTHREAD_AZURE_SUBSCRIPTION_ID` | Expected subscription; retains the wrong-subscription guard |
| `OPENTHREAD_DEV_RESOURCE_GROUP` | Existing DEV resource group |
| `OPENTHREAD_CONTAINER_APP_NAME` | Full existing Container App name |
| `OPENTHREAD_ACR_NAME` | Existing registry name |
| `OPENTHREAD_CONTAINER_APPS_ENVIRONMENT_NAME` | Full existing managed environment name |
| `OPENTHREAD_STORAGE_ACCOUNT_NAME` | Existing storage account name |
| `OPENTHREAD_FRONTEND_ORIGIN` | Existing HTTPS SWA origin, without trailing slash |
| `ENTRA_AUTHORITY` | Backend tenant-specific v2.0 authority |
| `ENTRA_API_AUDIENCE` | Existing API client ID / expected audience |
| `ENTRA_REQUIRED_SCOPE` | Delegated scope name |
| `FOUNDRY_ENDPOINT` | Existing HTTPS resource root |
| `FOUNDRY_DEPLOYMENT` | Existing model deployment name, e.g. openthread-chat |
| `VITE_ENTRA_CLIENT_ID` | Existing SPA client ID |
| `VITE_ENTRA_AUTHORITY` | Existing SPA authority |
| `VITE_ENTRA_API_SCOPE` | Full delegated API scope URI |
| `FOUNDRY_API_KEY` | **Secret** existing Foundry key |
| `SWA_DEPLOYMENT_TOKEN` | **Secret** existing SWA publishing token |

Target identifiers are configuration, not credentials. Keep keys/tokens secret;
never put them in browser variables, command arguments, logs or build arguments.
The frontend redirect is derived as `${OPENTHREAD_FRONTEND_ORIGIN}/redirect.html`;
it must match the existing SPA registration. This cleanup does not change Entra.

A separate bootstrap using main.bicep also needs existing resource base names:
`OPENTHREAD_STATIC_WEB_APP_BASE_NAME`,
`OPENTHREAD_CONTAINER_APPS_ENVIRONMENT_BASE_NAME`,
`OPENTHREAD_CONTAINER_APP_BASE_NAME`, and optionally `OPENTHREAD_ACR_BASE_NAME`.
Use the same established names and suffix convention; these are not rename requests.
The default placeholders allow CI compilation, not a real deployment.

The separate budget parameters require `OPENTHREAD_BUDGET_NOTIFICATION_EMAIL`.
Set `OPENTHREAD_BUDGET_NAME` to the existing budget name when managing an existing
budget. The template is not part of routine delivery.

## Runtime and delivery identities

User access tokens authorize the API and workspace ownership. The Container App
system-assigned Managed Identity pulls images with AcrPull and accesses Table/Blob
with their Data Contributor roles. Foundry inference uses its API key.
The ARM service connection uses workload identity federation; it is a separate
delivery identity. SWA publishing uses its deployment token.

Routine CD requires registry push/read, app update, environment read/join, and
resource-group deployment permissions. Bootstrap creation/RBAC administration is
separate; routine delivery does not need Foundry/Storage creation or role writes.

## Actual pipeline flow

Validation runs backend and delivery tests, frontend tests/typecheck/build,
main/backend/storage Bicep compilation/lint, Docker build/health/401 smoke, and
whitespace checks. The blocking develop build policy is external configuration.

DeliverDev requires successful validation, refs/heads/develop, and IndividualCI
or BatchedCI. It uses the openthread-dev environment with sequential locking.
Manual, PR, feature and main events do not deliver DEV.

The script checks the subscription, existing ACR, runtime identity and AcrPull;
builds linux/amd64; tests the container without secrets; pushes a commit/build tag;
resolves the digest; and applies only backend.bicep in Incremental mode. It writes
secure parameters to a temporary 0600 file and suppresses protected command output.
It then builds/publishes frontend assets and runs HTTP/configuration and browser
smokes. The script does not bootstrap ACR, Storage, Foundry or Entra.

Do not apply deployBackend=false bootstrap configuration over a real backend:
that mode restores a public placeholder intentionally.

## Verification boundaries

Recorded build #46 delivered DEV successfully. Health/version, digest identity,
HTTPS, unauthenticated rejection, Storage configuration and runtime RBAC are
verified. Automated browser smoke never signs in or performs inference.
Legitimate-user chat/streaming/image tests and two-user isolation remain pending.

Health probes do not call Foundry or establish downstream readiness. Limits are
process-local; Table leases/ETags coordinate conversations across replicas, not
global rate limits. What-if/ARM validation are separately recorded manual checks,
not routine pipeline stages. No production delivery is implemented.
