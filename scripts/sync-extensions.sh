#!/bin/bash
# sync-extensions.sh — Sync repo extensions to OpenClaw runtime
# Single source of truth: repo/extensions/ -> ~/.openclaw/extensions/
# Run after any extension code change.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$SCRIPT_DIR/.." && pwd)/extensions"
LIVE="$HOME/.openclaw/extensions"

EXTENSIONS=(shield-gate coherence-gate r-awareness usage-tracker heuristic-auditor)

changed=0
for name in "${EXTENSIONS[@]}"; do
  src="$REPO/$name/index.js"
  dst="$LIVE/$name/index.js"

  if [ ! -f "$src" ]; then
    echo "  WARN $name: no repo source"
    continue
  fi

  if [ ! -f "$dst" ]; then
    echo "  WARN $name: no live target"
    continue
  fi

  if diff -q "$src" "$dst" > /dev/null 2>&1; then
    echo "  OK $name: in sync"
  else
    cp "$src" "$dst"
    echo "  UPDATED $name"
    changed=$((changed + 1))
  fi

  # Also sync supporting files
  for f in "$REPO/$name"/*.json; do
    [ -f "$f" ] || continue
    fname=$(basename "$f")
    if [ -f "$LIVE/$name/$fname" ]; then
      if ! diff -q "$f" "$LIVE/$name/$fname" > /dev/null 2>&1; then
        cp "$f" "$LIVE/$name/$fname"
        echo "  UPDATED $name/$fname"
        changed=$((changed + 1))
      fi
    fi
  done
done

echo ""
if [ "$changed" -gt 0 ]; then
  echo "$changed file(s) updated. Restart gateway to apply: openclaw gateway restart"
else
  echo "All extensions in sync. No restart needed."
fi
