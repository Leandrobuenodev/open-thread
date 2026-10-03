# Open Thread DEV inference infrastructure

This isolated entrypoint declares only an OpenAI inference account (S0) and
one model deployment. Provisioning this model is separate from routine backend delivery.
It does not modify ACR, ACA, SWA, Entra, RBAC or billing.

## Recorded configuration — 2026-10-01

Environment identifiers below are placeholders. Model deployment and one direct
client call were verified at the recorded date; authenticated application E2E remains partial.

| Setting | Value |
| --- | --- |
| Subscription | `<AZURE_SUBSCRIPTION_ID>` |
| Tenant | `<AZURE_TENANT_ID>` |
| Resource group | `<DEV_RESOURCE_GROUP>` |
| Region | `brazilsouth` |
| Account kind / SKU | `OpenAI` / `S0` |
| Account name | `openthread-dev-foundry-` plus `uniqueString(resourceGroup().id)` |
| Model / version | `gpt-4.1-mini` / `2025-04-14` |
| Deployment | `openthread-chat` |
| Deployment type | `GlobalStandard`, consumption billing |
| Reviewed capacity | 1 unit: 1,000 TPM / 1 RPM according to the catalog |

The subscription returned quota limit 200, usage 0 and available capacity 200
for this exact region/model/type. The catalog omits minimum/step; provider-level
ARM validation of the 1-unit candidate succeeded. Provisioning of this exact 1-unit configuration subsequently succeeded. One unit is suitable for occasional DEV smoke tests and can
throttle consecutive calls; it is not a spending limit. No retries are added.

Capacity remains explicitly supplied through `FOUNDRY_REVIEWED_CAPACITY`, with
no default and template guards of 1–10 units. Never allocate all available quota
automatically. `NoAutoUpgrade` pins the version. The catalog reports `Legacy`
and inference retirement on 2027-04-14; reconfirm before future changes.

GlobalStandard can process globally; Brazil South does not imply Brazil-only
processing. Public HTTPS and API-key authentication match the current client.

## Build and review

```bash
BICEP_BIN="$HOME/.azure/bin/bicep"
"$BICEP_BIN" build infra/foundry.bicep --stdout > /tmp/openthread-mini-template.json
"$BICEP_BIN" lint infra/foundry.bicep
FOUNDRY_REVIEWED_CAPACITY=1 "$BICEP_BIN" build-params infra/foundry.dev.bicepparam --stdout > /tmp/openthread-mini-parameters.json
python3 - <<'PARAMS'
import json
from pathlib import Path
bundle = json.loads(Path('/tmp/openthread-mini-parameters.json').read_text())
Path('/tmp/openthread-mini-arm-params.json').write_text(bundle['parametersJson'])
PARAMS
az deployment group validate --subscription "$OPENTHREAD_AZURE_SUBSCRIPTION_ID" --resource-group "$OPENTHREAD_DEV_RESOURCE_GROUP" --name openthread-foundry-dev-review --template-file /tmp/openthread-mini-template.json --parameters @/tmp/openthread-mini-arm-params.json --validation-level Provider
az deployment group what-if --subscription "$OPENTHREAD_AZURE_SUBSCRIPTION_ID" --resource-group "$OPENTHREAD_DEV_RESOURCE_GROUP" --name openthread-foundry-dev-review --template-file /tmp/openthread-mini-template.json --parameters @/tmp/openthread-mini-arm-params.json --mode Incremental --validation-level Provider --result-format FullResourcePayloads
```

Stop for Delete, unrelated changes or unexpected modifications. After review and
authorization, use the same compiled files with `az deployment group create`
in Incremental mode, named `openthread-foundry-dev`. Never use Complete mode.

## Local configuration and validation

Outputs contain only account name, endpoint root and deployment name. Capture
keys without printing them, shell tracing or debug logging. Confirm
`git check-ignore backend/.env` before writing the key. Preserve other settings.
Set only `FOUNDRY_ENDPOINT`, `FOUNDRY_DEPLOYMENT=openthread-chat` and
`FOUNDRY_API_KEY` in that local ignored file. Do not place keys in documentation,
tracked files, frontend variables or command arguments.

Start from `backend` with the project's Python environment:
`python -m uvicorn app.main:app --host 127.0.0.1 --port 8107 --env-file .env`.
Check both health endpoints and unauthenticated `/api/chat` rejection. Prefer
a real Entra-authenticated HTTP test; otherwise explicitly load `.env` and test
`FoundryClient` directly. A direct test does not establish authenticated E2E.
Limit smoke tests to three short inference calls, stopping after success.

## Execution result — 2026-10-01

Provider validation and Bicep build/lint/parameter compilation passed. What-if
returned 2 Create (account and deployment), 3 Ignore (existing resources), with
no Modify/Delete. Incremental deployment `openthread-foundry-dev` succeeded.
Account `<FOUNDRY_ACCOUNT_NAME>` and child `openthread-chat` both
reported Succeeded, with the exact model/version/type and 1-unit allocation.
The reported deployment limits are 1 RPM and 1,000 TPM.

The ignored local `backend/.env` was configured without exposing the key, with
permissions 0600. Python 3.11.15 backend startup explicitly loaded that file.
Both `/health` and `/health/version` returned 200; `/api/chat` without bearer
token returned 401 with `WWW-Authenticate: Bearer`. One real call through the
existing FoundryClient returned `OK`; no retries or additional calls were made.
No real API-scope Entra bearer token was available locally, so authenticated
HTTP E2E and real browser login remain pending. No auth bypass was introduced.

Backend validation: 90 tests passed (one Starlette/httpx deprecation warning).
The smoke-test backend was stopped after validation. No application deployment,
commit, push or pipeline was executed; existing workspace changes were preserved.

## Consumption cost

Official Microsoft retail prices consulted on 2026-10-01 for Brazil South,
GPT-4.1 mini GlobalStandard: input USD 0.40, cached input USD 0.10, output
USD 1.60 per million tokens. No PTU is selected. 1,000 requests with 1,000
uncached input and 500 output tokens each cost USD 1.20 for inference only.
This is illustrative, excluding taxes, exchange rates and other services.

## Official references

- [Foundry v1 API, Azure OpenAI endpoints and authentication](https://learn.microsoft.com/en-us/azure/foundry/openai/api-version-lifecycle?tabs=key)
- [Model capabilities](https://learn.microsoft.com/en-us/azure/foundry/foundry-models/concepts/models-sold-directly-by-azure)
- [Regional model availability](https://learn.microsoft.com/en-us/azure/foundry/foundry-models/concepts/models-sold-directly-by-azure-region-availability)
- [Quota management](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/quota)
- [Model retirement schedule](https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/model-retirement-schedule)
- [Account ARM schema](https://learn.microsoft.com/en-us/azure/templates/microsoft.cognitiveservices/2025-06-01/accounts)
- [Deployment ARM schema](https://learn.microsoft.com/en-us/azure/templates/microsoft.cognitiveservices/2025-06-01/accounts/deployments)
- [Azure OpenAI pricing](https://azure.microsoft.com/en-us/pricing/details/azure-openai/)
