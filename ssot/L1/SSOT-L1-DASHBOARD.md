# SSOT-L1-DASHBOARD — Web UI
Updated: {{GENERATED_DATE}}

## Purpose
The Dashboard is a Flask-based web UI for monitoring and managing your ResonantOS installation.

## Access
- **URL:** http://127.0.0.1:19100
- **Auth:** {{DASHBOARD_AUTH_METHOD}}

## Pages

### Home
**Route:** `/`

**Features:**
- System health overview
- Memory usage (context window breakdown)
- Token usage summary
- Recent activity feed

### Agents
**Route:** `/agents`

**Features:**
- List all configured agents
- Model selection per agent
- Token usage by agent
- Session management

### Chatbots
**Route:** `/chatbots`

**Features:**
- Channel configuration (Telegram, Discord, etc.)
- Message history
- Bot status

### Memory
**Route:** `/memory`

**Features:**
- SSoT document browser
- Memory search (semantic + keyword)
- Memory log viewer
- Compression stats

### Wallet
**Route:** `/wallet`

**Features:**
- Balance display (Human + AI + Symbiotic)
- Transaction history
- Transfer UI
- Approval management

### Bounties
**Route:** `/bounties`

**Features:**
- Bounty board (open + claimed + completed)
- Create new bounty
- Claim bounty
- Submit completion

### Tribes
**Route:** `/tribes`

**Features:**
- Tribe discovery
- Membership management
- Tribe creation

### Projects
**Route:** `/projects`

**Features:**
- Active projects list
- Project status dashboard
- Task tracking

### Docs
**Route:** `/docs`

**Features:**
- SSoT documentation viewer
- Quick reference guides
- API documentation

### Settings
**Route:** `/settings`

**Features:**
- Component toggles (Shield, Logician, etc.)
- Model configuration
- Channel setup
- Extension management

## Configuration

### Server
- **Framework:** Flask
- **Port:** 19100
- **Host:** 127.0.0.1 (localhost only)
- **Process:** {{DASHBOARD_PROCESS_MANAGER}}

### Dependencies
- Flask
- Jinja2
- {{DASHBOARD_ADDITIONAL_DEPS}}

## API Endpoints

### System
- `GET /api/system/health` — Health check
- `GET /api/system/status` — Full status

### Memory
- `GET /api/memory/stats` — Memory usage stats
- `POST /api/memory/search` — Semantic search

### Agents
- `GET /api/agents/list` — List all agents
- `POST /api/agents/configure` — Update agent config

### Wallet
- `GET /api/wallet/balance` — Get all balances
- `POST /api/wallet/transfer` — Execute transfer

### Full API documentation:** `/docs/api`

## Development

### Run Locally
```bash
cd {{DASHBOARD_PATH}}
python server.py
```

### Logs
{{DASHBOARD_LOG_PATH}}

### Restart
```bash
{{DASHBOARD_RESTART_COMMAND}}
```

---

_This document describes the Dashboard. Configuration is populated during setup._
