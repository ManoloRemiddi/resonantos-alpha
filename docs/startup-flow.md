# Startup Flow and Entrypoints — ResonantOS Alpha

**Purpose:** New contributors can understand what starts what, in what order, and on what ports — in 10 minutes.

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         USER MACHINE                                 │
│                                                                      │
│  ┌──────────────┐     ┌──────────────────┐     ┌────────────────┐ │
│  │  install.js  │────▶│   ~/.openclaw/   │◀────│  openclaw CLI  │ │
│  │  (Node.js)   │     │                  │     │                │ │
│  └──────────────┘     │  ├── agents/      │     └────────────────┘ │
│         │             │  ├── extensions/  │              │          │
│         │             │  ├── workspace/  │              │          │
│         │             │  └── openclaw.json│              │          │
│         ▼             └────────┬─────────┘              ▼          │
│  ┌──────────────┐              │          ┌─────────────────────┐  │
│  │ Dashboard    │              │          │   OpenClaw Gateway  │  │
│  │ (Flask/WS)  │              │          │   (Node.js)         │  │
│  │ port 19100  │              │          │   loads extensions   │  │
│  └──────┬───────┘              │          │   from extensions/  │  │
│         │                      │          └──────────┬──────────┘  │
│         │                      │                     │             │
└─────────┼──────────────────────┼─────────────────────┼─────────────┘
          │                      │                     │
          ▼                      ▼                     ▼
     HTTP requests          File reads           Extension hooks
     (browser)              ~/.openclaw/         (before_turn,
                                              after_turn, etc.)
```

---

## 1. Installation Flow

### Prerequisites

```
git clone https://github.com/ResonantOS/resonantos-alpha.git
cd resonantos-alpha
git checkout dev
node install.js
```

`install.js` validates dependencies, then copies files from the repo clone to `~/.openclaw/`.

### What Gets Installed Where

| Source (repo clone) | Destination (`~/.openclaw/`) |
|---------------------|------------------------------|
| `extensions/*.js` | `agents/main/agent/extensions/` |
| `agents/setup/` | `agents/setup/agent/` |
| `workspace-templates/*` | `workspace/` (if missing) |
| `ssot/templates/*` | `workspace/resonantos-alpha/ssot/` (if empty) |
| `skills/*` | `workspace/skills/` |
| Dashboard venv | `dashboard/venv/` (created) |
| Dashboard config | `dashboard/config.json` (from example, if missing) |

### Step-by-Step Installation

```
1. Preflight checks
   ├── git required
   ├── node >= 18 required
   ├── python3 + pip required
   └── openclaw installed globally (npm install -g openclaw) if missing

2. Extensions installed
   └── r-memory.js, r-awareness.js, gateway-lifecycle.js
       → ~/.openclaw/agents/main/agent/extensions/

3. SSoT documents
   └── Copied from ssot/templates/ to workspace/ if dir is empty
       (never overwrites existing docs)

4. Workspace templates
   └── AGENTS.md, SOUL.md, USER.md, IDENTITY.md, TOOLS.md,
       HEARTBEAT.md, MEMORY.md
       → ~/.openclaw/workspace/
       (only if file doesn't already exist)

5. R-Memory and R-Awareness configs
   └── ~/.openclaw/workspace/r-memory/config.json
       ~/.openclaw/workspace/r-awareness/config.json
       ~/.openclaw/workspace/r-awareness/keywords.json

6. Setup Agent
   └── agents/setup/ → ~/.openclaw/agents/setup/agent/
   └── Registered in openclaw.json agents list

7. Skills
   └── skills/* → ~/.openclaw/workspace/skills/

8. Dashboard dependencies
   └── Python venv created at dashboard/venv/
   └── pip install -r requirements.txt (flask, flask-cors, psutil, etc.)

9. Dashboard config
   └── dashboard/config.example.json → dashboard/config.json
       (only if config.json doesn't exist)
```

---

## 2. Startup Flow

### A. OpenClaw Gateway

```
openclaw gateway start
    │
    ▼
Loads ~/.openclaw/openclaw.json
    │
    ▼
Loads workspace rules from ~/.openclaw/workspace/
    (AGENTS.md, SOUL.md, USER.md, IDENTITY.md, TOOLS.md, etc.)
    │
    ▼
Registers extensions from ~/.openclaw/agents/main/agent/extensions/
    ├── r-memory.js       (before_turn, after_turn hooks)
    ├── r-awareness.js    (before_turn hook — SSOT document injection)
    └── gateway-lifecycle.js (after_turn hook — gateway maintenance)
    │
    ▼
Gateway listens for AI agent requests
(ports vary by platform — launchd on macOS, systemd on Linux, direct on Windows)
```

### B. Extensions Initialization

**r-memory.js** — Conversation compression
- Active on every turn
- Tracks token count; triggers compression at configurable threshold (default: 36,000)
- Compressed summaries written to `~/.openclaw/workspace/r-memory/`

**r-awareness.js** — SSOT document injection
- Injects relevant SSOT documents into each turn based on keywords
- Keywords map to SSOT hierarchy (L0/L1/L2)
- Config in `~/.openclaw/workspace/r-awareness/config.json`

**gateway-lifecycle.js** — Gateway maintenance
- Monitors task state
- Auto-resumes gateway after configurable delay if stopped
- Logs to `~/.openclaw/shield/logs/gateway-lifecycle.log`

### C. Dashboard server_v2.py

```
cd dashboard
source venv/bin/activate    # activates Python venv
python server_v2.py
    │
    ▼
Flask app starts on port 19100 (default)
    │
    ▼
Registers all route modules from dashboard/routes/
    ├── docs.py        (API: SSOT document serving)
    ├── memory.py      (API: r-memory operations)
    ├── projects.py    (API: GitHub Projects)
    ├── wallet.py      (API: Solana wallet)
    ├── system.py      (API: system info, restart)
    ├── bounty.py      (API: bounty board)
    └── profile.py     (API: user profile)
    │
    ▼
Dashboard at http://localhost:19100
```

---

## 3. Data Flow

```
User request (browser)
    │
    ▼
Dashboard (Flask) ────── HTTP ──────▶ serves pages/templates/static assets
    │                                        (no backend processing)
    ▼
OpenClaw Gateway (separate process)
    │
    ├── before_turn hooks run
    │   ├── r-awareness: injects SSOT docs
    │   └── (other extensions)
    │
    ▼
AI model processes turn
    │
    ├── after_turn hooks run
    │   ├── r-memory: updates conversation state / triggers compression
    │   ├── gateway-lifecycle: logs task state
    │   └── (other extensions)
    │
    ▼
Response returned to Dashboard → browser
```

---

## 4. Entrypoint Inventory

| Entrypoint | Command | Description |
|-----------|---------|-------------|
| **Installer** | `node install.js` | Installs/updates all components |
| **OpenClaw Gateway** | `openclaw gateway start` | Starts the AI agent gateway |
| **Dashboard** | `cd dashboard && source venv/bin/activate && python server_v2.py` | Starts Flask web UI on port 19100 |
| **Setup Agent** | `openclaw start --agent setup` | Onboarding configurator |
| **GitHub Project Agent** | `openclaw start --agent main` | Main AI agent with GitHub integration |
| **Dashboard Watchdog** | `bash dashboard/dashboard-watchdog.sh` | Monitors and restarts dashboard |
| **Shield Health Sensors** | `bash shield/watchdog/health-sensors.sh` | System health checks |

---

## 5. Config Sources

### Priority Order (highest to lowest)

```
1. Environment variables
   └── RESONANTOS_REPO_DIR, LOGICIAN_SOCK, OPENCLAW_HOME, etc.

2. ~/.openclaw/openclaw.json          (OpenClaw main config)
   └── agent definitions, model defaults, extension list

3. dashboard/config.json              (Dashboard config)
   └── Solana RPCs, token addresses, DAO config
   └── Loaded by Config class in shared/__init__.py

4. ~/.openclaw/workspace/
   ├── r-memory/config.json           (R-Memory compression params)
   ├── r-awareness/config.json         (R-Awareness injection rules)
   └── r-awareness/keywords.json       (Keyword → SSOT document map)

5. Repo clone (read-only reference)
   └── ssot/L0/, ssot/L1/, ssot/L2/   (installed to workspace by install.js)
```

### Key Paths

| Path | Description |
|------|-------------|
| `~/.openclaw/` | OpenClaw root directory |
| `~/.openclaw/workspace/` | Agent workspace, templates, memory, SSOT |
| `~/.openclaw/agents/` | Agent definitions (setup, main) |
| `~/.openclaw/extensions/` | Runtime copies of extensions |
| `~/.openclaw/openclaw.json` | OpenClaw main config |
| `~/resonantos-alpha/` | **Repo clone** (not installed — your working copy) |
| `dashboard/config.json` | Dashboard Solana/config |
| `dashboard/venv/` | Python virtual environment |

### Config Loading (Dashboard)

```python
# dashboard/shared/__init__.py
class Config:
    # Loads dashboard/config.json
    # Exposes get(key1, key2, ..., default=None)

from shared import Config, WORKSPACE, RMEMORY_DIR

cfg = Config()
solana_rpc = cfg.get("solana", "rpcs", "devnet", default="https://api.devnet.solana.com")
```

---

## 6. Log Locations

| Log | Location |
|-----|----------|
| Gateway lifecycle | `~/.openclaw/shield/logs/gateway-lifecycle.log` |
| Shield gate | `~/.openclaw/shield/logs/shield-gate.log` |
| R-Memory | `~/.openclaw/workspace/r-memory/r-memory.log` |
| R-Awareness | `~/.openclaw/workspace/r-awareness/r-awareness.log` |
| Dashboard (stdout) | Terminal where `python server_v2.py` was run |
| Dashboard (access) | `dashboard/dashboard.log` (if configured) |

---

## 7. Platform Differences

| Concern | macOS | Linux | Windows |
|---------|-------|-------|---------|
| Gateway management | `launchctl` (LaunchAgent) | `systemd` or direct `pkill` | Direct process |
| OpenClaw install | `npm install -g` | `npm install -g` | `npm install -g` |
| Dashboard start | `source venv/bin/activate` | `source venv/bin/activate` | `venv\Scripts\activate` |
| File locking | `chflags schg` | `chattr +i` | N/A (no immutability) |
| Temp dir | `/tmp/` | `/tmp/` or `/var/tmp/` | `%TEMP%` |
