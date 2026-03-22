#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
REPO_ROOT=$(git -C "$SCRIPT_DIR/.." rev-parse --show-toplevel 2>/dev/null || true)

if [ -z "$REPO_ROOT" ]; then
  echo "Could not determine repo root for Shield pre-push hook." >&2
  exit 1
fi

python3 "$SCRIPT_DIR/file_guard.py" install-hook "$REPO_ROOT"
