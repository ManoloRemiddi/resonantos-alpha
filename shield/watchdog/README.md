# OpenClaw Watchdog — Cross-Node Health Monitoring

> **AI agents that look after each other.**

When you have two machines running OpenClaw — one orchestrator and one node — the node can monitor the orchestrator's health and automatically restart it if it goes down.

## What It Does

1. **Diagnoses** — 9 health sensors check WHY something is wrong, not just IF
2. **Recovers** — Automatically restarts the gateway service (up to 3 attempts)
3. **Alerts** — Sends a Telegram message when automatic recovery fails

## How It Works

```
Node Machine (watchdog)          Orchestrator (monitored)
┌──────────────────────┐         ┌──────────────────────┐
│  Scheduled task      │  SSH    │  watchdog-handler.sh  │
│  every 5 minutes     │───────→│  (forced command)     │
│                      │        │         │              │
│  watchdog-client     │        │  health-sensors.sh    │
│  (PS1 or bash)       │        │  (9 diagnostic checks)│
│                      │        │         │              │
│  ← JSON report ──────│←───────│  {"overall":"ok",...}  │
│                      │        │                        │
│  If critical:        │  SSH   │  restart-gateway      │
│  restart command ────│───────→│  (launchctl)          │
│                      │        │                        │
│  If restart fails:   │        │                        │
│  Telegram alert ─────│──→ 📱  │                        │
└──────────────────────┘        └──────────────────────┘
```

## Security

The watchdog SSH key is maximally restricted:

- **`restrict`** — disables all forwarding, PTY, agent relay
- **`command=`** — can ONLY execute the handler script
- **`from=`** — works ONLY from the node's IP
- **Dedicated user** — no shell, no access to your files
- **Scoped sudo** — can ONLY restart OpenClaw services

**Blast radius of full node compromise:** attacker can restart your OpenClaw gateway. Nothing else.

## Health Sensors

| Sensor | What | Diagnoses |
|--------|------|-----------|
| gateway_process | Is the process running? | Crash vs hang |
| gateway_http | Does the API respond? | Port conflict vs timeout |
| launchagent | Is the service registered? | Missing vs crashed |
| disk_space | Available storage | GB remaining + percentage |
| memory | System memory pressure | Pressure level + free % |
| network | Internet connectivity | DNS vs HTTPS vs firewall |
| node_tunnel | Is the node connected? | Reachable vs tunnel down |
| openclaw_config | Config file validity | Valid JSON or corrupted |
| extensions | Extension syntax | Which extension is broken |

## Quick Start

See [SETUP.md](./SETUP.md) for step-by-step instructions.

**Requirements:**
- Two machines with OpenClaw installed
- SSH access between them (direct Ethernet recommended)
- macOS orchestrator (Linux support: adapt launchctl to systemd)
- Windows or Linux node (PowerShell or bash client)

## Adapting for Your Setup

### Linux Orchestrator
Replace `launchctl` commands in `watchdog-handler.sh` with:
```bash
systemctl --user restart openclaw-gateway
```

### Linux Node (instead of Windows)
Use a bash version of the client with `cron` instead of Scheduled Tasks.

### Different Network
Change `from="10.0.0.2"` in the authorized_keys to your node's IP.

## Philosophy

This is deterministic infrastructure, not AI. Zero tokens, zero model calls, zero hallucination risk. The watchdog is a bash script and a cron job — the same tools sysadmins have used for decades.

AI enters the picture only after the watchdog reports what's wrong. The human (or orchestrator AI) decides what to do with that information.
