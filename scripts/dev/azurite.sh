#!/usr/bin/env bash
set -euo pipefail
# Official Azurite fallback when the project Docker wrapper cannot find its CLI.
npm exec --yes --package azurite@3.35.0 -- azurite \
  --location "${OPENTHREAD_AZURITE_DIRECTORY:-.local/azurite}" \
  --blobHost 127.0.0.1 --queueHost 127.0.0.1 --tableHost 127.0.0.1 \
  --skipApiVersionCheck --silent
