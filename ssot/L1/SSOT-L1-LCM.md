# LCM — Lossless Context Management

**Version:** 0.7.0
**Plugin:** `@martian-engineering/lossless-claw`
**Status:** Active — primary context engine
**DB:** `~/.openclaw/lcm.db` (SQLite)
**Source:** [github.com/Martian-Engineering/lossless-claw](https://github.com/Martian-Engineering/lossless-claw)
**Updated:** 2026-04-09

---

## What It Is

LCM replaces OpenClaw's built-in sliding-window compaction with a DAG-based summarization system. When conversations grow beyond the context window, instead of truncating old messages, LCM summarizes them into a hierarchy of summaries. Raw messages stay in SQLite. Nothing is lost.

## Core Principle

> Compaction, not truncation. Every message is persisted. Summaries link back to source. Agents can drill into any summary to recover original detail.

---

## Architecture

### Data Model

```
Messages (raw, persisted in SQLite)
    ↓ leaf compaction (chunks of ~20K tokens)
Leaf Summaries (depth 0, ~800-1200 tokens each)
    ↓ condensation (groups of 4-8 summaries)
Condensed Summaries (depth 1+, ~1500-2000 tokens each)
    ↓ deeper condensation
Higher-Level Summaries (depth 2, 3, ...)
```

This forms a DAG (Directed Acyclic Graph). Each summary links to its sources (messages or lower summaries). Agents navigate the DAG via tools.

### Context Assembly (per turn)

```
[summary_1, summary_2, ..., summary_n, message_1, message_2, ..., message_m]
 |-- budget-constrained -----------|  |---- fresh tail (protected) -----|
```

1. Fetch all context_items ordered by ordinal
2. Split into evictable prefix (summaries) + protected fresh tail (last N raw messages)
3. Fill remaining token budget from evictable set, newest first
4. Summaries wrapped in XML with metadata (id, kind, depth, time range)

### Compaction Lifecycle

**Incremental (after each turn):**
- If raw tokens outside fresh tail exceed leafChunkTokens -> run one leaf pass
- If incrementalMaxDepth != 0 -> cascade condensation passes
- Best-effort: failures don't break conversation

**Three-level escalation per summary attempt:**
1. Normal (temperature 0.2, standard prompt)
2. Aggressive (temperature 0.1, facts-only prompt)
3. Fallback (deterministic truncation to ~512 tokens)

Compaction always makes progress.

### Large File Handling

Files > 25K tokens are intercepted at ingestion, stored to ~/.openclaw/lcm-files/, replaced with a compact reference + ~200 token exploration summary. Retrievable via lcm_describe(id: "file_xxx").

---

## Agent Tools

| Tool | Purpose | Speed | Cost |
|------|---------|-------|------|
| lcm_grep | Search messages/summaries by regex or full-text | Fast (DB query) | Cheap |
| lcm_describe | Inspect a specific summary or stored file | Fast (DB query) | Cheap |
| lcm_expand_query | Deep recall: sub-agent walks DAG, answers question | ~30-120s | Moderate |
| lcm_expand | Low-level DAG walker (sub-agents only) | n/a | n/a |

**Escalation pattern:** grep -> describe -> expand_query. Start cheap, go deeper only when needed.

**Summary footers:** Each summary block ends with "Expand for details about:" listing what was compressed away. Use lcm_expand_query with that summary's ID to recover details.

---

## Configuration

Plugin config in openclaw.json under plugins.entries.lossless-claw.config:

### Key Parameters

| Parameter | Default | Our Setting | Description |
|-----------|---------|-------------|-------------|
| contextThreshold | 0.75 | 0.75 | Fraction of context window triggering compaction |
| freshTailCount | 32 | 20 | Recent messages protected from compaction |
| incrementalMaxDepth | 0 | 2 | Condensation depth (-1 = unlimited cascade, 0 = leaf only, N = N levels max) |
| leafChunkTokens | 20000 | default | Max source tokens per leaf chunk |
| leafTargetTokens | 1200 | default | Target tokens for leaf summaries |
| condensedTargetTokens | 2000 | default | Target tokens for condensed summaries |
| leafMinFanout | 8 | default | Min messages per leaf summary |
| condensedMinFanout | 4 | default | Min summaries per condensed node |

**⚠️ Bounded depth required:** `incrementalMaxDepth: 3` (max 3 condensation levels). With unlimited depth (-1), the DAG grows indefinitely and all summary nodes get loaded into `context_items` → context window bloat. Use `incrementalMaxDepth: 0` for leaf-only, or a positive integer for a specific depth cap. Default (0) accumulates summaries at depth 0 and wastes context space.

### Environment Variables (override config)

| Variable | Description |
|----------|-------------|
| LCM_SUMMARY_MODEL | Model for summarization (defaults to agent's model) |
| LCM_PRUNE_HEARTBEAT_OK | Delete HEARTBEAT_OK cycles from storage |
| LCM_AUTOCOMPACT_DISABLED | Disable auto-compaction |

---

## Setup Agent — Required Config Values

When the setup agent installs LCM for a new user, apply these settings. Do not use defaults.

```json
"plugins": {
  "entries": {
    "lossless-claw": {
      "enabled": true,
      "config": {
        "freshTailCount": 32,
        "contextThreshold": 0.75,
        "incrementalMaxDepth": 3
      }
    }
  }
}
```

**Key rules:**
- `incrementalMaxDepth: 2` — must be bounded. Default (0) accumulates summaries at depth 0. Unlimited (-1) creates infinite DAG layers and context_items bloat. Use `incrementalMaxDepth: 0` for leaf-only, or a positive integer for a specific depth cap.
- `freshTailCount: 20` — protects 20 most recent messages from compaction. Lower values risk losing conversation continuity.
- `contextThreshold: 0.75` — triggers compaction at 75% context fill. Safe default, do not increase above 0.85.

**`maxExpandTokens` history:** Present in 0.5.2 schema, removed in 0.5.3 (causing validation failures if set), re-added in 0.7.0. Currently safe to set.

**Why bounded depth matters:** Each condensation level combines 4-8 child summaries into a parent. With unlimited depth, the DAG grows indefinitely and ALL summary nodes load into `context_items` — which feeds directly into the model's context window. The bloat event (Mar 2026) produced 7,359 context_items entries and ~350K token context files.

**Fresh install note:** The `context_items` table only needs clearing on existing installations migrating from unbounded depth. New installations start clean.

---

## Current State (2026-03-27)

| Metric | Value |
|--------|-------|
| Conversations | 350 |
| Messages stored | 23,013 |
| Summaries | 342 |
| context_items | 0 (cleared after bloat incident) |
| Message tokens | ~9.8M chars (~2.5M tokens) |
| Summary tokens | ~266K chars (~65K tokens) |
| DB path | ~/.openclaw/lcm.db |
| DB size | 295 MB |
| Plugin version | 0.5.2 |
| **Critical fix** | `incrementalMaxDepth: 3` — was -1 (unlimited) causing context_items bloat (7,359 entries → context window overflow) |

---

## Relationship to Other Memory Systems

```
+--------------------------------------------------+
|              Active Context Window                |
|  +----------------+  +-------------------------+ |
|  | LCM Summaries  |  | Fresh Tail (32 msgs)    | |
|  | (DAG nodes)    |  | (raw, protected)        | |
|  +-------+--------+  +-------------------------+ |
|          |                                        |
|  +-------v--------+  +-------------------------+ |
|  | R-Awareness    |  | MEMORY.md               | |
|  | (SSoT inject)  |  | (permanent, ~15K)       | |
|  | + Headers      |  |                         | |
|  +----------------+  +-------------------------+ |
+--------------------------------------------------+
         | expand_query
         v
+--------------------------------------------------+
|              LCM SQLite Database                  |
|  Raw messages + DAG summaries (nothing lost)      |
+--------------------------------------------------+
         | memory_search
         v
+--------------------------------------------------+
|              RAG (memory-core)                    |
|  SQLite-vec embeddings + FTS5                     |
|  Indexes: SSoT, memory/, research/                |
+--------------------------------------------------+
```

- **LCM** = in-session context management (compaction + retrieval)
- **R-Awareness** = session cold-start injection (SSoT docs + memory log headers)
- **RAG (memory-core)** = cross-session semantic search (independent of LCM)
- **MEMORY.md** = permanent curated memory (always in context)

LCM and RAG are orthogonal. LCM manages what the model sees in conversation. RAG provides searchable knowledge across sessions.

---

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Replace native compaction, don't layer on top | Native compaction is lossy and unrecoverable |
| DAG over flat summaries | Enables targeted expansion — drill into specific time ranges |
| incrementalMaxDepth: 3 | Bounded condensation (3 levels max) prevents unbounded DAG growth |
| freshTailCount: 32 | Enough recent context for continuity |
| Three-level escalation | Compaction always makes progress, even on bad LLM output |
| contextThreshold: 0.75 | Leaves 25% headroom for model response |
| Large file interception | Single file paste doesn't consume entire context |
| XML wrapper format | Gives model metadata for reasoning about summary age/scope |
| Session reconciliation | Crash recovery via JSONL comparison |

---

## Update History

| Version | Date | Key Changes |
|---------|------|-------------|
| 0.1.4 | 2026-03-07 | Initial install, first day of release |
| 0.4.0 | 2026-03-22 | LCM 0.4.0 release |
| 0.5.1 | 2026-03-24 | LCM 0.5.1 |
| 0.5.2 | 2026-03-26 | LCM 0.5.2 — critical fix: incrementalMaxDepth: -1 enables unlimited cascade condensation |
| config | 2026-03-27 | incrementalMaxDepth: -1 → 3 (bounded). Was causing context_items bloat (7,359 entries). freshTailCount: 4 → 32. Added Setup Agent section. |
| schema | 2026-03-28 | Added maxExpandTokens (type:number, default:4000) to configSchema.properties. Added to config parameters table. |
| 0.5.3 | 2026-04-03 | **UPGRADED:** maxExpandTokens REMOVED from configSchema (present in 0.5.2, gone in 0.5.3). New schema properties: statelessSessionPatterns, skipStatelessSessions, largeFileThresholdTokens, summaryModel, summaryProvider, expansionModel, expansionProvider, delegationTimeoutMs, maxAssemblyTokenBudget, summaryMaxOverageFactor, customInstructions, leafChunkTokens, leafMinFanout, condensedMinFanout, condensedMinFanoutHard. Removed maxExpandTokens from schema — must delete from config if present. Config fixed: removed maxExpandTokens:4000 (was causing schema validation failure). |
| 0.7.0 | 2026-04-09 | **UPGRADED:** Major release. maxExpandTokens RE-ADDED to configSchema (was removed in 0.5.3, restored in 0.7.0). Plugin deps updated: @mariozechner/pi-agent-core, @mariozechner/pi-ai, @sinclair/typebox 0.34.48. New features: cache-aware compaction (cacheAwareCompaction object), dynamic leaf chunk tokens (dynamicLeafChunkTokens object), circuit breaker (circuitBreakerThreshold, circuitBreakerCooldownMs), bootstrapMaxTokens, newSessionRetainDepth, largeFileSummaryModel, largeFileSummaryProvider, summaryTimeoutMs, fallbackProviders, timezone, pruneHeartbeatOk, largeFileTokenThreshold alias. Note: maxExpandTokens is now safe to set again. |
