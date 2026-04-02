#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SSOT_ROOT="$REPO_ROOT/ssot"
LOG_FILE="$REPO_ROOT/shield/logs/ssot-staleness.json"

mkdir -p "$(dirname "$LOG_FILE")"

python3 - "$SSOT_ROOT" "$LOG_FILE" <<'PY'
import json
import os
import re
import sys
from datetime import datetime, timezone

ssot_root = sys.argv[1]
log_file = sys.argv[2]
now = datetime.now(timezone.utc)
date_patterns = [
    re.compile(r"Updated:\s*(\d{4}-\d{2}-\d{2})"),
    re.compile(r"\|\s*Updated\s*\|\s*(\d{4}-\d{2}-\d{2})\s*\|"),
]

files = []
for level in ("L0", "L1"):
    root = os.path.join(ssot_root, level)
    for dirpath, _, filenames in os.walk(root):
        for name in filenames:
            if name.endswith(".ai.md"):
                files.append(os.path.join(dirpath, name))

files.sort()
stale_files = []

for file_path in files:
    with open(file_path, "r", encoding="utf-8") as handle:
        header = "".join(handle.readlines()[:5])

    updated = None
    for pattern in date_patterns:
        match = pattern.search(header)
        if match:
            updated = match.group(1)
            break

    rel_path = os.path.relpath(file_path, ssot_root).replace(os.sep, "/")

    if updated is None:
      stale_files.append({
          "path": rel_path,
          "updated": None,
          "days_old": None,
          "reason": "missing_updated_header",
      })
      continue

    updated_dt = datetime.strptime(updated, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    days_old = (now.date() - updated_dt.date()).days
    if days_old > 14:
        stale_files.append({
            "path": rel_path,
            "updated": updated,
            "days_old": days_old,
        })

payload = {
    "checked_at": now.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    "total_files": len(files),
    "stale_files": stale_files,
    "fresh_files": len(files) - len(stale_files),
}

with open(log_file, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2)
    handle.write("\n")

sys.exit(1 if stale_files else 0)
PY
