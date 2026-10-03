# Open Thread persistence: minimum-cost Azure Storage

The current decision is **Azure Table Storage for workspace/chat data** and
**Azure Blob Storage for images**. No relational database, ORM, SQL driver, SQL
connection URL, Alembic or numbered SQL migrations remain. Existing Git history
preserves earlier implementations. Persistence is deployed in DEV. Authenticated product verification remains partial;
see [DEV verification](dev-full-e2e-validation.md).

This choice follows this environment's explicit low-volume DEV and
minimum-operating-cost requirements. Storage is billed mainly for capacity and
operations, with no continuously running database server. It is not universally
better than a relational database. Queries, indexing, cross-partition consistency
and operational recovery require application design. The contracts allow a future
PostgreSQL, Azure SQL, Cosmos DB or other adapter if real requirements justify it.
No exact recurring price is promised: region, operations, egress and capacity vary.

## Boundaries

`ConversationStore` contains workspace operations and uses only `EntityRepository`
and `ObjectStorage` protocols. FastAPI routes and ChatService import no Azure SDKs.
The composition root selects adapters; `app/storage/azure.py` is the sole SDK
integration (`azure-data-tables`, `azure-storage-blob`, `azure-identity`).
The same adapters talk to Azurite locally and Azure DEV. Azure SDK errors
are translated to sanitized `StorageError` (503) or `StorageConflict` (409).
No automatic inference retry is introduced.

## Entity access design

One Table, **OpenThreadWorkspace**, groups all structured records for one user in
one partition. This deliberately adjusts the conceptual multi-table proposal:
co-locating conversation heads, messages and attachment metadata permits atomic
same-partition batches for lifecycle changes. Azure does not allow transactional
batches across tables or partitions. All batches have at most 100 entities;
normal chat start/completion is well below that limit.

`PartitionKey = SHA256(tid + NUL + oid)` from validated claims. Frontend never
supplies an owner. The hash is stable, hides raw identity in Blob names and avoids
invalid key characters. RowKey prefix/range queries always include this partition:

| Prefix / RowKey | Entity / fields |
|---|---|
| `c:{conversation UUID}` | Conversation title, timestamps, optional project ID, pin bool, next sequence, pending attempt/lease, deletion tombstone |
| `m:{conversation UUID}:{20-digit sequence}:{message UUID}` | User/assistant content, role, status, reply/replacement IDs, timestamps; message ownership is inherited from the owner partition and checked conversation |
| `p:{project UUID}` | Project name, timestamps, optional deletion tombstone |
| `a:{conversation UUID}:{attachment UUID}` | Sanitized filename, MIME, byte size, dimensions, Blob reference, optional message ID, `uploading/ready/retiring` state |
| `v:{conversation UUID}:{edit attempt UUID}` | Superseded sequence range marking a historical branch |
| `r:{conversation UUID}:{user-message UUID}` | Current completed assistant attempt for Regenerate |
| `t:{conversation UUID}:{message UUID}:{chunk ordinal}` | Text chunks for a large assistant response |

Messages sort by padded sequence and UUID; sequence allocation and inserts are
committed with the conversation ETag, so competing replicas cannot allocate the
same sequence. User-facing API UUIDs and paging remain unchanged. Superseded
status is calculated from persisted branch/reply markers; original content is
preserved without rewriting hundreds of rows. Large responses are split into
8,000-character chunks because Table string properties have a 64 KiB UTF-16 limit;
chunks and completed-message state commit in the same batch.

Recents/Pinned sort by updated time descending, UUID descending. Project names
sort ascending with UUID tie-break. Table has no secondary indexes: this low-volume
implementation scans the relevant owner/key range and sorts/slices in the adapter
consumer. The API retains 50-conversation and 100-message pages; the LLM context
retains the existing 20-message/byte/token limits. Retrieval can read more stored
history than the returned/context window. Large histories and hot owner partitions
would justify indexed access patterns, cursors or a different adapter later.

## Concurrency and consistency

- Updates/deletes require ETag (`IfNotModified`); no wildcard upsert overwrites.
- Start commits head lease, new user/assistant, attachments and edit marker in one
  transaction. Validation/context-budget failure commits nothing.
- Completion commits user/assistant, output chunks, active reply marker and lease
  release together. A failed completion cannot supersede the prior completed reply.
- Stop stores partial/cancelled attempt via the existing protected SSE cleanup.
- The 120-second lease expires after worker crashes; next start marks prior pending
  messages failed. Late completion cannot overwrite a newer attempt.
- GET checks the conversation ETag before/after aggregate reads and retries at most
  three times; persistent churn returns 409 rather than an inconsistent snapshot.
- Association includes a guarded Project entity in the same batch, serializing
  against deletion. Pins remain a conversation property, without separate pin rows.
- Blob and Table have **no distributed transaction**. Durable reservations and
  explicit upload/deletion states represent intermediate/failure cases.

## Blob structure and upload lifecycle

Private container `attachments`, Blob key generated entirely by the backend:

```
attachments/{owner SHA256}/{conversation UUID}/{attachment UUID}.png
```

Message ID is intentionally omitted: a staged upload exists before a user message,
and edits can retain the same normalized binary without copying it. Table metadata
supplies the message relation. The original name is only sanitized display metadata.
Never store image base64, tokens or secrets in entities. Base64 is created transiently
for the existing Foundry Chat Completions image input.

One image/message, 2 MiB input, PNG/JPEG/WebP, decoded-format/MIME validation,
16-million-pixel cap, no animated/SVG/HTML payloads, RGB PNG normalization and
256px maximum dimensions remain. Files/images are streamed through an authenticated
API download after ownership validation; the browser receives no storage key, public
URL or SAS. Responses are `private, no-store` and `nosniff`. All binary references
have a strict generated-name layout; path traversal cannot select arbitrary blobs.

Upload reserves metadata and the conversation ETag lease **before** writing Blob.
Replacement/discard drafts enter retiring state before Blob deletion. Successful
finalization atomically binds ready metadata and releases the lease. Failed writes
attempt compensation; when compensation fails, the durable reservation stays.
After lease expiry, the next conversation mutation performs guarded recovery of
unfinished upload/discard records. Conversation deletion removes the entire owned
Blob prefix, including a binary written before a process crash. Recovery cannot
bind an unfinished or retiring image to a message.

## Delete and retry

Conversation deletion first writes a guarded tombstone (active inference returns
409), making resource/message/attachment reads unavailable and preventing writes.
Then it removes all owned Blob-prefix contents, all message/attachment/version/reply/
chunk entities in guarded batches of at most 99 plus head, and finally the head.
A failure returns 503/409 and retains the head/tombstone; repeat DELETE or the next
owner's conversation-list request resumes cleanup. There is no intentional orphan.
After complete deletion, repeat DELETE returns the existing 404 behavior.

Project deletion tombstones the Project, blocks new associations and renders old
associations detached immediately. It then explicitly detaches owned conversations
and removes the Project. A partial failure is retried by DELETE or the next Projects
list request. Conversations/messages/attachments/pins are preserved. Cleanup is
request-driven in this phase, not a background scheduler; a user who never returns
can leave a tombstone pending recovery. Retain monitoring/reconciliation planning
before expanding this beyond low-volume DEV.

## Local Azurite

Use a dedicated Compose project; it does not stop or modify other containers:

```bash
docker compose -f compose.azurite.yml up -d
```

Blob is loopback port 10000; Table is 10002. Named volume preserves emulator data.
If the Docker wrapper has no underlying Docker CLI, run official Azurite via npm:

```bash
scripts/dev/azurite.sh
```

Set backend `STORAGE_AUTH_MODE=azurite`, `STORAGE_TABLE_NAME=OpenThreadWorkspace`,
`STORAGE_BLOB_CONTAINER=attachments`. Default connection uses Azurite's documented
public development credentials and explicit loopback endpoints. An optional
`AZURITE_CONNECTION_STRING` must include local HTTP Blob/Table endpoints; remote
endpoints are rejected. This mode creates emulator Table/container only; it is not
cloud provisioning. Start Azurite before starting the backend or tests.

```bash
cd backend
python -m pip install -e '.[dev]'
STORAGE_AUTH_MODE=azurite uvicorn app.main:app --env-file .env --reload
python -m pytest
```

Integration tests automatically start a session-local official Azurite process on
ephemeral ports, allocate isolated Table/container names and clean up only their own
resources/process. npm/Node must be available (including on the existing hosted CI
agent); the pipeline definition/external pipeline need no change. Pure unit tests
do not start the emulator. All former SQL persistence integrations now exercise
real Azure SDK requests to Azurite; pure auth/provider/domain tests remain.
`test_table_storage.py` covers ETags/batch rollback, replica race, lease recovery,
restart, large-output chunks, edits above 100 messages, private Blob paths and
partial deletion/upload/project failures. See the existing browser harness and
`workspace-experience.py` / `chat-experience.py` for actual React/API/SSE/Azurite
verification, using a synthetic test identity/provider/speech source.

## Future Azure authentication and IaC

Use `STORAGE_AUTH_MODE=managed_identity`, `STORAGE_ACCOUNT_NAME`, optionally explicit
`STORAGE_TABLE_ENDPOINT`/`STORAGE_BLOB_ENDPOINT` (HTTPS only). Composition uses
DefaultAzureCredential; ACA uses its existing system-assigned Managed Identity.
No connection string/account key is the cloud solution, and no storage secret goes
to Vite. The cloud adapter does not create resources at startup.

`infra/storage.bicep` and `storage.dev.bicepparam` prepare a dedicated StorageV2
Standard_LRS account, TLS 1.2, HTTPS only, private attachments container, workspace
Table, Blob public access disabled and Shared Key disabled. Data-role assignments
are scoped to this account for the existing ACA principal:
Storage Table Data Contributor and Storage Blob Data Contributor. No ACA, Foundry,
Entra or pipeline is changed by this template.

For a separate new-environment deployment (the existing DEV is already deployed): approve creation, review account name/location/cost,
apply this prepared IaC, wait for RBAC propagation, configure ACA environment
endpoints/auth mode in a separately reviewed change, validate real Entra/Foundry
and restart/reload/cleanup. Decide backups/retention/monitoring/reconciliation and
access patterns for larger data volumes. Old SQL files are not imported automatically;
no prior local data was silently transformed or removed from external databases.


## Historical pre-deployment validation

The following records an earlier preparation step, not current deployment status.
Storage and runtime RBAC are now deployed; authenticated application checks remain partial.

Bicep build/lint, parameter compilation and ARM ProviderNoRbac validation passed.
Read-only what-if returned **7 Create**, **5 Ignore**, with no Modify/Delete:
account, Blob service/private container, Table service/workspace Table and two
account-scoped role assignments. The existing ACA identity was discovered by a
read-only query; the prepared parameter file takes its principal from
`OPENTHREAD_ACA_PRINCIPAL_ID`, without embedding keys. Nothing was applied.

```bash
az bicep build --file infra/storage.bicep --outfile /tmp/openthread-storage.json
az bicep lint --file infra/storage.bicep
# Set the existing ACA principal ID (not a secret), then compile parameters:
az bicep build-params --file infra/storage.dev.bicepparam --outfile /tmp/openthread-storage.parameters.json
az deployment group validate -g "$OPENTHREAD_DEV_RESOURCE_GROUP" --template-file /tmp/openthread-storage.json --parameters @/tmp/openthread-storage.parameters.json --validation-level ProviderNoRbac
az deployment group what-if -g "$OPENTHREAD_DEV_RESOURCE_GROUP" --template-file /tmp/openthread-storage.json --parameters @/tmp/openthread-storage.parameters.json --validation-level ProviderNoRbac
```

The Docker wrapper in this workspace could not find `/usr/bin/docker`; local
validation used the official npm emulator. Dedicated Compose remains prepared.
The 14-step browser test is `scripts/smoke/storage-experience.py`, including a
fresh browser session, multiple messages, repeated reloads, pin/Project association,
Blob image, continued context, Regenerate, earlier-prompt edit and partial Stop.

Final local validation: 185 backend tests and 14 delivery tests passed, plus
92 frontend tests, TypeScript checking and the production build. Persistence
integration tests used real Azurite Table/Blob services. Ruff checks on changed
Python files and `git diff --check` passed. SQLAlchemy, psycopg and Alembic were
uninstalled from the backend validation environment before the final test run.

Primary references: [transaction batches](https://devblogs.microsoft.com/azure-sdk/announcing-the-new-azure-data-tables-libraries/),
[TableClient/ETags](https://learn.microsoft.com/en-us/python/api/azure-data-tables/azure.data.tables.tableclient),
[Azurite](https://learn.microsoft.com/en-us/azure/storage/common/storage-use-azurite),
[Storage RBAC](https://learn.microsoft.com/en-us/azure/role-based-access-control/built-in-roles/storage),
[read-only what-if validation levels](https://learn.microsoft.com/en-us/azure/azure-resource-manager/bicep/deploy-what-if).
