#!/bin/bash
set -euo pipefail

SOURCE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_REPO="${1:-$(pwd)}"
SOURCE_HOOK="$SOURCE_ROOT/.git/hooks/pre-push"
TARGET_HOOK="$TARGET_REPO/.git/hooks/pre-push"

if [ ! -f "$SOURCE_HOOK" ]; then
  echo "[Shield] Source hook not found: $SOURCE_HOOK" >&2
  exit 1
fi

if [ ! -d "$TARGET_REPO/.git/hooks" ]; then
  echo "[Shield] Target repo does not look like a git repo: $TARGET_REPO" >&2
  exit 1
fi

cp "$SOURCE_HOOK" "$TARGET_HOOK"
chmod +x "$TARGET_HOOK"

echo "[Shield] Installed pre-push hook to $TARGET_HOOK"
