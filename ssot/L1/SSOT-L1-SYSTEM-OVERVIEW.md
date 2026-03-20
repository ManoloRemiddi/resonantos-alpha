# SSOT-L1-SYSTEM-OVERVIEW — ResonantOS Architecture
Updated: 2026-03-16

| Field | Value |
|-------|-------|
| ID | SSOT-L1-SYSTEM-OVERVIEW-V1 |
| Created | 2026-02-09 |
| Updated | 2026-03-16 |
| Author | Setup Agent |
| Level | L1 (Architecture) |
| Type | Truth |
| Status | Active |
| Stale After | 90 days |

---

## 1. System Stack

```
┌─────────────────────────────────────┐
│         ResonantOS Layer            │
│  Shield, Logician, R-Awareness,     │
│  Memory Logs, Dashboard, Watchdog   │
├─────────────────────────────────────┤
│         OpenClaw Kernel             │
│  Gateway, Sessions, Tools, Cron,    │
│  LCM (context engine), Plugins      │
├─────────────────────────────────────┤
│         Infrastructure              │
│  Host machine, Channels, Providers  │
└─────────────────────────────────────┘
```

ResonantOS is NOT a fork of OpenClaw. It is a **compatible experience layer** that rides on OpenClaw's infrastructure. All ResonantOS features integrate WITH OpenClaw's existing systems — never fight them.

## 2. OpenClaw Kernel (What We Ride On)

### 2.1 Gateway
- **Process:** `openclaw gateway` — Node.js daemon on port 18789
- **Config:** `~/.openclaw/openclaw.json` — all settings
- **Restart:** SIGUSR1 signal, auto-reconnects sessions

### 2.2 Sessions
- **Main session:** `agent:main:main` — persistent, direct chat with human
- **Sub-agent sessions:** Spawned for background tasks, isolated context
- **Session store:** SQLite-backed, per-agent

### 2.3 Models
> **Configure per your setup.** ResonantOS is model-agnostic — provider switch = config change, not rebuild.

Recommended allocation:
| Role | Recommendation |
|------|---------------|
| Main session | Best reasoning model you have access to |
| Sub-agents | Cost-effective workhorse model |
| Coding | Codex CLI or equivalent external tool |
| Heartbeat | Cheapest available model |

### 2.4 Channels
Configure in `openclaw.json`. Supported: Telegram, Discord, Webchat, Signal, WhatsApp, Slack, IRC, and more.

### 2.5 Tools (OpenClaw-Provided)
| Tool | Purpose |
|------|---------|
| read/write/edit | File operations |
| exec/process | Shell commands, background processes |
| web_search/web_fetch | Internet access |
| browser | Browser automation |
| cron | Scheduled jobs, reminders |
| message | Send/react/delete on channels |
| memory_search/memory_get | Semantic search over memory files |
| sessions_spawn/send/list | Sub-agent management |
| tts | Text-to-speech |

### 2.6 Memory (OpenClaw Built-in)
- **MEMORY.md:** Long-term curated memory (loaded in main session only)
- **memory/*.md:** Daily notes, raw logs
- **memory_search:** Semantic vector search over memory files (SQLite + embeddings)
- **Workspace files:** AGENTS.md, SOUL.md, USER.md, IDENTITY.md, TOOLS.md, HEARTBEAT.md — loaded at session start

### 2.7 Heartbeat
- **Interval:** Configurable in openclaw.json
- **Purpose:** Periodic checks, proactive tasks
- **Config:** HEARTBEAT.md defines what to check

### 2.8 Cron
- **Scheduler:** Built into gateway
- **Job types:** `systemEvent` (inject into main session) or `agentTurn` (isolated sub-agent)

### 2.9 Platform Security Configuration

Recommended security settings for production deployments:

| Setting | Recommended | Why |
|---------|-------------|-----|
| `tools.sessions.visibility` | `tree` | Agent sees only own session + spawned sub-agents. `self` breaks monitoring; `all` leaks cross-session data. |
| Queue mode | `collect` (default) | Corrections batch together, background agents finish uninterrupted. |
| `plugins.allow` | Explicit allowlist | Only load plugins you trust. Reduces attack surface. |

**Agent Tool Restrictions:** Sandbox agents by role. Research agents should have web/file/memory access but no exec/browser/messaging. Creative agents should be local-only (no web, no messaging). Define per-agent `tools.allow` lists in your config.

**Node Permissions (Multi-Machine):** Apply least-privilege allowlists for remote nodes. Only designated agents (main, deputy, setup) should target remote nodes. Deny destructive operations by default.

## 3. ResonantOS Layer (What We Build)

### 3.1 SSoT System
**Purpose:** Hierarchical document system giving AI structured awareness at multiple zoom levels.

| Level | Scope | Update Freq |
|-------|-------|-------------|
| L0 | Foundation (vision, philosophy, identity) | Rarely |
| L1 | Architecture (system specs, how things work) | Monthly |
| L2 | Projects (active work items) | Weekly |
| L3 | Drafts (WIP ideas) | As needed |
| L4 | Notes (raw captures) | Daily |

**Naming convention:** `SSOT-L{level}-{NAME}.md`
- `.md` = **original, authoritative source of truth**
- `.ai.md` = **compressed derivative** (50-80% smaller, loaded by AI to save tokens)
- Workflow: edit `.md` → delete old `.ai.md` → regenerate

### 3.2 Components

| Component | Purpose | Key Files |
|-----------|---------|-----------|
| **Shield** | Security enforcement — file protection, data leak prevention, coding delegation | `~/.openclaw/extensions/shield-gate/` |
| **Logician** | Deterministic policy engine (Mangle/Datalog) | `logician/poc/production_rules.mg` |
| **R-Awareness** | Context injection — keywords trigger relevant SSoT docs + always-on navigational docs | `~/.openclaw/extensions/r-awareness/` |
| **Dashboard** | Local web UI (Flask) for system management | `dashboard/` |
| **Watchdog** | Service health monitoring, auto-restart | LaunchAgents/systemd |
| **LCM** | Lossless Context Management — DAG-based summarization replacing lossy compaction | Plugin: `@martian-engineering/lossless-claw` |
| **Memory Logs** | Structured session capture (DNA format: Process Log + Trilemma + DNA Sequencing) | `memory/shared-log/` |

### 3.3 Plugins (OpenClaw Extension System)

| Plugin | Type | Purpose |
|--------|------|---------|
| shield-gate | Extension | Security enforcement layers |
| coherence-gate | Extension | Response quality checks |
| r-awareness | Extension | SSoT document injection |
| usage-tracker | Extension | LLM call logging |
| heuristic-auditor | Extension | Post-response philosophical audit |
| lossless-claw | Context Engine | LCM — lossless context management |

### 3.4 Key Design Principle: Integration Over Replacement

Never duplicate what OpenClaw already provides. Build enhancement layers ON TOP of OpenClaw's systems. External triggers only for compression/eviction.

## 4. Memory Architecture (4-Layer Stack)

| Layer | What | Persistence |
|-------|------|-------------|
| MEMORY.md | Long-term curated knowledge | Permanent, main session only |
| Memory Headers | Last N memory log summaries (RECENT-HEADERS.md) | FIFO, always-on via R-Awareness |
| LCM | Session history compression (DAG-based) | Automatic via context engine |
| RAG | Semantic vector search over documents | On-demand via embeddings |

### Key Paths
- **Memory logs:** `memory/shared-log/MEMORY-LOG-YYYY-MM-DD[-suffix].md`
- **Breadcrumbs:** `memory/breadcrumbs.jsonl` (real-time event capture)
- **Daily notes:** `memory/YYYY-MM-DD.md`
- **Headers:** `ssot/L1/RECENT-HEADERS.md` (auto-generated)

## 5. File System Layout

```
~/.openclaw/
├── openclaw.json              # Gateway config
├── extensions/                # ResonantOS plugins
│   ├── shield-gate/
│   ├── r-awareness/
│   ├── coherence-gate/
│   ├── usage-tracker/
│   └── heuristic-auditor/
├── workspace/                 # Agent workspace root
│   ├── AGENTS.md              # Agent behavior rules
│   ├── SOUL.md                # Identity & personality
│   ├── USER.md                # Human profile
│   ├── IDENTITY.md            # Name, emoji, vibe
│   ├── TOOLS.md               # Local tool notes
│   ├── MEMORY.md              # Long-term curated memory
│   ├── HEARTBEAT.md           # Periodic check config
│   ├── OPEN-ITEMS.md          # Live WIP register
│   ├── memory/                # Daily notes + shared logs
│   └── [project-repo]/        # Your project repo
│       ├── dashboard/         # Dashboard (Flask)
│       ├── logician/          # Policy engine
│       ├── shield/            # Security daemon + configs
│       ├── scripts/           # Automation scripts
│       └── ssot/              # SSoT hierarchy (L0-L4)
```

## 6. Token Budget Strategy

| Principle | Rule |
|-----------|------|
| Default loading | `.ai.md` compressed versions |
| Detail needed | Zoom into full `.md` docs |
| Periodic checks | Batch into heartbeats |
| Exact-time tasks | Use cron (isolated, cheap model) |
| Security | Never load MEMORY.md in non-main sessions |

## 7. References

| Document | Contents |
|----------|----------|
| `L0/SSOT-L0-OVERVIEW.md` | What ResonantOS is, mission, vision |
| `L1/SSOT-L1-SHIELD.md` | Shield enforcement architecture |
| `L1/SSOT-L1-LOGICIAN.md` | Policy engine specification |
| `L1/SSOT-L1-R-AWARENESS.md` | Context injection system |
| `L1/SSOT-L1-MEMORY-ARCHITECTURE.md` | Memory stack design |
| `L1/SSOT-L1-MEMORY-LOG.md` | Memory log format (DNA template) |
| `L1/SSOT-L1-LCM.md` | Lossless Context Management |
| `L1/OPENCLAW-INDEX.ai.md` | OpenClaw kernel docs index |
