# Multimodal workspace

The implemented workspace includes image input, browser speech dictation, prompt
revisions, Projects and pinned chats. It is deployed in DEV; authenticated product
checks remain partial. See [DEV verification](dev-full-e2e-validation.md).
Persistence is Azure Table Storage + private Blob Storage, with Azurite locally.
See [current architecture, setup and consistency](conversation-persistence.md).

## Provider compatibility and DEV budget

Read-only deployment inspection confirmed `openthread-chat` is
`gpt-4.1-mini`, version `2025-04-14`, provisioning state `Succeeded`.
[Microsoft's model capabilities](https://learn.microsoft.com/en-us/azure/foundry/foundry-models/concepts/models-sold-directly-by-azure#gpt-41-series)
include image input, Chat Completions and streaming. The existing
`/openai/v1/chat/completions` request uses a content array:

```json
{"role":"user","content":[
  {"type":"text","text":"Describe this image"},
  {"type":"image_url","image_url":{"url":"data:image/png;base64,<encoded private image>"}}
]}
```

[Microsoft's vision API format](https://learn.microsoft.com/en-us/azure/ai-services/openai/how-to/gpt-with-vision)
supports data URIs. Base64 exists only in memory during inference, never in the
Message table, public URLs, API responses, logs or frontend token storage.
Local provider tests inspect the actual outgoing HTTP request; browser tests use
synthetic provider/identity. No live Foundry image inference was executed.

The existing 1,000-token DEV budget, 100-token safety margin and 256-token output
reserve remain. Each image is conservatively charged **104 input tokens**:
up to 64 patches of 32×32 pixels, multiplied by 1.62 for this model snapshot
([image token calculation](https://developers.openai.com/api/docs/guides/images-vision)).
Images are downscaled to at most **256×256**, preserving aspect ratio. Text is
still estimated by UTF-8 bytes. The existing bounded recent context window is
trimmed oldest-first, excludes superseded/failed/partial assistant versions,
and removes leading assistant fragments. Current prompt+image must fit; otherwise
HTTP 422 occurs before persisting an inference attempt. With defaults, an image
leaves at most 468 UTF-8 bytes for the current text. Fine print and small objects
can be lost at this resolution; increasing resolution requires revisiting quota.

## Attachments and storage

Binary data is stored in a private Blob container; Table stores metadata/state and
backend-generated owner/conversation references. Authenticated API downloads validate
ownership. The injected ObjectStorage contract supports different adapters without
changing domain/API/frontend. The old filesystem adapter has been removed.
One PNG/JPEG/WebP image, 2 MiB input, actual decoded MIME validation, 16-million-pixel
limit, normalization to RGB PNG/256px, no animated/SVG/HTML content and path traversal
protection remain. See the persistence design for reservations, retiring states,
request-driven recovery, deletion tombstones and resumable cleanup.

## Prompt editing

`POST /api/conversations/{id}/messages/{message_id}/edit` accepts edited text and
uses the same authenticated SSE/Stop/Regenerate pipeline. Ownership is checked
for both conversation and user message. Assistant or superseded messages cannot
be edited. The text must be nonempty and respect the UTF-8 message limit.

The backend creates a new user UUID with `replaces_id` pointing to the prior
prompt, reserves monotonically increasing sequence numbers, and marks that prompt
and its entire later branch `superseded` in the same transaction. Old rows and
attachments remain retrievable and labeled Previous version in the UI; they are
excluded from logical model context. The new response is a normal assistant
attempt. A provider failure or Stop preserves the edited prompt/partial attempt;
Regenerate resumes from the newest active user prompt. Validation/budget errors
roll back branch supersession. The initial conversation title remains stable.
This phase edits text and retains the original image; image replacement/removal
within an edited historical prompt is not exposed.

## Projects, pins and API

`Project`: UUID, owner partition derived from validated `(tid, oid)`, name
(up to 80 characters), UTC creation/update timestamps. Conversation has nullable
`project_id` (explicitly detached on Project deletion) and `is_pinned` (false by default).

- `GET/POST /api/projects`: list/create owned Projects.
- `PATCH/DELETE /api/projects/{id}`: rename/delete owned Project. Delete detaches
  conversations, preserving messages/images/pins even during an active chat.
- `PATCH /api/conversations/{id}`: update `project_id` or `is_pinned`. Both the
  conversation and target Project must belong to the authenticated user.
- `GET /api/library?offset=0`: owned pinned/project conversations, 50 per page,
  ordered by conversation updated time descending, then UUID descending.
  Sidebar loads successive pages independently of the first Recents page, so
  old pins and project chats remain visible.
- `POST /api/conversations/{id}/attachments?filename=...`: raw image bytes, MIME
  in Content-Type. Returns metadata only.
- `GET/DELETE /api/conversations/{id}/attachments/{attachment_id}`: private
  download/discard staged image. Bound images cannot be removed individually.
- `POST /api/chat`: existing SSE request plus `attachment_ids` (maximum one).
  Text may be omitted/empty when there is an image. Image input requires streaming.
- Existing conversation CRUD, paging and Regenerate remain.

Frontend adds project creation dialog with async errors, inline expand/rename/delete,
per-conversation Project selection/detach and pin/unpin. Pinned appears only when
there are pins. Reload/new authenticated session re-fetches backend records;
there is no browser session-only data store. Project instructions, project-level
LLM context, moving files between projects and sharing are outside this package.

## Speech-to-text

Web Speech API (`SpeechRecognition` or `webkitSpeechRecognition`) is detected at
runtime. Microphone toggles start/finish and offers cancel. Final transcript is
appended to the editable composer; **recognition never calls send**. Permission
errors, no speech, start errors, unsupported browsers, unmount and disabled states
are handled. Controls have at least 44×44 touch targets. Browser locale selects the
recognition language; keyboard input remains available without recognition support.

[MDN documents limited browser support and possible server-based recognition](https://developer.mozilla.org/en-US/docs/Web/API/SpeechRecognition).
The microphone tooltip discloses the browser's online service. Open Thread creates
no speech resource or paid API integration, stores no audio, and cannot guarantee
offline recognition. Use a secure origin (localhost works) and a compatible browser.

## Verification

There are no SQL migrations. Entity creation is versioned in code; backward-compatible
property changes can evolve the adapter. Formal schema/data conversion requires an
explicit future strategy rather than pretending relational migration semantics.

Run backend tests against Azurite, frontend tests, typecheck/build and delivery guards.
`test_table_storage.py` exercises actual Table ETags/batches, replicas/recovery,
large text, restart, private Blob ownership and partial cleanup failures.
`test_workspace.py` and `test_chat_stream.py` retain workspace/multimodal/SSE/Stop/
edit/Regenerate coverage. Browser scripts exercise the five features together using
actual React/API/Table/Blob and deterministic identity/provider/speech fixtures.
The current architecture/setup and cloud prerequisites are in the persistence guide.
No Azure resource, commit, push or deployment is performed in this package.
