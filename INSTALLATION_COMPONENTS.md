# ResonantOS Installation Components

> What gets installed when someone runs the ResonantOS installer

## Overview

ResonantOS is a sovereign AI operating system built on OpenClaw/Clawdbot. The installer sets up:
1. Multi-agent constellation
2. Symbiotic Shield (security)
3. Dashboard (command center)
4. Core protocols and configuration

---

## 1. Multi-Agent Constellation

### Core Agents

| Agent | Model | Purpose |
|-------|-------|---------|
| **Strategist** | claude-opus-4-5 | Main orchestrator, works with user on ideas, delegates work |
| **Coder** | claude-opus-4-5 | Technical implementation, builds features |
| **Designer** | claude-sonnet-4-5 | Visual design, UI mockups |
| **Researcher** | claude-haiku-4-5 | Information gathering, web research |
| **Acupuncturist** | claude-opus-4-5 | Finds ONE leverage point for systemic problems |
| **Blindspot** | claude-sonnet-4-5 | Challenges assumptions, finds failure modes |
| **Tester** | claude-sonnet-4-5 | Verification and testing |

### Agent Configuration

Each agent needs:
- `workspace/` — working directory with AGENTS.md
- `agentDir/` — Clawdbot agent directory
- Entry in `clawdbot.json` agents list
- Appropriate model assignment

### Agent Workspaces Structure

```
~/clawd/agents/
├── strategist/
│   └── AGENTS.md          # Orchestrator prompt + protocols
├── coder/
│   └── AGENTS.md          # Coding-focused prompt
├── designer/
│   └── AGENTS.md          # Design-focused prompt
├── researcher/
│   └── AGENTS.md          # Research-focused prompt
├── acupuncturist/
│   └── AGENTS.md          # Systemic Architect prompt
└── ...
```

---

## 2. Symbiotic Shield

### Components

| Component | File | Purpose |
|-----------|------|---------|
| Scanner | `scanner.py` | Detects 55+ injection patterns |
| Classifier | `classifier.py` | Data sensitivity (PUBLIC → SECRET) |
| A2A Monitor | `a2a_monitor.py` | Agent-to-agent security |
| Vigil Layer | `vigil_layer.py` | YARA + embedding detection |
| Daemon | `daemon.py` | 24/7 background service |

### Shield Installation

```bash
# Location
~/clawd/security/shield/

# Dependencies
pip install yara-python pyyaml

# Jailbreak database (submodule)
git clone https://github.com/verazuo/jailbreak_llms.git

# Install launchd service
./shield_ctl.sh install

# Start daemon
./shield_ctl.sh start

# Verify
curl http://127.0.0.1:9999/health
```

### Shield Configuration

`config.yaml`:
```yaml
intervention_mode: warn  # monitor | warn | block
sensitivity_threshold: 50
enable_scanner: true
enable_classifier: true
enable_a2a_monitor: true
enable_vigil: true
```

### Automatic Startup

LaunchAgent at `~/Library/LaunchAgents/com.resonantos.shield.plist`:
- RunAtLoad: true
- KeepAlive: true

---

## 3. Dashboard

### Location
`~/clawd/projects/resonantos-v3/dashboard/`

### Components
- `server.py` — Flask API server
- `templates/` — UI templates
- `static/` — CSS, JS assets

### Features
- Agent activity monitor
- Shield status indicator (top-left)
- Token usage tracking
- Task management

### Running
```bash
cd ~/clawd/projects/resonantos-v3/dashboard
python3 server.py
# Access at http://localhost:19100
```

---

## 4. Core Files

### User Customizable

| File | Purpose |
|------|---------|
| `IDENTITY.md` | Agent name, emoji, avatar |
| `USER.md` | Human's profile |
| `SOUL.md` | Agent personality and values |
| `MEMORY.md` | Long-term curated memories |
| `TOOLS.md` | Environment-specific notes |

### System Files

| File | Purpose |
|------|---------|
| `AGENTS.md` | Protocols, behaviors, rules |
| `HEARTBEAT.md` | Periodic check tasks |
| `memory/YYYY-MM-DD.md` | Daily logs |

---

## 5. Cron Jobs

| Job | Schedule | Purpose |
|-----|----------|---------|
| shield-daily-check | 6:00 AM | Run Shield tests, check alerts |
| todo-sync | 6:00 AM | Morning TODO sync |
| guardian-health | Sunday 2:00 AM | Weekly system health |
| archivist-docs | Tue/Fri 3:00 AM | Documentation updates |

---

## 6. Installer Checklist

### Phase 1: Base Installation
- [ ] Install Clawdbot
- [ ] Install Solana CLI (`sh -c "$(curl -sSfL https://release.anza.xyz/stable/install)"`)
- [ ] Configure API keys (Anthropic, etc.)
- [ ] Set up workspace directory structure

### Phase 2: Agent Setup
- [ ] Create agent workspaces with AGENTS.md files
- [ ] Add agents to clawdbot.json
- [ ] Configure models per agent

### Phase 3: Security
- [ ] Install Shield dependencies
- [ ] Clone jailbreak_llms database
- [ ] Create Shield launchd service
- [ ] Start Shield daemon
- [ ] Verify health endpoint

### Phase 4: Dashboard
- [ ] Install dashboard dependencies
- [ ] Configure dashboard
- [ ] Create dashboard launchd service (optional)

### Phase 5: Cron Jobs
- [ ] Set up daily Shield check
- [ ] Set up morning TODO sync
- [ ] Set up weekly health check

### Phase 6: Customization
- [ ] User fills in IDENTITY.md
- [ ] User fills in USER.md
- [ ] User customizes SOUL.md

---

## 7. Directory Structure (Final)

```
~/clawd/
├── AGENTS.md                    # Main protocols
├── IDENTITY.md                  # Agent identity
├── USER.md                      # Human profile
├── SOUL.md                      # Agent personality
├── MEMORY.md                    # Long-term memory
├── TOOLS.md                     # Environment notes
├── HEARTBEAT.md                 # Periodic tasks
├── memory/                      # Daily logs
│   └── YYYY-MM-DD.md
├── agents/                      # Agent workspaces
│   ├── strategist/
│   ├── coder/
│   ├── designer/
│   ├── researcher/
│   ├── acupuncturist/
│   └── ...
├── security/
│   ├── shield/                  # Symbiotic Shield
│   │   ├── daemon.py
│   │   ├── shield_ctl.sh
│   │   ├── scanner.py
│   │   ├── classifier.py
│   │   ├── a2a_monitor.py
│   │   ├── vigil_layer.py
│   │   ├── config.yaml
│   │   ├── jailbreak_llms/      # Attack database
│   │   └── tests/
│   ├── alerts/
│   └── logs/
└── projects/
    └── resonantos-v3/
        └── dashboard/           # Command center
```

---

## Version

- **ResonantOS:** v3.0
- **Shield:** v1.0
- **Dashboard:** v3.0
- **Document updated:** 2026-02-03
