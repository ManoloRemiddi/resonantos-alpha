#!/bin/bash
# Logician Health Monitor — deterministic, no AI
# Checks unix socket health via test query
# Run via launchd every 60s

set -euo pipefail

SOCK="/tmp/mangle.sock"
LOG="$HOME/resonantos-alpha/logician/logs/monitor.log"
PLIST="com.resonantos.logician"
STATUS_FILE="$HOME/resonantos-alpha/logician/monitor/status.json"

mkdir -p "$(dirname "$LOG")" "$(dirname "$STATUS_FILE")"

ts() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }

# 1. Socket file check
if [ ! -S "$SOCK" ]; then
    echo "$(ts) FAIL: socket $SOCK missing — restarting" >> "$LOG"
    launchctl kickstart -k "gui/$(id -u)/$PLIST" 2>/dev/null || true
    sleep 3
    if [ ! -S "$SOCK" ]; then
        echo "$(ts) CRITICAL: restart failed" >> "$LOG"
        printf '{"status":"down","lastCheck":"%s","lastError":"restart failed"}\n' "$(ts)" > "$STATUS_FILE"
        exit 1
    fi
    echo "$(ts) RECOVERED after restart" >> "$LOG"
fi

# 2. gRPC query check via Node.js (lightweight — single fact query)
RESULT=$(node -e "
const grpc = require('@grpc/grpc-js');
const protoLoader = require('@grpc/proto-loader');
const pd = protoLoader.loadSync(process.env.HOME + '/resonantos-alpha/logician/poc/mangle-service/proto/mangle.proto', { keepCase: true, longs: String, enums: String, defaults: true, oneofs: true });
const proto = grpc.loadPackageDefinition(pd).mangle;
const client = new proto.Mangle('unix://$SOCK', grpc.credentials.createInsecure());
const call = client.Query({ query: 'agent(/main)' });
const r = [];
call.on('data', d => r.push(d.answer));
call.on('end', () => { console.log(JSON.stringify(r)); process.exit(0); });
call.on('error', () => { console.log('ERROR'); process.exit(1); });
setTimeout(() => { console.log('TIMEOUT'); process.exit(1); }, 3000);
" 2>&1) || true

if echo "$RESULT" | grep -q 'agent(/main)'; then
    printf '{"status":"healthy","lastCheck":"%s","lastQuery":"agent(/main)","ok":true}\n' "$(ts)" > "$STATUS_FILE"
else
    echo "$(ts) WARN: gRPC query failed: $RESULT" >> "$LOG"
    printf '{"status":"degraded","lastCheck":"%s","lastError":"query failed"}\n' "$(ts)" > "$STATUS_FILE"
fi
