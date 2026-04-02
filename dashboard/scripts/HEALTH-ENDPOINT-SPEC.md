# /api/system/health Endpoint Specification

Add to routes/system.py. Single endpoint returning composite health for ALL subsystems.

## Response Shape
```json
{
  "status": "ok|degraded|warning",
  "subsystems": {
    "dashboard": {"status": "ok", "version": "0.6.0"},
    "shield": {"status": "ok", "uptime_s": 1296000, ...},
    "logician": {"status": "ok", "socket": true},
    "gateway": {"status": "ok", "connected": true, "connId": "..."},
    "lcm": {"status": "ok", "messages": 36870, "summaries": 736},
    "cron": {"status": "ok|degraded", "total": 27, "errors": 0},
    "disk": {"status": "ok", "free_gb": 45.2}
  }
}
```

## Logic
- Dashboard: always ok + version from _get_version() (import from server_v2)
- Shield: urllib to localhost:9999/health, timeout 2s
- Logician: check os.path.exists("/tmp/mangle.sock")
- Gateway: use gw.connected and gw.conn_id from shared
- LCM: sqlite3 connect to LCM_DB, count messages + summaries tables
- Cron: subprocess openclaw cron list --json, count errors
- Disk: os.statvfs, warn if < 5GB free
- Overall: all ok = ok, any error = degraded, else warning

## Imports needed
subprocess, sqlite3, os, json already available in system.py
Need: from server_v2 import _get_version (or inline)
