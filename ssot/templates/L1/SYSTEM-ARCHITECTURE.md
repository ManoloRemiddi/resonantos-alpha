# ResonantOS — System Architecture

| Field | Value |
|-------|-------|
| Version | 1.0 (Alpha) |
| Date | 2026-02-18 |
| Level | L1 (Architecture) |

---

## System Stack

```
┌─────────────────────────────────────┐
│         ResonantOS Layer            │
│  (SSoT, Compression, Memory, etc.) │
├─────────────────────────────────────┤
│         OpenClaw Kernel             │
│  (Gateway, Sessions, Tools, Cron)   │
├─────────────────────────────────────┤
│         Infrastructure              │
│  (macOS/Linux, Messaging, LLM API) │
└─────────────────────────────────────┘
```

ResonantOS is a compatible experience layer on OpenClaw. It integrates WITH existing systems — never fights them.

---

## OpenClaw Kernel

### Gateway
- Node.js daemon managing sessions, tools, and channels
- Config: `~/.openclaw/openclaw.json` (hot-reloadable)
- Restart: `openclaw gateway restart`

### Sessions
- **Main session:** Persistent chat with human
- **Sub-agents:** Spawned for background tasks with isolated context
- **Compaction:** OpenClaw summarizes large contexts when they exceed limits

### Models
- **Primary model (e.g. Opus 4.6):** Main session, complex reasoning
- **Cheap model (e.g. Haiku 4.5):** Heartbeat checks, sub-agents, compression
- **Principle:** Use full reasoning only where needed; save tokens everywhere else

### Channels
OpenClaw supports multiple messaging channels: Telegram, Discord, Slack, WhatsApp, Signal, iMessage, webchat.

### Tools
| Tool | Purpose |
|------|---------|
| read/write/edit | File operations |
| exec/process | Shell commands, background tasks |
| web_search/web_fetch | Internet access |
| browser | Web automation |
| cron | Scheduled jobs and reminders |
| message | Send/react/delete on channels |
| memory_search/get | Semantic memory search |
| sessions_spawn/send | Sub-agent management |
| tts | Text-to-speech |

### Memory (Native)
- **MEMORY.md:** Long-term curated memory
- **memory/*.md:** Daily raw logs
- **memory_search:** Semantic vector search
- **Workspace files:** AGENTS.md, SOUL.md, USER.md, IDENTITY.md, TOOLS.md, HEARTBEAT.md

### Heartbeat
Periodic polling mechanism. Configurable interval. Uses cheap model. Drives proactive checks (email, calendar, tasks). Configure via HEARTBEAT.md.

### Cron
Built-in scheduler. Job types: `systemEvent` (inject into main session) or `agentTurn` (isolated sub-agent run). Use for reminders, scheduled tasks, reports.

---

## ResonantOS Layer

### SSoT System
Hierarchical documents giving AI structured awareness at multiple zoom levels.

| Level | Scope | Update Frequency |
|-------|-------|-----------------|
| L0 | Vision, philosophy, business | Rare |
| L1 | Architecture, system specs | Monthly |
| L2 | Active projects | Weekly |
| L3 | WIP ideas | As needed |
| L4 | Raw captures, notes | Daily |

**Path:** `ssot/L{0-4}/`

Each document can have a compressed `.ai.md` variant (50-80% smaller, lossless) used by R-Awareness to save tokens.

### Components

| Component | Purpose | Status |
|-----------|---------|--------|
| **R-Memory** | Conversation compression & archival | Active |
| **R-Awareness** | SSoT context injection | Active |
| **Shield** | Security monitoring, file protection | In development |
| **Logician** | Governance, policy validation | Spec phase |
| **Guardian** | Self-healing, watchdog | Design |
| **Dashboard** | Web UI for system management | Active |
| **Crypto Wallet** | Solana integration, DAO governance | Alpha |

### Integration Principle

ResonantOS builds ON TOP of OpenClaw — never duplicating or replacing existing functionality. Extensions hook into OpenClaw's lifecycle events to add capabilities.

---

## Token Budget Strategy

| Context | Model | Rationale |
|---------|-------|-----------|
| Main chat | Primary (Opus) | Full reasoning needed |
| Heartbeat | Cheap (Haiku) | Routine checks |
| Sub-agents | Cheap (Haiku) | Background work |
| Doc loading | .ai.md compressed | 50-80% savings |

**Principles:**
- Default to compressed docs
- Zoom into full versions only when needed
- Batch heartbeat checks
- Use cron for exact-time tasks
