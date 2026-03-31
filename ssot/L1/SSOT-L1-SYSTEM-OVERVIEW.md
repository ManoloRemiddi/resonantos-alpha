# SSOT-L1-SYSTEM-OVERVIEW — ResonantOS Architecture
Updated: {{GENERATED_DATE}}

| Field | Value |
|-------|-------|
| ID | SSOT-L1-SYSTEM-OVERVIEW-V1 |
| Created | {{SETUP_DATE}} |
| Updated | {{GENERATED_DATE}} |
| Author | {{AGENT_NAME}} |
| Level | L1 (Architecture) |
| Type | Truth |
| Status | Active |
| Stale After | 90 days |

---

## 1. System Stack

```
┌─────────────────────────────────────┐
│         ResonantOS Layer            │
│  (SSoT, Shield, Logician, etc.)     │
├─────────────────────────────────────┤
│         OpenClaw Kernel             │
│  (Gateway, Sessions, Tools, Cron)   │
├─────────────────────────────────────┤
│         Infrastructure              │
│  {{USER_OS}}, {{USER_CHANNELS}}     │
└─────────────────────────────────────┘
```

ResonantOS is NOT a fork of OpenClaw. It is a **compatible experience layer** that rides on OpenClaw's infrastructure. All ResonantOS features integrate WITH OpenClaw's existing systems — never fight them.

## 2. OpenClaw Kernel (What We Ride On)

### 2.1 Gateway
- **Process:** `openclaw gateway` — Node.js daemon on port 18789
- **Config:** `~/.openclaw/openclaw.json` — all settings, hot-reloadable via `config.patch`
- **Auth:** OAuth token to Anthropic API (not direct API key)
- **Restart:** SIGUSR1 signal, auto-reconnects sessions

### 2.2 Sessions
- **Main session:** `agent:main:main` — persistent, direct chat with you
- **Sub-agent sessions:** Spawned for background tasks, isolated context
- **Compaction:** When context gets large, OpenClaw uses LCM (Lossless Context Management) for lossless compression
- **Session store:** SQLite-backed, per-agent

### 2.3 Models
- **Primary:** {{USER_PRIMARY_MODEL}} (main session — full reasoning)
- **Heartbeat:** {{USER_HEARTBEAT_MODEL}} (periodic checks, token-efficient)
- **Sub-agents:** {{USER_SUBAGENT_MODELS}} (background tasks)
- **Principle:** Use your best model for main work, cheaper models for background tasks

### 2.4 Channels
- **Primary:** {{USER_PRIMARY_CHANNEL}} (your main interface)
- **Secondary:** {{USER_SECONDARY_CHANNELS}}
- **Capabilities:** Inline buttons, reactions, streaming (varies by channel)

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
| gateway | Config, restart, updates |
| tts | Text-to-speech |

### 2.6 Memory (OpenClaw Built-in)
- **MEMORY.md:** Long-term curated memory (loaded in main session only)
- **memory/*.md:** Daily notes, raw logs
- **memory_search:** Semantic vector search over memory files (SQLite + embeddings)
- **Workspace files:** AGENTS.md, SOUL.md, USER.md, IDENTITY.md, TOOLS.md, HEARTBEAT.md — loaded at session start as system context

### 2.7 Heartbeat
- **Interval:** Configurable (default: OpenClaw defaults)
- **Model:** {{USER_HEARTBEAT_MODEL}}
- **Purpose:** Periodic checks (email, calendar, proactive tasks)
- **Config:** HEARTBEAT.md defines what to check

### 2.8 Cron
- **Scheduler:** Built into gateway
- **Job types:** `systemEvent` (inject into main session) or `agentTurn` (isolated sub-agent)
- **Use cases:** Reminders, scheduled tasks, periodic reports

### 2.9 Platform Security Configuration

OpenClaw platform-level security settings configured in `openclaw.json`:

| Setting | Value | Default | Rationale |
|---------|-------|---------|-----------|
| `tools.sessions.visibility` | `tree` | `tree` | Agent sees own session + spawned subagents only. Options: `self` (too restrictive — breaks subagent monitoring), `tree` (correct), `agent` (all sessions of same agent — leaks cross-session context), `all` (all agents — dangerous). Set explicitly to prevent silent default changes. |
| `session.dmScope` | (default: `main`) | `main` | DMs collapse to one session. Safe for single-user. For multi-user: switch to `per-channel-peer`. |

**Queue mode:** `collect` (default) for all agents. Messages arriving mid-run are coalesced into a single followup turn. Alternatives: `steer` (inject at tool boundary — risks derailing expensive background work), `followup` (one turn per message). `collect` is correct for most workloads — corrections batch cleanly, background agents finish uninterrupted. Override per-session with `/queue <mode>` if needed.

**Key distinctions (from OpenClaw architecture analysis):**
- **Session key = routing**, not authorization. It isolates context, not power.
- **Session lane = single-writer correctness**, not privacy. It prevents concurrent writes, not cross-session reads.

**Security audit reference:** `openclaw security audit` checks for dangerous exposures. Run periodically.

## 3. ResonantOS Layer (What We Build)

### 3.1 SSoT System ✅ IMPLEMENTED
**Purpose:** Hierarchical document system giving AI structured awareness at multiple zoom levels.

**Hierarchy:**
| Level | Scope | Token Cost | Update Freq |
|-------|-------|-----------|-------------|
| L0 | Foundation (vision, philosophy, business) | ~130 tokens (compressed) | Rarely |
| L1 | Architecture (system specs, how things work) | Medium | Monthly |
| L2 | Projects (active work items) | Low | Weekly |
| L3 | Drafts (WIP ideas) | Varies | As needed |
| L4 | Notes (raw captures) | Ephemeral | Daily |

**Location:** `~/resonantos-augmentor/ssot/L{0-4}/` (or your configured SSoT path)

**Naming convention:** `SSOT-L{level}-{NAME}[-SUFFIX].md`
- `.md` = **original, authoritative source of truth** (human-editable, may be locked with `schg`)
- `.ai.md` = **compressed derivative** generated FROM the `.md` original (loaded by AI, saves tokens)
- `-DRAFT` = needs revision
- `-OLD` = v1 spec, kept for reference

**How it works:**
1. Full documents (`.md`) are the source of truth — all edits happen here first
2. Compressed versions (`.ai.md`) are derivatives, 50-80% smaller, regenerated from the original
3. AI loads compressed versions by default, full versions when detail needed
4. When updating: edit `.md` → delete old `.ai.md` → regenerate `.ai.md` from updated `.md`
5. Overview docs at each level provide cheap navigation (few tokens for full picture)

### 3.2 Shield ✅ IMPLEMENTED
**Purpose:** Security enforcement daemon — blocks dangerous operations before they execute.

**Architecture:** Flask daemon on port 9999, hooks into OpenClaw via extension

**Layers:**
1. Destructive command blocking (rm, force push, etc.)
2. Coding gate (code modifications go through Codex)
3. Coherence enforcement (task-focus validation)
4. Network allowlist
5. Sensitive path protection
6. Config change gate
7. Repository contamination prevention
8. File guard (watchdog for workspace integrity)
9. YARA malware scanning (nightly)
10. Atomic rebuild gate (Create → Verify → Delete for code changes)

**State:** Active, 16 blocking layers

### 3.3 Logician ✅ IMPLEMENTED
**Purpose:** Governance engine — validates operations against rules expressed in Mangle Datalog.

**Architecture:** Mangle server (Unix socket `/tmp/mangle.sock`) + logician-proxy (HTTP on port 8081)

**Rule base:** `production_rules.mg` (278 facts, 10 agents)
**Query language:** Mangle Datalog (subset of Datalog with stratified negation)

**Use cases:**
- Agent capability boundaries
- Task eligibility
- Resource access control
- Policy compliance checks

**State:** Active, 19 rule files

### 3.4 LCM (Lossless Context Management) ✅ ACTIVE
**Purpose:** Replace OpenClaw's lossy compaction with DAG-based summarization.

**Plugin:** `@martian-engineering/lossless-claw` v0.5.2
**Database:** `~/.openclaw/lcm.db` (SQLite, {{USER_LCM_DB_SIZE}} MB)

**Key config:**
- `freshTailCount: 32` — recent messages protected from compaction
- `incrementalMaxDepth: -1` — unlimited auto-condensation (prevents summary bloat)
- `contextThreshold: 0.75` — compaction triggers at 75% of context window

**Agent tools:** `lcm_grep`, `lcm_describe`, `lcm_expand`, `lcm_expand_query`

**State:** Active, primary context engine

### 3.5 R-Awareness ✅ IMPLEMENTED
**Purpose:** Context injection system — loads SSoT docs triggered by keywords in conversation.

**Triggers:** Keywords in user messages or AI tool calls
**Config:** `keywords.json` (keyword → document mapping)
**Cold-start docs:** Recent headers (last 20 memory log summaries)

**State:** Active, {{USER_KEYWORD_COUNT}} keywords configured

### 3.6 Dashboard ✅ IMPLEMENTED
**Purpose:** Web UI for system monitoring and management.

**Server:** Flask on port 19100
**Pages:** Home, Agents, Chatbots, Memory, Wallet, Bounties, Tribes, Projects, Docs, Settings

**Features:**
- System health monitoring
- Agent management
- Memory bridge (SSoT manager)
- Token usage tracking
- Shield policy viewer
- Logician rule explorer

**State:** Active, v{{USER_DASHBOARD_VERSION}}

### 3.7 Memory Architecture
**Layer 1: MEMORY.md** (~15K tokens) — curated long-term memory, main session only
**Layer 2: Recent Headers** (~5K tokens) — last 20 memory log headers via R-Awareness
**Layer 3: LCM** (session-scoped) — lossless context management
**Layer 4: RAG** (on-demand) — semantic search via `memory_search`

**Memory log format:** 3-part DNA (Process Log + Trilemma + DNA Sequencing)
**Generation:** Intraday cron (every 3h) + nightly safety net (04:30)

### 3.8 Crypto Wallet (Symbiotic Wallet)
**Status:** {{USER_WALLET_STATUS}}
**Chain:** Solana DevNet
**Architecture:** Three-wallet (Human + AI + Symbiotic PDA)
**Tokens:** $RCT (soulbound) + $RES (transferable)

### 3.9 DAO
**Status:** {{USER_DAO_STATUS}}
**Governance:** Multi-signature via Symbiotic Wallet
**Token-gating:** $RCT holder access

## 4. File System Layout

```
~/.openclaw/
├── openclaw.json              # Gateway config
├── lcm.db                    # LCM database
├── workspace/                 # Agent workspace root
│   ├── AGENTS.md              # Agent behavior rules
│   ├── SOUL.md                # Identity & personality
│   ├── USER.md                # Human profile
│   ├── IDENTITY.md            # Name, emoji, vibe
│   ├── TOOLS.md               # Local tool notes
│   ├── MEMORY.md              # Long-term curated memory
│   ├── HEARTBEAT.md           # Periodic check config
│   ├── memory/                # Daily notes
│   │   ├── shared-log/        # Memory logs (DNA format)
│   │   └── breadcrumbs.jsonl  # Real-time event capture
│   └── {{USER_SSOT_PATH}}/    # SSoT hierarchy
│       ├── L0/                # Foundation docs
│       ├── L1/                # Architecture docs
│       ├── L2/                # Project docs
│       ├── L3/                # Drafts
│       └── L4/                # Notes
├── extensions/                # Custom plugins
│   ├── shield-gate/
│   ├── coherence-gate/
│   ├── r-awareness/
│   ├── usage-tracker/
│   └── heuristic-auditor/
└── agents/                    # Agent directories
    └── main/                  # Main agent
```

## 5. Infrastructure

### 5.1 Hardware
{{USER_HARDWARE_SECTION}}

### 5.2 Operating System
- **OS:** {{USER_OS}}
- **Architecture:** {{USER_ARCH}}
- **Node.js:** {{USER_NODE_VERSION}}

### 5.3 Network
{{USER_NETWORK_SECTION}}

### 5.4 Backups
{{USER_BACKUP_SECTION}}

### 5.5 Monitoring
{{USER_MONITORING_SECTION}}

## 6. Token Budget Strategy

| Context | Model | Reason |
|---------|-------|--------|
| Direct chat | {{USER_PRIMARY_MODEL}} | Full reasoning, complex tasks |
| Heartbeat checks | {{USER_HEARTBEAT_MODEL}} | Cheap, routine checks |
| Sub-agent tasks | {{USER_SUBAGENT_MODELS}} | Background work |
| Document loading | .ai.md preferred | 50-80% token savings |

**Budget principles:**
- Load compressed docs by default
- Zoom into full docs only when detail needed
- Batch periodic checks into heartbeats (fewer API calls)
- Use cron for exact-time tasks (isolated, cheap model)
- Never load MEMORY.md in non-main sessions (security + tokens)

## 7. Extension Registry

| Extension | Purpose | State |
|-----------|---------|-------|
| **shield-gate** | Security enforcement | Active |
| **coherence-gate** | Task coherence enforcement | Active |
| **r-awareness** | SSoT context injection | Active |
| **heuristic-auditor** | Post-response quality audit | Active |
| **usage-tracker** | Token/cost tracking | Active |
| **lossless-claw** | Context engine (LCM) | Active |

## 8. Key Design Principles

| Principle | Rationale |
|-----------|-----------|
| Experience layer, not fork | Ensures OpenClaw compatibility |
| Integration over replacement | R-Memory v1 failed by replacing built-in memory; LCM integrates |
| Deterministic over AI | Scripts/cron for reliability, AI only when reasoning needed |
| Quality over speed | Build properly the first time |
| Open-source first | Don't reinvent what exists and works |
| Model-agnostic architecture | Provider switch = config change, not rebuild |

## 9. Current State

| Metric | Value |
|--------|-------|
| OpenClaw version | {{USER_OPENCLAW_VERSION}} |
| ResonantOS components | {{USER_COMPONENT_COUNT}} active |
| LCM conversations | {{USER_LCM_CONVERSATIONS}} |
| LCM messages | {{USER_LCM_MESSAGES}} |
| LCM summaries | {{USER_LCM_SUMMARIES}} |
| SSoT documents | {{USER_SSOT_DOCUMENT_COUNT}} |
| Memory logs | {{USER_MEMORY_LOG_COUNT}} |
| Dashboard version | {{USER_DASHBOARD_VERSION}} |

---

_This overview is maintained by the Setup Agent. Personal sections are populated during onboarding and updated as your system evolves._
