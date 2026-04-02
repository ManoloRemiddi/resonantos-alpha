# SSOT-L1-SHIELD — Shield Security System
Updated: 2026-03-27

| Field | Value |
|-------|-------|
| ID | SSOT-L1-SHIELD-V3 |
| Created | 2026-02-19 |
| Updated | 2026-03-27 |
| Author | Augmentor |
| Level | L1 (Architecture) |
| Type | Truth |
| Status | Active |
| Replaces | SSOT-L1-SHIELD-V2 |
| Stale After | 90 days |

---

## 1. Overview

Shield is ResonantOS's security enforcement layer. It operates as a multi-component system that:

1. **Gates AI behavior** — 14 blocking layers intercept tool calls, messages, and agent spawning (via OpenClaw plugin hooks)
2. **Gates git pushes** — blocks pushes containing leaked credentials, unverified code, or Logician-denied repos
3. **Protects files** — locks critical files (cross-platform: macOS `chflags`, Linux `chattr`, POSIX `chmod`)
4. **Scans for data leaks** — regex-based detection of credentials, private content, business secrets
5. **Enforces verification** — blocks completion claims without evidence (Layer 6k) and SSoT freshness (Layer 6j)

Shield is **deterministic** — no AI involved in security decisions. Pure regex, pattern matching, and Logician queries.

## 2. Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    ENFORCEMENT CHAIN                     │
│                                                          │
│  Tool Call ──► shield-gate plugin ──► 14 LAYERS          │
│                    │    (before_tool_call,                │
│                    │     message_sending,                 │
│                    │     subagent_spawning,               │
│                    │     after_compaction)                │
│                    ▼                                     │
│               ALLOW / BLOCK + turnEvidence tracking       │
│                                                          │
│  Git Push ──► pre-push hook                              │
│                 ├── data_leak_scanner.py (scan diff)     │
│                 ├── Logician query (safe_path + git)     │
│                 └── pre-push secret scanner (grep)       │
│                                                          │
│  Files ──► file_guard.py ──► chflags/chattr/chmod        │
│                                                          │
│  Hooks ──► hook_guardian.sh ──► self-healing monitor      │
└─────────────────────────────────────────────────────────┘
         │
         ▼
    Logician (proxy :8081 / Mangle socket)
```

## 3. Shield Gate Plugin (14 Layers)

**Type:** OpenClaw plugin (hooks: `before_tool_call`, `message_sending`, `subagent_spawning`, `after_compaction`)
**Location:** `~/.openclaw/extensions/shield-gate/index.js` (~2,000 lines)
**Purpose:** Intercept and gate all AI tool calls, outbound messages, and agent spawns

### 3.1 Layer Registry

| Layer | Name | Hook | Purpose |
|-------|------|------|---------|
| 1 | Destructive Pattern Check | before_tool_call | Blocks `rm -rf`, `DROP TABLE`, `mkfs`, fork bombs, `shutdown` |
| 2 | Protected File Write | before_tool_call | Blocks writes to `.openclaw/openclaw.json`, `.ssh/`, `.env`, Solana keys |
| 3 | Safe Command Fast-Path | before_tool_call | Whitelists `ls`, `cat`, `grep`, `git status/log/diff`, `curl`, etc. |
| 4 | Pipe/Redirect Detection | before_tool_call | Commands with `\|` or `>` skip safe-prefix fast-path |
| 5 | Coherence Gate | before_tool_call | Cross-checks with coherence-gate plugin |
| 6a | Direct Coding Gate | before_tool_call | Blocks writes >300 chars to `.js/.sh/.py` files — must delegate to Codex |
| 6b | Delegation Gate | before_tool_call | Validates TASK.md quality (Root Cause, Fix, Test Command sections, min 100 chars) |
| 6c | State Claim Gate | before_tool_call | Blocks state/number claims without prior verification commands in tool history |
| 6f | Config Change Gate | before_tool_call | Intercepts modifications to `openclaw.json` |
| 6g | Model Selection Hierarchy | before_tool_call | Enforces SOUL.md model preference: free > paid, local > remote |
| 6h | Autonomous Development Gate | before_tool_call | Requires self-debate for design-level work |
| 6i | Memory Log Gate | before_tool_call | Enforces intraday memory log writing |
| 6j | SSoT Freshness Gate | before_tool_call, message_sending | Blocks completion claims when SSoT-significant files were written but no SSoT doc updated |
| 6k | Completion Verification Gate | before_tool_call, message_sending | Blocks completion claims without verification evidence (exec, browser, or file re-read after writes) |
| 9a | Injection Protection | message_sending | Filters outbound messages for credential leaks |

### 3.2 Turn Evidence Tracking

Shield tracks per-session state via `turnEvidence` Map:
- `writes[]` — all file writes with timestamps + sequence numbers
- `execCalls[]`, `toolCalls[]`, `readFiles[]` — tool usage history
- `eventSeq` — monotonic counter for ordering (avoids timestamp collisions)
- `lastWritePath`, `lastSsotRelevantWrite`, `lastSsotDocWrite` — for staleness checks
- `ssotRequiredDocs` Set — which SSoT docs need updating based on file paths changed

**SSoT-Significant Path Mapping:**

| Path Pattern | Required SSoT Doc |
|---|---|
| logician/ | SSOT-L1-LOGICIAN.ai.md |
| shield/, shield-gate/ | SSOT-L1-SHIELD.ai.md |
| extensions/ | SSOT-L1-SYSTEM-OVERVIEW.ai.md |
| dashboard/ | SSOT-L1-DASHBOARD.ai.md |
| openclaw.json, agents/ | SSOT-L1-SYSTEM-OVERVIEW.ai.md |

### 3.3 Completion Claim Detection

Scans outbound messages for patterns: "fixed", "done", "completed", "deployed", "updated", "resolved", "implemented".
Exempt patterns: questions, future tense, planning language, partial claims.

**All gates default to BLOCKING.** Downgrading to advisory requires Manolo's written approval.

## 4. Memory Doorman (Filesystem Sanitizer)

**Purpose:** Structural enforcement at the filesystem level — sanitizes all `.md` files written to memory directories, regardless of source.

**Architecture:** `fswatch` daemon → `sanitize-memory-write.py` → clean file in-place

```
Any process (cron, AI, manual) ──► writes .md to memory/ ──► fswatch detects ──► sanitizer runs ──► clean file
```

**Attack vector blocked:** Malicious content in Telegram message → session history → memory log cron → RAG index → future session injection. The doorman breaks this chain at the filesystem write point.

**Components:**

| File | Purpose |
|------|---------|
| `scripts/sanitize-memory-write.py` | 10-category regex sanitizer (HTML injection, tool XML, base64, prompt injection, verbatim/padding noise) |
| `scripts/memory-doorman.sh` | fswatch wrapper, watches memory dirs, triggers sanitizer |
| `com.resonantos.memory-doorman.plist` | LaunchAgent (KeepAlive, RunAtLoad) |

**Watched paths:**
- `~/.openclaw/workspace/memory/shared-log/` (memory logs)
- `~/.openclaw/workspace/memory/` (daily notes, breadcrumbs excluded by extension filter)

**Sanitizer categories (10):**
1. HTML dangerous tags (script, iframe, style, object, embed, form)
2. Standalone HTML (link, meta, base)
3. Event handler attributes (onclick, onerror, etc.)
4. JavaScript/data URLs
5. Claude tool XML blocks
6. Tool result XML
7. Thinking blocks
8. Base64 blobs (200+ chars)
9. Verbatim/padding noise (PRESERVE_VERBATIM, padding)
10. Prompt injection patterns

**Cross-platform:**

| OS | File watcher | Implementation |
|----|-------------|----------------|
| macOS | `fswatch` (Homebrew) | Current — LaunchAgent |
| Linux | `inotifywait` (inotify-tools) | Same sanitizer, systemd unit instead of LaunchAgent |
| Windows | PowerShell `FileSystemWatcher` | Same sanitizer (Python), scheduled task or service |

The sanitizer script (`sanitize-memory-write.py`) is pure Python with no OS dependencies — only the watcher layer differs per platform.

**Logs:** `/tmp/memory-doorman.log`

## 5. Other Components

### 4.1 Data Leak Scanner (`data_leak_scanner.py`)

**Location:** `~/resonantos-augmentor/shield/data_leak_scanner.py`
**Purpose:** Scan text, files, and git diffs for credential/secret leaks

**Detection categories:** Credentials (API keys, PEM, seed phrases), private content (MEMORY.md, USER.md, SOUL.md markers), business-sensitive docs, forbidden files.

**Logician integration:** Queries `safe_path("<repo>")` and `can_use_tool(/main, /git)`. Fail-closed: Logician unreachable → push denied.

### 4.2 File Guard (`file_guard.py`)

Cross-platform file locking (macOS `chflags`, Linux `chattr`, POSIX `chmod`). Guard manifest covers agent config, extensions, identity, dashboard, shield, SSoT, GitHub hooks. Status checks use `os.stat()` with `st_flags` bitmask (SF_IMMUTABLE|UF_IMMUTABLE) — zero subprocess overhead. Dashboard exposes summary endpoint (`/api/shield/guard/summary`) for fast page loads, with lazy per-group file loading (`/api/shield/guard/group/<key>`).

### 4.3 Hook Guardian (`hook_guardian.sh`)

Monitors pre-push hooks; auto-restores if deleted or tampered. Runs periodically via launchd.

### 4.4 SSoT Staleness Script (`scripts/ssot-staleness-check.sh`)

Scans L0/L1 `.ai.md` files for `Updated:` headers. Flags files >14 days old or missing headers. Outputs JSON to `shield/logs/ssot-staleness.json`. Runs daily at 07:00 Rome via cron.

## 6. Pre-Push Hook Chain

```
1. Shield lock check (is Shield enabled?)
2. Data leak scanner (scan diff for credentials/secrets)
3. Logician approval (safe_path + can_use_tool queries)
4. Secret grep scanner (20+ char suffix patterns)
```

Any step failing → push blocked (exit 1).

## 7. Deployment

| Component | Location | Managed By |
|-----------|----------|------------|
| shield-gate plugin | `~/.openclaw/extensions/shield-gate/index.js` | OpenClaw (plugin, loaded at gateway start) |
| data_leak_scanner.py | `resonantos-augmentor/shield/` | Pre-push hook |
| file_guard.py | `resonantos-augmentor/shield/` | CLI / dashboard API |
| hook_guardian.sh | `resonantos-augmentor/shield/` | launchd |
| shield_lock.py | `resonantos-augmentor/shield/` | CLI (human-only) |
| ssot-staleness-check.sh | `resonantos-augmentor/scripts/` | OpenClaw cron (daily 07:00) |
| sanitize-memory-write.py | `resonantos-augmentor/scripts/` | Memory Doorman (fswatch) |
| memory-doorman.sh | `resonantos-augmentor/scripts/` | LaunchAgent (KeepAlive) |

## 8. Design Principles

1. **Deterministic** — no AI in the security loop; pure regex + Logician rules
2. **Fail-closed for git** — Logician unreachable → push denied
3. **Default-to-strict** — all gates blocking; advisory requires human approval
4. **Self-healing** — hooks auto-restored if tampered
5. **Human-only unlock** — password required to disable Shield
6. **Evidence-based** — completion claims require verification; SSoT changes require doc updates
7. **Cross-platform** — file locking works on macOS and Linux
