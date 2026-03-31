# SSOT-L1-MEMORY-ARCHITECTURE — Memory System Overview

**Level:** L1 (Architecture)  
**Last Updated:** 2026-03-07  
**Status:** Active

---

## Overview

ResonantOS has three distinct memory systems, each with a specific purpose. This document provides an overview of all three.

## The Three Memory Systems

### 1. R-Memory (Temporarily Disabled)

**Purpose:** Conversation compression and context management.

**Status:** Temporarily disabled (2026-03-06) — incompatible with latest OpenClaw version. Under investigation.

**Function:**
- Compresses old conversation blocks when context fills up
- Uses lossy compression to summarize history
- Manages FIFO eviction of oldest compressed blocks

**Location:** `~/.openclaw/extensions/r-memory.js`

---

### 2. Memory Log

**Purpose:** Long-term memory of key decisions, insights, and human-AI collaboration sessions.

**Format:**
```markdown
# YYYY-MM-DD — Shared Memory Log

LOG ENTRY: [thesis/insight]
- Origin:
- Thesis:
- Validation:

MEMORY LOG ENTRY [date] - [time]
PART 1: PROCESS LOG (THE "STRATEGIC VIEW")
- Human Practitioner's Core Input:
- AI Analysis:
- Key Decisions & Failures:
- Pivotal Insights:
- Final Output:

PART 2: FINE-TUNING DATASET (THE "MACHINE VIEW")
[TRAINING PAIR N]
- [CONTEXT]:
- [PROMPT_VIOLATION]:
- [CORRECTED_POLICY]:
```

**Location:** `~/.openclaw/workspace/memory/shared-log/`

**Created by:** Memory Archivist (cron job at 05:30 daily)

---

### 3. Knowledge Base (RAG)

**Purpose:** Per-agent vector search database for retrieval-augmented generation.

**Features:**
- Per-agent SQLite databases with embeddings
- Local Ollama embedding model (nomic-embed-text)
- Configurable SSoT access per agent (L0/L1/L2)
- Common KB for shared knowledge across agents
- File upload/delete via Dashboard

**Location:** `~/.openclaw/memory/{agent}.sqlite`

**Access:** Dashboard → Settings → Knowledge Base

---

## Comparison Table

| System | Purpose | Storage | Access |
|--------|---------|---------|--------|
| R-Memory | Context compression | In-context | Automatic |
| Memory Log | Long-term decisions | `memory/shared-log/` | Read by archivist |
| Knowledge Base | Semantic search | SQLite vectors | RAG queries |

---

## Memory Archivist

The Memory Archivist is a cron job that runs daily at 05:30 (Rome time):

1. Scans SSoT hierarchy (L1-L4)
2. Generates drift detection report
3. Extracts key decisions from last 24h
4. Creates Memory Log entry in `memory/shared-log/YYYY-MM-DD.md`

**Cron ID:** `6d2e225f-26ca-4d53-9d3f-742b59b200c6`

---

## Related SSoTs

- `SSOT-L1-R-MEMORY.md` — R-Memory technical spec (may need update)
- `SSOT-L1-RAG-SYSTEM.md` — Knowledge Base / RAG system
- `MEMORY.md` — Long-term memory of identity and philosophy
