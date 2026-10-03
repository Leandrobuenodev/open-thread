# Open Thread DEV infrastructure

The existing deployment target is `<DEV_RESOURCE_GROUP>`. Existing ACA, its
managed environment and SWA retain their Azure names; see the
[delivery guide](../docs/dev-delivery.md) for exact names, permissions, configuration
and the authorization sequence.

- `main.bicep`: completed bootstrap definition for the existing Basic ACR with
  admin disabled, AcrPull assignment and ACA SystemAssigned identity. Do not rerun
  bootstrap for the first application rollout. SWA/environment are references.
- `backend.bicep`: shared ACA configuration; routine delivery updates only the ACA.
- `dev.bicepparam`: environment-supplied DEV values with compile-only placeholders; bootstrap defaults to the existing
  placeholder. The Foundry key is a secure runtime input, never a checked-in value.

The real backend uses digest-pinned images, native secret references, managed
identity for ACR pull, HTTPS ingress on targetPort 8000, CPU 0.25/memory 0.5Gi,
minReplicas 0/maxReplicas 2 and three HTTP /health probes. Probes never invoke AI.
The in-memory abuse protection is per process, not global across replicas.

The application image repository in the existing ACR is `openthread-backend`.
Bootstrap's placeholder uses
port 80 and must not be redeployed over a running real backend unintentionally.
The four previously reviewed omitted properties retain intentional Azure defaults.

Local checks (no deployment):

```bash
az bicep build --file infra/main.bicep --stdout
az bicep build --file infra/backend.bicep --stdout
az bicep lint --file infra/main.bicep
az bicep lint --file infra/backend.bicep
FOUNDRY_API_KEY_FOR_DEPLOYMENT='' az bicep build-params --file infra/dev.bicepparam --stdout
git diff --check
```

ARM validation and what-if are read-only review steps requiring Azure access.
Neither authorizes applying the template. No deployment was executed in this task.
