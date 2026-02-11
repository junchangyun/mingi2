#!/usr/bin/env bash
set -euo pipefail

INTERVAL_SECONDS=${INTERVAL_SECONDS:-5}
COMMIT_PREFIX=${COMMIT_PREFIX:-"auto: update"}

# Simple polling watcher: commit+push when there are changes.
while true; do
  if [[ -n "$(git status --porcelain)" ]]; then
    ts=$(date '+%Y-%m-%d %H:%M:%S')
    git add -A
    # Avoid empty commit if changes disappear between status and add.
    if ! git diff --cached --quiet; then
      git commit -m "${COMMIT_PREFIX} ${ts}" >/dev/null
      git push >/dev/null
      echo "[auto] pushed at ${ts}"
    fi
  fi
  sleep "${INTERVAL_SECONDS}"
done
