#!/usr/bin/env bash

set -euo pipefail

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

REPORT_FILE="/tmp/recovery-audit-$(date +%Y%m%d-%H%M%S).txt"
PASS_COUNT=0
FAIL_COUNT=0

log_line() {
    printf '%s\n' "$1" | tee -a "$REPORT_FILE"
}

pass() {
    PASS_COUNT=$((PASS_COUNT + 1))
    log_line "✅ PASS $1"
}

fail() {
    FAIL_COUNT=$((FAIL_COUNT + 1))
    log_line "❌ FAIL $1"
}

launchctl_output="$(launchctl list 2>/dev/null || true)"

check_launchagent() {
    local label="$1"
    local line

    line="$(printf '%s\n' "$launchctl_output" | awk -v target="$label" 'NR > 1 && $3 == target {print $0; exit}')"
    if [ -n "$line" ]; then
        pass "LaunchAgent ${label}: ${line}"
    else
        fail "LaunchAgent ${label}: not found in launchctl list"
    fi
}

check_launchagent "ai.openclaw.gateway"
check_launchagent "com.resonantos.dashboard"
check_launchagent "com.resonantos.shield"
check_launchagent "com.resonantos.logician"
check_launchagent "com.resonantos.watchdog"
check_launchagent "com.resonantos.watchdog-health"
check_launchagent "com.resonantos.logician-proxy" # com.openclaw.mangle-server

if curl -sf "http://127.0.0.1:19100/" >/dev/null; then
    pass "Dashboard HTTP 200: http://localhost:19100/"
else
    fail "Dashboard HTTP 200: http://localhost:19100/ did not return 200"
fi

if dashboard_health="$(curl -sf "http://127.0.0.1:19100/api/system/health")"; then
    if dashboard_detail="$(
        printf '%s' "$dashboard_health" | python3 -c '
import json
import sys

payload = json.load(sys.stdin)
status = payload.get("status")
subsystems = payload.get("subsystems", {})
if status == "ok":
    print(f"status=ok subsystems={len(subsystems)}")
    raise SystemExit(0)
print(f"status={status!r}")
raise SystemExit(1)
'
    )"; then
        pass "Dashboard /api/system/health: ${dashboard_detail}"
    else
        fail "Dashboard /api/system/health: ${dashboard_detail}"
    fi
else
    fail "Dashboard /api/system/health: request failed"
fi

if shield_health="$(curl -sf "http://127.0.0.1:9999/health")"; then
    if shield_detail="$(
        printf '%s' "$shield_health" | python3 -c '
import json
import sys

payload = json.load(sys.stdin)
status = payload.get("status", "unknown")
service = payload.get("service", "unknown")
print(f"service={service} status={status}")
'
    )"; then
        pass "Shield health endpoint: ${shield_detail}"
    else
        pass "Shield health endpoint: responded on http://localhost:9999/health"
    fi
else
    fail "Shield health endpoint: http://localhost:9999/health did not respond"
fi

if [ -S "/tmp/mangle.sock" ]; then
    pass "Logician socket: /tmp/mangle.sock exists"
else
    fail "Logician socket: /tmp/mangle.sock missing"
fi

if logician_proxy="$(
    curl -sf "http://127.0.0.1:8081/query" \
        -H "Content-Type: application/json" \
        -d '{"query":"agent(/main)."}'
)"; then
    if logician_detail="$(
        printf '%s' "$logician_proxy" | python3 -c '
import json
import sys

payload = json.load(sys.stdin)
count = payload.get("count")
query = payload.get("query")
print(f"query={query} count={count}")
'
    )"; then
        pass "Logician proxy :8081: ${logician_detail}"
    else
        pass "Logician proxy :8081: responded"
    fi
else
    fail "Logician proxy :8081: no HTTP response"
fi

LCM_DB="${HOME}/.openclaw/lcm.db"
if [ -f "$LCM_DB" ]; then
    lcm_size="$(stat -f%z "$LCM_DB" 2>/dev/null || wc -c < "$LCM_DB")"
    pass "LCM database: ${LCM_DB} exists (${lcm_size} bytes)"
else
    fail "LCM database: ${LCM_DB} missing"
fi

if tm_detail="$(
    defaults export /Library/Preferences/com.apple.TimeMachine - 2>/dev/null | python3 -c '
import plistlib
import sys

payload = plistlib.loads(sys.stdin.buffer.read())
destinations = payload.get("Destinations", [])
latest = None
latest_volume = None

for destination in destinations:
    snapshots = destination.get("SnapshotDates", [])
    if snapshots:
        candidate = max(snapshots)
        if latest is None or candidate > latest:
            latest = candidate
            latest_volume = destination.get("LastKnownVolumeName", "unknown")

if latest is None:
    print("no snapshots recorded")
    raise SystemExit(1)

stamp = latest.isoformat().replace("+00:00", "Z")
print(f"volume={latest_volume} latest_snapshot={stamp}")
'
)"; then
    pass "Time Machine backups: ${tm_detail}"
else
    fail "Time Machine backups: unable to confirm snapshots"
fi

if backblaze_detail="$(
    python3 -c '
import glob
import os
import xml.etree.ElementTree as ET

last_backup_file = "/Library/Backblaze.bzpkg/bzdata/bzreports/bzstat_lastbackupcompleted.xml"
last_transmit_file = "/Library/Backblaze.bzpkg/bzdata/bzlogs/bzreports_lastfilestransmitted/bzstat_lastfile_transmitted.xml"
done_files = sorted(glob.glob("/Library/Backblaze.bzpkg/bzdata/bzbackup/bzdatacenter/bz_done_*.dat"))

if not os.path.exists(last_backup_file):
    print("missing bzstat_lastbackupcompleted.xml")
    raise SystemExit(1)

backup_root = ET.parse(last_backup_file).getroot()
backup_node = backup_root.find("lastbackupcompleted")
backup_dt = backup_node.attrib.get("localdatetime", "unknown") if backup_node is not None else "unknown"
backup_ms = int(backup_node.attrib.get("gmt_millis", "0")) if backup_node is not None else 0

transmit_dt = "unknown"
if os.path.exists(last_transmit_file):
    transmit_root = ET.parse(last_transmit_file).getroot()
    transmit_node = transmit_root.find("lastfile_transmitted")
    if transmit_node is not None:
        transmit_dt = transmit_node.attrib.get("gmt_date", "unknown")

if backup_ms <= 0 and not done_files:
    print("no completed Backblaze backup markers found")
    raise SystemExit(1)

detail = f"last_backup={backup_dt}"
if transmit_dt != "unknown":
    detail += f" last_file={transmit_dt}"
if done_files:
    detail += f" done_markers={len(done_files)}"
print(detail)
'
)"; then
    pass "Backblaze backups: ${backblaze_detail}"
else
    fail "Backblaze backups: unable to confirm completed backup markers"
fi

git_status="$(git -C "$(pwd)" status --porcelain 2>/dev/null || true)"
if [ -z "$git_status" ]; then
    pass "Git repo clean: no uncommitted changes"
else
    fail "Git repo clean: uncommitted changes present"
fi

if cron_detail="$(
    openclaw cron list --all --json 2>/dev/null | python3 -c '
import json
import sys

raw = sys.stdin.read()
start = raw.find("{")
if start == -1:
    print("no JSON payload returned")
    raise SystemExit(1)

payload = json.loads(raw[start:])
jobs = payload.get("jobs", [])
errors = 0
for job in jobs:
    state = job.get("state", {})
    if state.get("consecutiveErrors", 0) > 0 or state.get("lastStatus") == "error" or state.get("lastRunStatus") == "error":
        errors += 1

print(f"jobs={len(jobs)} errors={errors}")
raise SystemExit(0 if errors == 0 else 1)
'
)"; then
    pass "Cron health: ${cron_detail}"
else
    fail "Cron health: ${cron_detail:-unable to inspect cron jobs}"
fi

if gateway_status="$(openclaw gateway status 2>/dev/null)"; then
    runtime_line="$(printf '%s\n' "$gateway_status" | grep -F "Runtime:" | head -1 || true)"
    probe_line="$(printf '%s\n' "$gateway_status" | grep -F "RPC probe:" | head -1 || true)"
    if printf '%s\n' "$gateway_status" | grep -Fq "Runtime: running" && printf '%s\n' "$gateway_status" | grep -Fq "RPC probe: ok"; then
        pass "OpenClaw gateway running: ${runtime_line}; ${probe_line}"
    else
        fail "OpenClaw gateway running: ${runtime_line:-runtime unknown}; ${probe_line:-probe unknown}"
    fi
else
    fail "OpenClaw gateway running: openclaw gateway status failed"
fi

log_line "Summary: ${PASS_COUNT} passed, ${FAIL_COUNT} failed"
log_line "Report: ${REPORT_FILE}"

if [ "$FAIL_COUNT" -eq 0 ]; then
    exit 0
fi

exit 1
