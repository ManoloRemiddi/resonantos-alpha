# SSOT-L1-SYSTEM-OVERVIEW — ResonantOS Architecture
Updated: 2026-03-16

| Field | Value |
|-------|-------|
| ID | SSOT-L1-SYSTEM-OVERVIEW-V1 |
| Created | 2026-02-09 |
| Updated | 2026-03-15 |
| Author | Augmentor |
| Level | L1 (Architecture) |
| Type | Truth |
| Status | Active |
| Stale After | 90 days |

---

## 1. System Stack

```
┌─────────────────────────────────────┐
│         ResonantOS Layer            │
│  (SSoT, Compression, Memory, etc.) │
├─────────────────────────────────────┤
│         OpenClaw Kernel             │
│  (Gateway, Sessions, Tools, Cron)   │
├─────────────────────────────────────┤
│         Infrastructure              │
│  (macOS, Telegram, Anthropic API)   │
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
- **Main session:** `agent:main:main` — persistent, direct chat with Manolo
- **Sub-agent sessions:** Spawned for background tasks, isolated context
- **Compaction:** When context gets large, OpenClaw summarizes history (mode: safeguard)
- **Session store:** SQLite-backed, per-agent

### 2.3 Models
- **Primary:** `anthropic/claude-opus-4-6` (main session — full reasoning)
- **Heartbeat:** `google/gemini-2.5-flash` (free tier periodic checks)
- **Sub-agents:** Various (Codex for coding, MiniMax M2.5 for R-Memory compression, M2.1 for narrative)
- **Principle:** Opus for main session, Gemini Flash for heartbeat, MiniMax for R-Memory — save tokens aggressively

### 2.4 Channels
- **Telegram:** Primary interface, paired with Manolo (chatId: YOUR_TELEGRAM_CHAT_ID)
- **Webchat:** Available but secondary
- **Capabilities:** Inline buttons, reactions (minimal mode), streaming (partial)

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
- **Interval:** Configurable (currently using OpenClaw defaults)
- **Model:** Haiku 4.5 (token-efficient)
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

**Queue mode:** `collect` (default) for all agents. Messages arriving mid-run are coalesced into a single followup turn. Alternatives: `steer` (inject at tool boundary — risks derailing expensive background work), `followup` (one turn per message). Decision (2026-03-16): `collect` is correct for our workload — corrections batch cleanly, background agents finish uninterrupted. Override per-session with `/queue <mode>` if needed.

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

**Location:** `/resonantos-alpha/ssot/L{0-4}/`

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

### 3.2 Compression System ✅ IMPLEMENTED
**Purpose:** Create token-efficient versions of all SSoT documents.

**Method:**
- Sub-agent (Haiku 4.5) reads full document
- Removes filler, redundancy, verbose explanations
- Preserves ALL technical details, numbers, parameters, decisions
- Uses terse notation, abbreviations, shorthand
- Output: `.ai.md` file alongside original

**Trigger:** External (human-initiated or scripted) — never self-triggered by AI
**Eviction:** FIFO (deterministic) over "smart" eviction (probabilistic)

**Token savings achieved:** 55-81% across L0 documents

### 3.3 Components (Planned/In Design)

| Component | Status | Description |
|-----------|--------|-------------|
| Shield | OLD spec exists | Security monitoring daemon |
| Logician | OLD spec exists | Governance, policy validation |
| Guardian | Not started | Self-healing, watchdog |
| R-Memory v2 | Designing | Enhanced memory (must integrate WITH OpenClaw) |
| R-Awareness | OLD spec exists | Context awareness layer |
| A2A Protocols | Not started | Agent-to-agent economy |
| Crypto Wallet | Not started | Solana integration |
| DAO | Not started | Decentralized governance |

### 3.4 Key Design Principle: Integration Over Replacement

**Root cause of v1 failure:** R-Memory v1 was built without understanding OpenClaw's existing memory system. It created parallel structures that conflicted with OpenClaw's built-in memory, causing data deletion.

**v2 approach:**
1. Map OpenClaw's memory internals completely (source code, not just docs)
2. Identify integration points (hooks, not replacements)
3. Build R-Memory v2 as an enhancement layer ON TOP of OpenClaw's memory
4. Never duplicate what OpenClaw already provides
5. External triggers only for compression/eviction

## 4. File System Layout

```
~/.openclaw/
├── openclaw.json              # Gateway config
├── workspace/                 # Agent workspace root
│   ├── AGENTS.md              # Agent behavior rules
│   ├── SOUL.md                # Identity & personality
│   ├── USER.md                # Human profile
│   ├── IDENTITY.md            # Name, emoji, vibe
│   ├── TOOLS.md               # Local tool notes
│   ├── MEMORY.md              # Long-term curated memory
│   ├── HEARTBEAT.md           # Periodic check config
│   ├── memory/                # Daily notes
│   │   └── YYYY-MM-DD.md
│   └── resonantos-alpha/  # ResonantOS repo
│       ├── docs/              # Old v1 documents (reference)
│       └── ssot/              # SSoT hierarchy
│           ├── L0/            # Foundation docs
│           ├── L1/            # Architecture docs (this level)
│           ├── L2/            # Project docs
│           ├── L3/            # Drafts
│           └── L4/            # Notes
```

## 5. Token Budget Strategy

| Context | Model | Reason |
|---------|-------|--------|
| Direct chat with Manolo | Opus 4 | Full reasoning, complex tasks |
| Heartbeat checks | Haiku 4.5 | Cheap, routine checks |
| Sub-agent tasks | Haiku 4.5 | Background work, compression |
| Document loading | .ai.md preferred | 50-80% token savings |

**Budget principles:**
- Load compressed docs by default
- Zoom into full docs only when detail needed
- Batch periodic checks into heartbeats (fewer API calls)
- Use cron for exact-time tasks (isolated, cheap model)
- Never load MEMORY.md in non-main sessions (security + tokens)

## 6. Extension Architecture

### 6.1 Overview

ResonantOS components run as **OpenClaw plugins** (extensions). Each extension hooks into the gateway's event system (before_tool_call, after_tool_call, before_response, etc.) to enforce policies, inject context, or track usage.

### 6.2 Extension Registry

| Extension | Purpose | Layers/Features |
|-----------|---------|-----------------|
| **shield-gate** | Security enforcement | 16 blocking layers (destructive commands, coding gate, coherence enforcement, network allowlist, sensitive path protection, config change gate, repo contamination, etc.) |
| **coherence-gate** | Task coherence enforcement | Verifies agent stays on-task, prevents drift |
| **r-awareness** | SSoT context injection | Keyword-triggered document loading, compound keywords, coldStartDocs |
| **heuristic-auditor** | Post-response quality audit | Checks responses against heuristic rules |
| **usage-tracker** | Token/cost tracking | Persistent usage stats across all agents |
| **lossless-claw** | Context engine (LCM) | Lossless context management, compaction — **stock OpenClaw plugin** (not ours) |

### 6.3 File Layout & Sync Architecture

**Source of truth:** `~/resonantos-alpha/extensions/{name}/`

```
resonantos-alpha/extensions/
├── shield-gate/
│   ├── index.js              # Main plugin code
│   └── openclaw.plugin.json  # Plugin manifest (id, name, version)
├── coherence-gate/
├── r-awareness/
│   ├── index.js
│   ├── openclaw.plugin.json
│   ├── keywords.json         # R-Awareness keyword triggers
│   └── package.json
├── usage-tracker/
└── heuristic-auditor/
    ├── index.js
    ├── openclaw.plugin.json
    └── heuristics.json       # Audit rules
```

**Live runtime:** `~/.openclaw/extensions/{name}/` — gateway loads plugins from here.

**⚠️ CRITICAL: Symlinks do NOT work.** OpenClaw's plugin boundary security (`openBoundaryFileSync`) resolves symlinks via `realpath()` and blocks any source that resolves outside the plugin root directory. This is correct security behavior — prevents path traversal. Both per-file and per-directory symlinks are blocked.

**Sync workflow (zero-drift):**
1. Edit code in `~/resonantos-alpha/extensions/{name}/index.js`
2. Run `scripts/sync-extensions.sh` — diffs repo→live, copies only changed files
3. Run `openclaw gateway restart` to load updated code
4. **Never edit `~/.openclaw/extensions/` directly** — those are deploy copies

**Script location:** `~/resonantos-alpha/scripts/sync-extensions.sh`

### 6.4 Plugin Configuration

In `openclaw.json`:
```json
{
  "plugins": {
    "allow": ["coherence-gate", "heuristic-auditor", "lossless-claw", "r-awareness", "shield-gate", "usage-tracker", "telegram"],
    "entries": {
      "shield-gate": { "enabled": true },
      "r-awareness": { "enabled": true },
      ...
    }
  }
}
```

- `plugins.allow` = whitelist of permitted plugin IDs (anything not listed is blocked)
- `plugins.entries` = per-plugin config (enabled, options)
- `plugins.slots.contextEngine` = `lossless-claw` (LCM manages compaction)

### 6.5 Shield Gate Layers (16 Blocking)

| # | Layer | Scope |
|---|-------|-------|
| 1 | Destructive Command Check | exec: rm, chmod, kill, etc. |
| 1.5 | Delegation Gate | exec: codex delegation |
| 2 | Coherence Gate Enforcement | all tools: task coherence |
| 3 | Direct Coding Gate | exec/write: blocks direct code file creation |
| 4 | Context Isolation Gate | read/write: memory safety |
| 5 | Research Discipline Gate | web_search: complexity check |
| 6a | Repo Contamination Gate | exec/write: cross-repo safety |
| 6b | Verification Claim Gate | message: "fixed" without evidence |
| 6c | State Consistency Gate | message: single-source state claims |
| 6d | Atomic Rebuild Gate | write/exec: non-atomic replacements |
| 6e | Config Change Gate | exec: openclaw.json modifications |
| 6f | Model Selection Gate | sessions_spawn: model hierarchy |
| 6g | Behavioral Integrity Gate | all: anti-bypass detection |
| 6l | Derivative Protection Gate | write: blocks direct .ai.md edits when .md exists |
| 7 | External Action Gate | message/exec: external communications |
| 8 | Post-Compaction Recovery Gate | all: context loss detection |
| 10 | Network Allowlist Gate | web_fetch: domain allowlist/blocklist (31 allowed, 10 blocked, fail-closed) |
| 11 | Sensitive Path Protection Gate | read/write/edit/exec: blocks sub-agent access to credential paths (25 patterns, main exempt) |

### 6.6 Legacy Code Locations

Shield-gate was originally at `~/resonantos-alpha/shield/shield-gate.js`. The canonical copy is now `extensions/shield-gate/index.js`. The `shield/` directory also contains `file_guard.py` (macOS `chflags schg` file protection — separate from the plugin) and `daemon.py` (Shield daemon on port 9999).

## 7. Current State

| Item | Status |
|------|--------|
| OpenClaw Gateway | Running, configured |
| Telegram | Paired, working |
| SSoT L0 | 6 documents (all DRAFT, need revision) |
| SSoT L1 | This document + OLD v1 specs for reference |
| Compression | Working (Haiku sub-agent) |
| R-Memory v2 | Design phase (OpenClaw mapping needed) |
| Token optimization | Haiku for heartbeat/subagents, compressed docs |

## 7. References

| Document | Contents |
|----------|----------|
| SSOT-L0-OVERVIEW-DRAFT.md | What ResonantOS is, who, why |
| SSOT-L1-SHIELD-OLD.md | v1 Shield spec (reference) |
| SSOT-L1-LOGICIAN-OLD.md | v1 Logician spec (reference) |
| SSOT-L1-R-MEMORY-OLD.md | v1 R-Memory spec (reference) |
| SSOT-L1-R-AWARENESS-OLD.md | v1 R-Awareness spec (reference) |
| SSOT-L1-MEMORY-SST-OLD.md | Memory taxonomy & R-Memory v2 design |
