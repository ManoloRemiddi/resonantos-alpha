#!/bin/bash
# Logician Health Monitor — deterministic, no AI
# Linux-safe: uses the repo-managed control script for health/restart.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
CTL="$REPO_ROOT/logician/scripts/logician_ctl.sh"
LOG="$REPO_ROOT/logician/logs/monitor.log"
STATUS_FILE="$REPO_ROOT/logician/monitor/status.json"

mkdir -p "$(dirname "$LOG")" "$(dirname "$STATUS_FILE")"

ts() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }
write_status() {
  printf '%s\n' "$1" > "$STATUS_FILE"
}

if "$CTL" health >/tmp/logician-monitor-health.out 2>&1; then
  write_status "{\"status\":\"healthy\",\"lastCheck\":\"$(ts)\",\"ok\":true,\"source\":\"monitor\"}"
  exit 0
fi

echo "$(ts) WARN: health check failed — attempting restart" >> "$LOG"
cat /tmp/logician-monitor-health.out >> "$LOG" 2>/dev/null || true

if "$CTL" restart >/tmp/logician-monitor-restart.out 2>&1; then
  sleep 2
  if "$CTL" health >/tmp/logician-monitor-health.out 2>&1; then
    echo "$(ts) RECOVERED: restart succeeded" >> "$LOG"
    write_status "{\"status\":\"healthy\",\"lastCheck\":\"$(ts)\",\"ok\":true,\"source\":\"monitor-restart\"}"
    exit 0
  fi
fi

echo "$(ts) CRITICAL: restart failed" >> "$LOG"
cat /tmp/logician-monitor-restart.out >> "$LOG" 2>/dev/null || true
cat /tmp/logician-monitor-health.out >> "$LOG" 2>/dev/null || true
write_status "{\"status\":\"down\",\"lastCheck\":\"$(ts)\",\"ok\":false,\"source\":\"monitor\",\"lastError\":\"restart failed\"}"
exit 1
