# R-Memory V6 — Conversation Memory System

**Version:** 6.0.0  
**Status:** Production (Active)  
**Extension:** `~/.openclaw/extensions/r-memory-v6/index.js`  
**Plugin manifest:** `~/.openclaw/extensions/r-memory-v6/openclaw.plugin.json`  
**Updated:** 2026-03-05  
**Supersedes:** R-Memory V5.2.0 (backed up to `ssot/older/SSOT-L1-R-MEMORY-V5.2.md`)

---

## What It Is

R-Memory is a **global OpenClaw extension** that replaces OpenClaw's built-in lossy compaction with a high-fidelity memory system. It provides:

1. **Lossless compression** — old conversation is compressed (not summarized) to preserve decisions, facts, code, and file paths
2. **Evolving narrative** — a persistent working memory document that survives context resets, preventing AI drift
3. **Context injection** — narrative and compressed history are automatically injected at the start of each turn
4. **Multi-agent support** — runs independently per agent, with per-agent config, logs, archives, and narrative files

## Core Principle

> Compression, not summarization. The AI should never lose critical information. OpenClaw's lossy compaction fallback should never run.

---

## Architecture Overview

R-Memory V6 is a **global extension** installed at `~/.openclaw/extensions/r-memory-v6/`. Unlike V5 which was a per-agent extension, V6 registers globally and operates on whichever agent triggers it, identified by `ctx.agentId`.

### Data Flow

```
Each turn completes (agent_end fires)
    ├→ Archive: If total tokens > compressTrigger, overflow messages saved to disk
    ├→ Compress: Overflow text sent to compression model → appended to compressed-summary.md
    └→ Narrative: Recent messages (6k tokens) + existing narrative → model updates narrative.md

Next turn begins (before_agent_start fires)
    └→ Inject: narrative.md + compressed-summary.md prepended to context

OpenClaw triggers compaction (session_before_compact fires)
    └→ R-Memory intercepts → provides file-based summary (narrative + compressed) → prevents lossy fallback
```

### The Three Hooks

| Hook | When | What R-Memory Does |
|------|------|-------------------|
| `before_agent_start` | Before each AI turn | Injects narrative (≤6k chars) + compressed history (≤4k chars) into context via `prependContext` |
| `agent_end` | After AI response complete | Archives overflow, compresses overflow, updates narrative (all async, non-blocking) |
| `session_before_compact` | OpenClaw triggers compaction | Provides file-based summary from narrative + compressed files, preventing lossy fallback |

### The Two Background Models

| Agent | Model | Purpose | Fires |
|-------|-------|---------|-------|
| **Compression** | `minimax/MiniMax-M2.5` | Compress overflow conversation blocks | `agent_end` (when tokens > trigger) |
| **Narrative** | `minimax/MiniMax-M2.1` | Maintain evolving narrative document | `agent_end` (every turn) |

Both run asynchronously (fire-and-forget) via `Promise.resolve().then(...)` and never block the main conversation.

---

## Multi-Agent Support

V6 is agent-aware. Each agent gets its own isolated data:

| Agent Data | Path Pattern |
|------------|-------------|
| Config | `~/.openclaw/agents/{agentId}/agent/r-memory/config.json` |
| Log | `~/.openclaw/agents/{agentId}/agent/r-memory/r-memory.log` |
| Narrative | `~/.openclaw/agents/{agentId}/agent/r-memory/narrative.md` |
| Compressed | `~/.openclaw/agents/{agentId}/agent/r-memory/compressed-summary.md` |
| Archives | `~/.openclaw/agents/{agentId}/agent/memory/archive/` |
| Usage stats | `~/.openclaw/agents/{agentId}/agent/r-memory/usage-stats.json` |
| Training data | `~/.openclaw/agents/{agentId}/agent/r-memory/training-data/{compression,narrative}/pairs.jsonl` |

### Enabling Per Agent

To enable R-Memory on an agent, create `r-memory/config.json` in the agent's directory:

```json
{
  "enabled": true,
  "compressTrigger": 15000,
  "compressedCeiling": 50000,
  "compressionModel": "minimax/MiniMax-M2.5",
  "narrativeModel": "minimax/MiniMax-M2.1",
  "narrativeMaxTokens": 2400,
  "minCompressChars": 200
}
```

If the config file doesn't exist or `enabled` is not `true`, all hooks are no-ops for that agent.

### Currently Active Agents

| Agent | Status | Purpose |
|-------|--------|---------|
| `main` | Active | Primary orchestrator (Manolo ↔ Augmentor) |
| `voice` | Active | Voice assistant agent |

---

## How It Works — Step by Step

### 1. Context Injection (before_agent_start)

At the start of every turn:
1. Read `r-memory/narrative.md` — if >100 chars, include (capped at 6k chars)
2. Read `r-memory/compressed-summary.md` — if >50 chars, include (capped at 4k chars)
3. Wrap in `<!-- R-Memory V6: Context -->` comment and inject via `prependContext`

This gives the AI its memory state before processing the user's message.

### 2. Archive Overflow (agent_end → subtaskArchiveRawBlocks)

After each AI response:
1. Extract all messages into text entries with token estimates (chars/4)
2. Compute total tokens across all entries
3. If total ≤ `compressTrigger`: skip (nothing to archive)
4. If total > `compressTrigger`: identify overflow entries (oldest messages that exceed the budget)
5. Write overflow entries to `memory/archive/rmem-{timestamp}-{hash}.md`
6. Log the archive event

Archive files are **never deleted** — they're the raw backup.

### 3. Compress Overflow (agent_end → subtaskCompressOverflow)

Runs in parallel with archiving:
1. Same overflow detection as archive step
2. If overflow text < `minCompressChars` (200): skip
3. Send overflow text (capped at 32k chars) to compression model
4. Append compressed output as a new timestamped section in `compressed-summary.md`
5. Apply FIFO ceiling: if total compressed text exceeds `compressedCeiling` tokens, drop oldest sections
6. Log training pair for future fine-tuning

### 4. Update Narrative (agent_end → subtaskUpdateNarrative)

Runs in parallel with archive and compression:
1. Extract recent messages (last ~6k tokens worth)
2. Sanitize: remove tool calls, JSON blocks, metadata, PRESERVE_VERBATIM tags
3. Build prompt: existing narrative + sanitized recent conversation
4. Send to narrative model with structured prompt (see Narrative Format below)
5. Write result to `r-memory/narrative.md` with timestamp header
6. Log training pair for future fine-tuning

### 5. Compaction Interception (session_before_compact)

When OpenClaw decides to compact:
1. Read `narrative.md` and `compressed-summary.md` from disk
2. Build a combined summary document
3. Return `{ compaction: { summary, firstKeptEntryId } }` — this replaces OpenClaw's lossy compaction
4. **R-Memory never returns undefined here** — it always provides its own summary or lets OpenClaw proceed only on error

---

## Narrative Format

The narrative model produces a structured document with these mandatory sections:

```markdown
## NOW
3-5 sentences. What is happening RIGHT NOW.

## WHY
The strategic goal driving current work.

## HOW
Technical approach, architecture decisions, what failed and why.

## Session
One paragraph. Arc of the session so far.

## Rivers
Active topic streams with status (active/paused/resolved).

## Decisions
Accumulative bullet list. Never removes old decisions.

## Queue
Pending tasks.

## Errors
Active problems. Removed only when resolved with evidence.
```

Key rules:
- Max 1000 words
- **Evolves** from previous narrative (not rewritten from scratch)
- Third person (separate observer)
- Specific: file paths, model names, versions, config values
- Failed approaches preserved (more valuable than successes)

---

## Token Budget and Triggers

| Parameter | Default | Config Key | Description |
|-----------|---------|-----------|-------------|
| Compress trigger | 15,000 tokens | `compressTrigger` | When total message tokens exceed this, overflow is archived and compressed |
| Compressed ceiling | 50,000 tokens | `compressedCeiling` | Max tokens for compressed history; oldest sections evicted via FIFO |
| Min compress chars | 200 | `minCompressChars` | Overflow smaller than this skipped (not worth compressing) |
| Narrative max tokens | 2,400 | `narrativeMaxTokens` | Max output tokens for both narrative and compression model calls |
| Injection cap (narrative) | 6,000 chars | hardcoded | Max narrative chars injected per turn |
| Injection cap (compressed) | 4,000 chars | hardcoded | Max compressed chars injected per turn |

### Token Estimation

R-Memory uses `Math.ceil(text.length / 4)` as its token estimate. This is intentionally approximate — accurate enough for threshold decisions without requiring a tokenizer dependency.

---

## API Key Resolution

Background model calls need API keys. R-Memory resolves them in this order:

1. **Environment variables** — e.g., `MINIMAX_API_KEY`
2. **Auth profiles** — `~/.openclaw/agents/main/agent/auth-profiles.json` (searches by provider name)
3. **Credentials directory** — `~/.openclaw/credentials/*.json` (searches by provider match)

The `main` agent's auth-profiles.json is used as the canonical key store regardless of which agent is running (all agents share the same API keys).

---

## Connection to OpenClaw

### Extension Registration

R-Memory V6 is a standard OpenClaw plugin:

```
~/.openclaw/extensions/r-memory-v6/
├── openclaw.plugin.json    # Plugin manifest (name, version, entry point)
├── index.js                # Extension code
└── TASK.md                 # Development notes
```

OpenClaw auto-discovers plugins in `~/.openclaw/extensions/*/openclaw.plugin.json` and loads them at gateway startup.

### Interaction with OpenClaw Compaction

OpenClaw has built-in compaction that fires when context grows too large. R-Memory **intercepts** this via the `session_before_compact` hook:

- R-Memory provides its own summary (from files on disk) → OpenClaw uses that instead of its default lossy summarization
- If R-Memory fails, it returns `undefined` and OpenClaw falls back to its default (this is the safety net, not the normal path)
- The `firstKeptEntryId` from OpenClaw's preparation is passed through to preserve message boundaries

### Interaction with OpenClaw Memory Search

Archived blocks in `memory/archive/rmem-*.md` are indexed by OpenClaw's semantic memory search (`memory_search` tool). Evicted conversation isn't lost — it's out of the context window but still discoverable via search.

### Interaction with Agent Settings

Agents can configure OpenClaw's native compaction thresholds in `settings.json`:

```json
{
  "compaction": {
    "enabled": true,
    "reserveTokens": 20000,
    "keepRecentTokens": 15000
  }
}
```

R-Memory's `compressTrigger` should be set **below** OpenClaw's compaction trigger to ensure R-Memory handles overflow before OpenClaw's compaction fires.

---

## Training Data Collection

Both agents log input/output pairs for future fine-tuning:

| Agent | File | Format |
|-------|------|--------|
| Compression | `r-memory/training-data/compression/pairs.jsonl` | `{timestamp, agentId, model, input, output, metadata}` |
| Narrative | `r-memory/training-data/narrative/pairs.jsonl` | `{timestamp, agentId, model, input, output, metadata}` |

**Purpose:** Fine-tune small local models (1-4B parameters) to eventually replace MiniMax cloud calls, eliminating per-token costs. Target models: Llama 3.2-1B (compression), Qwen3-4B (narrative).

---

## File Locations (Complete)

| File | Path | Purpose |
|------|------|---------|
| Extension code | `~/.openclaw/extensions/r-memory-v6/index.js` | The extension |
| Plugin manifest | `~/.openclaw/extensions/r-memory-v6/openclaw.plugin.json` | OpenClaw auto-discovery |
| Agent config | `~/.openclaw/agents/{id}/agent/r-memory/config.json` | Per-agent settings |
| Agent log | `~/.openclaw/agents/{id}/agent/r-memory/r-memory.log` | Activity log |
| Narrative | `~/.openclaw/agents/{id}/agent/r-memory/narrative.md` | Evolving working memory |
| Compressed | `~/.openclaw/agents/{id}/agent/r-memory/compressed-summary.md` | Compressed history blocks |
| Archives | `~/.openclaw/agents/{id}/agent/memory/archive/rmem-*.md` | Raw overflow backups (never deleted) |
| Usage stats | `~/.openclaw/agents/{id}/agent/r-memory/usage-stats.json` | API call tracking |
| Training (compression) | `~/.openclaw/agents/{id}/agent/r-memory/training-data/compression/pairs.jsonl` | Fine-tuning data |
| Training (narrative) | `~/.openclaw/agents/{id}/agent/r-memory/training-data/narrative/pairs.jsonl` | Fine-tuning data |
| Debug (narrative input) | `~/.openclaw/agents/{id}/agent/r-memory/narrative-input-debug.txt` | Debug artifact |
| Debug (narrative response) | `~/.openclaw/agents/{id}/agent/r-memory/narrative-response-debug.json` | Debug artifact |

---

## Configuration Reference

File: `r-memory/config.json` (per agent)

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | boolean | `true` | Enable/disable R-Memory for this agent |
| `compressionModel` | string | `minimax/MiniMax-M2.5` | Model for compression calls |
| `narrativeModel` | string | `minimax/MiniMax-M2.1` | Model for narrative calls |
| `narrativeMaxTokens` | number | `2400` | Max output tokens for model calls |
| `compressTrigger` | number | `15000` | Token threshold to trigger archiving + compression |
| `compressedCeiling` | number | `50000` | Max tokens for compressed history (FIFO eviction above this) |
| `minCompressChars` | number | `200` | Skip compression if overflow text below this char count |

---

## Key Design Decisions (V6)

| Decision | Rationale |
|----------|-----------|
| Global extension (not per-agent) | Single codebase, multi-agent via `ctx.agentId`. Simpler deployment and updates. |
| File-based compaction summary | Reads narrative + compressed from disk at compaction time. No complex in-memory state. Survives gateway restarts. |
| `narrative.md` in `r-memory/` dir | Keeps narrative scoped to R-Memory's data directory, not mixed with agent workspace files |
| 15K token trigger | Tested value for voice agent. Ensures ~15K raw tokens always remain in context for natural interaction. |
| MiniMax models | Cheap, fast, good enough for structured compression and narrative. Zero subscription cost impact. |
| Async fire-and-forget | Archive, compress, and narrative run in parallel without blocking the user's next turn |
| FIFO eviction on compressed | Deterministic — no AI deciding what's "important". Oldest compressed blocks removed first. |
| Training data collection | Every compression and narrative call logged for future local model fine-tuning |
| Auth key resolution chain | ENV → auth-profiles → credentials dir. Uses main agent's auth as canonical store. |
| **Archive sanitization (V6 CONSTRAINT)** | Archives written to `memory/archive/` get indexed by RAG. V5 archives contained tool call JSON, `PRESERVE_VERBATIM` tags, AAAA padding, and thinking blocks — degraded retrieval quality. **V6 MUST sanitize archive content before writing:** strip tool calls, XML wrapper tags, padding, and non-human-readable artifacts. Clean text only. This is a hard requirement if R-Memory is re-enabled. |

---

## Differences from V5.2

| Aspect | V5.2 | V6 |
|--------|------|-----|
| Installation | Per-agent (`extensions/r-memory.js`) | Global (`~/.openclaw/extensions/r-memory-v6/`) |
| Agent support | Single agent | Multi-agent (via `ctx.agentId`) |
| Narrative location | `SESSION_THREAD.md` (agent root) | `r-memory/narrative.md` (scoped to R-Memory dir) |
| Block system | Hash-based block cache, background pre-compression | Simple overflow detection, on-demand compression |
| Compaction trigger | 36,000 tokens | 15,000 tokens (configurable per agent) |
| FIFO ceiling | 80,000 tokens | 50,000 tokens (configurable per agent) |
| Camouflage routing | Yes (traffic segregation) | Removed (unnecessary complexity) |
| Context injection | On-demand read by AI | Automatic via `before_agent_start` + `prependContext` |
| Compression model | gpt-4o-mini | minimax/MiniMax-M2.5 |
| Narrative model | Opus (free via subscription) | minimax/MiniMax-M2.1 |
| Compaction interception | Complex block-swap logic | File-based summary (read from disk) |

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 6.0.0 | 2026-03-05 | Complete rewrite. Global extension, multi-agent, file-based compaction, narrative in r-memory dir, simplified architecture. |
| 5.2.0 | 2026-03-02 | Last per-agent version. Input sanitization, SESSION_THREAD.md auto-injection. |
| 5.0.1 | 2026-02-20 | Training data collection, narrative model → Opus. |
| 4.8.1 | 2026-02-20 | Camouflage routing (traffic segregation). |
| 4.6.3 | 2026-02-19 | Multi-provider support, background agent tracking. |
