# LEGACY / HISTORICAL / NOT CURRENT ARCHITECTURE

## A. Currently used

React chat/auth/landing components, FastAPI chat/workspace/runtime routers,
ConversationStore, ChatService, FoundryClient, Azure Storage adapters, Bicep and
CI/CD are the current Open Thread workload. See [architecture](architecture.md).

## B. Unused but harmless

The former release-intelligence experiment remains disconnected from the current
entrypoint and API. Retained files include frontend overview/release/investigator/
collections pages, the legacy AuthenticatedShell, mockReleaseData/releaseTypes,
backend domain/release_evidence.py and services/detection.py, and their tests.
These are historical code, not current product or cloud monitoring capabilities.
No large source deletion was performed. Negative Foundry tests rejecting old
provider headers remain valid regression coverage.

## C. Removed from current product guidance

The release-intelligence product direction is archived at
[archive/product-direction.md](archive/product-direction.md). Historical naming
and overnight reports are explicitly labeled. Stale persistence/deployment claims
in current docs and the landing were corrected. No current provider abstraction
or OpenCode Go integration exists; previous versions remain in Git history.
