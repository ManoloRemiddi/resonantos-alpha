#!/usr/bin/env bash
# Memory Doorman - watches memory dirs, sanitizes new/modified .md files
# Runs as LaunchAgent. Uses fswatch for filesystem monitoring.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SANITIZER="$SCRIPT_DIR/sanitize-memory-write.py"
LOG="/tmp/memory-doorman.log"

WATCH_DIRS=(
  "$HOME/.openclaw/workspace/memory/shared-log"
  "$HOME/.openclaw/workspace/memory"
)

if [[ ! -x "$SANITIZER" ]]; then
  echo "$(date -Iseconds) ERROR: Sanitizer not found at $SANITIZER" >> "$LOG"
  exit 1
fi

echo "$(date -Iseconds) Memory Doorman started. Watching: ${WATCH_DIRS[*]}" >> "$LOG"

/opt/homebrew/bin/fswatch --event Created --event Updated \
  -r \
  --include '\.md$' \
  --exclude '.*' \
  "${WATCH_DIRS[@]}" | while read -r filepath; do

  [[ -f "$filepath" ]] || continue
  [[ "$filepath" == *.md ]] || continue
  [[ "$(basename "$filepath")" == "0000-PREAMBLE.md" ]] && continue

  stats=$(python3 "$SANITIZER" --dry-run "$filepath" 2>&1)

  if [[ -n "$stats" ]]; then
    echo "$(date -Iseconds) SANITIZING $filepath -- $stats" >> "$LOG"
    python3 "$SANITIZER" "$filepath"
    echo "$(date -Iseconds) CLEANED $filepath" >> "$LOG"
  fi

done
