#!/bin/bash
# Hook Guardian — Monitors pre-push hooks for tampering.
# Runs via launchd every 30 seconds.
# If hooks are missing/modified, restores them and logs the event.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SHIELD_DIR="$REPO_ROOT/shield"
LOG_DIR="$SHIELD_DIR/alerts"
LOG_FILE="$LOG_DIR/hook_guardian.log"
HOOK_SIGNATURE="Shield Pre-Push Gate"

REPOS=(
    "$REPO_ROOT"
)

mkdir -p "$LOG_DIR"

for repo in "${REPOS[@]}"; do
    hook="$repo/.git/hooks/pre-push"
    repo_shield_dir="$repo/shield"
    hook_content=$(cat <<EOF
#!/bin/bash
# Shield Pre-Push Gate — DO NOT REMOVE
# This hook is monitored. Deletion triggers auto-restore + alert.

SHIELD_DIR="$repo_shield_dir"
SCANNER="\$SHIELD_DIR/data_leak_scanner.py"
LOCK="\$SHIELD_DIR/shield_lock.py"

python3 "\$LOCK" verify 2>/dev/null
if [ \$? -eq 1 ]; then
    echo "[Shield] 🔓 Gate unlocked by human — push allowed"
    exit 0
fi

echo "[Shield] 🔒 Running pre-push scan..."
python3 "\$SCANNER" pre-push "\$(git rev-parse --show-toplevel)"
exit \$?
EOF
)
    
    if [ ! -f "$hook" ]; then
        echo "$(date -u +%FT%TZ) ALERT: Hook missing at $hook — RESTORING" >> "$LOG_FILE"
        printf '%s\n' "$hook_content" > "$hook"
        chmod +x "$hook"
        echo "$(date -u +%FT%TZ) RESTORED: $hook" >> "$LOG_FILE"
    elif ! grep -q "$HOOK_SIGNATURE" "$hook" 2>/dev/null; then
        echo "$(date -u +%FT%TZ) ALERT: Hook tampered at $hook — RESTORING" >> "$LOG_FILE"
        cp "$hook" "${hook}.tampered.$(date +%s)"
        printf '%s\n' "$hook_content" > "$hook"
        chmod +x "$hook"
        echo "$(date -u +%FT%TZ) RESTORED (tampered copy saved): $hook" >> "$LOG_FILE"
    fi
done
