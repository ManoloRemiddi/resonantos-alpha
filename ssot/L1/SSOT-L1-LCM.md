# LCM — Lossless Context Management

**Version:** 0.5.2
**Plugin:** `@martian-engineering/lossless-claw`
**Status:** Active — primary context engine
**DB:** `~/.openclaw/lcm.db` (SQLite)
**Source:** [github.com/Martian-Engineering/lossless-claw](https://github.com/Martian-Engineering/lossless-claw)
**Updated:** 2026-03-26

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
| freshTailCount | 32 | 32 | Recent messages protected from compaction |
| incrementalMaxDepth | 0 | -1 | Condensation depth (-1 = unlimited cascade) |
| leafChunkTokens | 20000 | default | Max source tokens per leaf chunk |
| leafTargetTokens | 1200 | default | Target tokens for leaf summaries |
| condensedTargetTokens | 2000 | default | Target tokens for condensed summaries |
| leafMinFanout | 8 | default | Min messages per leaf summary |
| condensedMinFanout | 4 | default | Min summaries per condensed node |

**Critical setting:** incrementalMaxDepth: -1 enables unlimited automatic condensation. Without it (default 0), summaries accumulate at depth 0 and never get condensed — wasting context space.

### Environment Variables (override config)

| Variable | Description |
|----------|-------------|
| LCM_SUMMARY_MODEL | Model for summarization (defaults to agent's model) |
| LCM_PRUNE_HEARTBEAT_OK | Delete HEARTBEAT_OK cycles from storage |
| LCM_AUTOCOMPACT_DISABLED | Disable auto-compaction |

---

## Current State (2026-03-14)

| Metric | Value |
|--------|-------|
| Conversations | 126 |
| Messages stored | 14,579 |
| Summaries | 252 |
| This session messages | 5,124 |
| This session summaries | 104 |
| DB path | ~/.openclaw/lcm.db |
| Plugin version | 0.2.5 -> 0.3.0 (updating) |
| FTS5 | Not compiled in (falls back to LIKE search) |

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
| incrementalMaxDepth: -1 | Prevents summary accumulation at depth 0 |
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
| 0.2.5 | 2026-03-14 | Pre-update audit version |
| 0.3.0 | 2026-03-12 | Latest release, 11 contributors, updating today |
