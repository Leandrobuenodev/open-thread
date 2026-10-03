# Streaming chat over Table + Blob

The current workspace persistence is Azure Table Storage and private Blob Storage,
validated locally with Azurite and deployed in DEV. Authenticated cloud streaming
remains partially verified; see [DEV verification](dev-full-e2e-validation.md). See [architecture, partitions and recovery](conversation-persistence.md).
There is no SQL dependency, SQL schema migration or database server.

The existing authenticated `POST /api/chat` SSE contract is preserved:
`start` identifies persisted user/assistant, `delta` appends provider text, `done`
follows successful terminal persistence, and sanitized `error` reports failure.
Foundry still uses `/openai/v1/chat/completions`, streaming, the same deployment,
and the existing output/token/body/rate/concurrency limits. No model/quota change.

Conversation ETag and a 120-second persisted lease coordinate replicas. A short
same-owner-partition transaction reserves messages/sequence and attachments before
inference. Terminal batches persist completed/failed/cancelled status and release
the lease. No Table lock/client transaction is held during provider inference.
Stop aborts the browser stream; protected disconnect cleanup saves partial text.
Expired attempts fail on the next start, and late responses cannot replace newer
attempts. Regenerate reuses the newest active user prompt; a completed-reply marker
supersedes prior completed attempts. Failed Regenerate preserves the prior answer.
Edit appends a replacement and historical branch marker, preserving old rows.

Markdown/GFM/highlighting/Copy, scroll behavior, existing UI and JSON chat API remain.
JSON failures retain the original user-only failed-turn behavior. The SSE parser
still requires a valid ordered start/delta/done stream and never automatically
retries inference. Images are reconstructed from private Blob bytes only after
conversation ownership; budget trimming includes their normalized patch estimate.

Local browser fixture (synthetic identity/provider, no cloud token/inference):

```bash
# Start Azurite separately: scripts/dev/azurite.sh
STORAGE_AUTH_MODE=azurite STORAGE_TABLE_NAME=BrowserWorkspace \
STORAGE_BLOB_CONTAINER=browser-attachments FRONTEND_ORIGIN=http://127.0.0.1:5175 \
CHAT_RATE_LIMIT_REQUESTS=100 \
python -m uvicorn browser_app:app --app-dir backend/tests --host 127.0.0.1 --port 8089
# Start Vite on 5175 with the local browser test Entra settings and API URL 8089.
python scripts/smoke/chat-experience.py
python scripts/smoke/workspace-experience.py
python scripts/smoke/storage-experience.py
```

The tests cover real HTTP/SSE arrival before provider finish, disconnect, Stop,
Regenerate/versioning, reload/history, edit, private uploads and provider context.
The harness is outside the production entry/build. It does not replace eventual
real Microsoft login, Foundry image inference or microphone/device validation.
