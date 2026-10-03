# LEGACY / HISTORICAL / NOT CURRENT ARCHITECTURE

This is a dated process record. Its targets, planned work, and product direction
do not describe current runtime or deployment status. See [current architecture](architecture.md)
and [DEV verification](dev-full-e2e-validation.md).

# Open Thread local reliability review

## Execution boundary

Started 2026-09-30, America/Sao_Paulo. Repository: Azure-AI-Assist;
branch develop; HEAD ee33538b783d78ade60a230740c05dfd867dd50d.
Existing migration and isolated Foundry infrastructure changes remain uncommitted.
Initial tracked diff snapshot: `/tmp/openthread-overnight-initial.diff`.
No Azure queries, inference, provisioning, commits or pushes are authorized here.

Prior evidence: backend 79 tests passed on Python 3.11.15; frontend tests,
typecheck and build passed. Real Foundry provisioning stopped at zero available
quota; no account, model deployment or key was created. This is historical
evidence, not a fresh external verification.

## Prioritized findings and completion criteria

| Priority | Evidence and impact | Completion criterion | Status |
| --- | --- | --- | --- |
| Functional/authentication | AuthGate replaces authenticated children whenever MSAL is busy, destroying conversation state during token acquisition. | Keep authenticated children mounted; regression test refresh and startup states. | Complete |
| Functional | App uses render-state guards and timestamp IDs; repeated sends can race and duplicate keys. | Synchronous request guard, unique IDs, cancellation on unmount; tests. | Complete |
| Integration/errors | api.ts trusts successful JSON, accepts blank replies, exposes server error detail and has no deadline. | Validate response, bound request duration, actionable safe errors; tests. | Complete |
| Recovery/accessibility | Draft cleared before success; Enter during IME composition submits; long unbroken messages may overflow. | Retain failed draft, prevent composition sends, restore focus and contain long text; local tests/browser checks. | Complete |
| Backend configuration | URL parsing strips control characters; non-ASCII API-key headers can fail outside safe error handling. | Reject malformed configuration without exposing its contents; mock-only tests. | Complete |
| Execution/documentation | Docker executable cannot access Docker Desktop in this WSL distro. | Record limitation; verify Python 3.11 startup and healths independently. | Complete |

## Tool availability and limits

Python 3.11.15 is available at `/tmp/openthread-foundry-venv/bin/python`.
Node 22.23.1 and project dependencies are installed. Cached Chromium and
Playwright are available for local browser inspection.

No callable native task scheduler for this chat/project was exposed in tool
discovery. The Sites scheduler belongs to website publishing and is unsuitable.
The requested one-shot resume for 2026-10-01 00:35 America/Sao_Paulo has **not
been registered**. No sleeping process or replacement Codex session is used.
Official reference: https://learn.chatgpt.com/docs/automations?surface=app.
No account usage meter is exposed; the exact 98% stopping threshold cannot be
guaranteed. Goal token accounting is not account usage.

## Completed work and independent review

- Kept chat mounted during token acquisition, gated startup/redirect handling,
  and reset the subtree on account changes to prevent cross-account UI state.
- Preserved configured MSAL scopes and popup renewal; rejected empty tokens,
  prevented duplicate sign-in/sign-out and displayed safe authentication errors.
- Added synchronous send guards, UUID message IDs and browser cancellation on
  unmount, including the interval while token acquisition is pending.
- Validated successful API payloads, normalized the base URL, applied a 40-second
  browser deadline and safe status/network/response errors. No automatic retry.
- Retained failed drafts and avoided duplicate user bubbles on identical retries;
  respected IME composition and restored composer focus after loading.
- Wrapped long unbroken messages; raised small-text contrast from 3.19–3.62 to
  5.87–6.96. Added mobile sidebar Escape, focus containment/return and inert main.
- Converted configuration-dependent startup imports to an error boundary so
  missing frontend configuration displays a safe alert instead of a blank page.
- Rejected endpoint control characters and malformed API-key header credentials
  before HTTP; preserved lifespan reuse/close, deadlines and zero retries.
- Updated existing setup/recovery documentation and distinguished historical
  infrastructure review from the later quota-blocked provisioning attempt.
- Reviewed the combined diff and all affected consumers again. JWT protection,
  request/response fields, CORS, healths and in-memory-only behavior remain intact.
  No functional provider selection/fallback remains in application source.

## Final validation evidence

| Check | Result |
| --- | --- |
| `/tmp/openthread-foundry-venv/bin/python -m pytest -q` from backend | **90 passed**, Python 3.11.15. One existing Starlette TestClient/httpx deprecation warning. Mock transport only. |
| `npm test` from frontend | **36 passed**, four files. DOM tests use jsdom; MSAL fixtures do not prove actual sign-in. |
| `npx tsc -b` from frontend | Passed. |
| `npm run build` from frontend | Passed. Both main and MSAL redirect entries generated. |
| Explicit backend startup | Uvicorn started on 127.0.0.1:8107 using Python 3.11.15 and `--env-file .env`. |
| Local `/health`, `/health/version` | Both **200**. Unset release metadata is returned as null, not invented. |
| Local POST `/api/chat` without token | **401**, `WWW-Authenticate: Bearer`. No model request made. |
| Vite startup | Started on 127.0.0.1:5187 with `--strictPort`; existing project processes were preserved. |
| Chromium inspection | Landing: 1440/390/320 px, no horizontal overflow, broken internal anchors or page errors. Chat: simulated failure/retry with 5,000-character messages, focus restoration, no duplicated user bubble or overflow. Mobile sidebar Tab/Shift-Tab/Escape/return-focus passed. Simulated missing configuration showed safe startup alert. |
| Docker | Build not run: Docker Desktop is unavailable to this WSL distribution. Dockerfile/context inspected; Python 3.11, port 8000, non-root process and secret exclusions remain. |
| `git diff --check` | Passed. |
| Final functional legacy search | No AIProvider/OpenCodeGoProvider/OPENCODE_GO references in backend application or frontend source. Negative tests/historical migration notes intentionally remain. |

Browser script/results/screenshots are local temporary artifacts:
`/tmp/openthread-browser-review.cjs`, `/tmp/openthread-browser-results.json`,
`/tmp/openthread-landing-{1440,390,320}.png` and
`/tmp/openthread-chat-{1440,390,320}.png`. Browser chat traffic was intercepted
inside the test browser; no fabricated token was sent to the protected backend.
No real login, authenticated HTTP round trip or Foundry inference is claimed.

Added jsdom as a development dependency for React regression tests; no general
upgrade was performed. `npm audit` reports two moderate advisories in the
existing Vitest/mocker dependency chain. This execution uses `vitest run`, not
its server/UI. No runtime dependency is reported affected; dependency upgrade
is deferred rather than running a forced major upgrade. Result is recorded in
`/tmp/openthread-npm-audit.json`.

## Files changed in this local review

- `backend/app/foundry.py`, `backend/tests/test_foundry.py`.
- `frontend/src/App.tsx`, `frontend/src/api.ts`, `frontend/src/main.tsx`.
- `frontend/src/auth/AuthGate.tsx`, `frontend/src/auth/AuthProvider.tsx`.
- `frontend/src/chat/ChatComposer.tsx`, `ChatPage.tsx`, `ChatSidebar.tsx`,
  `chat.css`, `types.ts`.
- `frontend/tests/api.test.ts`, `auth.test.tsx`, `chat.test.tsx`.
- `frontend/package.json`, `frontend/package-lock.json`.
- `README.md`, `infra/foundry.README.md`, this progress record.

The isolated smoke-test servers on ports 8107 and 5187 were stopped after
validation; only processes started by this review were interrupted.

All pre-existing migration/infrastructure changes and the two local commits
beyond the remote remain. Secret environment files were not edited and are
confirmed ignored by Git. No pipeline, Dockerfile or Bicep definition was edited.

## Remaining limits and next action

Local objective complete; no relevant functional defect remains open in this
review. Real Foundry validation still requires resolution of the historical
quota blocker, creation of the approved destination and secure configuration in
an independently authorized external execution. Real browser → Entra → API
validation requires a genuine user sign-in. Docker build requires accessible
Docker Desktop/daemon. These were not simulated as successful external results.

Requested scheduled resume remains **not registered**; no native callable
scheduler with this thread/project destination was available. No account usage
percentage could be read, so an exact 98% cutoff is not promised.

Next concrete action: in an authorized external session, resolve Foundry quota
and validate one short authenticated chat using the documented local commands.
If a later run resumes this completed local objective without new evidence or
scope, stop without inventing work. No Azure query/change, key retrieval,
inference, commit, push, merge, deployment or pipeline run occurred here.
