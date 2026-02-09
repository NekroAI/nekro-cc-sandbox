#!/usr/bin/env bash
set -euo pipefail

WORKSPACE_ROOT="${WORKSPACE_ROOT:-/home/appuser/workspaces}"

mkdir -p "${WORKSPACE_ROOT}"

if ! runuser -u appuser -- test -w "${WORKSPACE_ROOT}" 2>/dev/null; then
  echo "[entrypoint] WORKSPACE_ROOT is not writable for appuser: ${WORKSPACE_ROOT}" >&2
  echo "[entrypoint] trying to fix permissions by chown to appuser..." >&2
  if ! chown -R appuser:appuser "${WORKSPACE_ROOT}"; then
    echo "[entrypoint] chown failed; cannot fix permissions automatically." >&2
  fi
fi

if ! runuser -u appuser -- test -w "${WORKSPACE_ROOT}" 2>/dev/null; then
  echo "[entrypoint] still not writable for appuser after chown: ${WORKSPACE_ROOT}" >&2
  echo "[entrypoint] please mount a writable directory or volume to WORKSPACE_ROOT." >&2
  exit 1
fi

exec runuser -u appuser -- uv run python -m nekro_cc_sandbox.main

