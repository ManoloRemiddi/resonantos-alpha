<!-- TEMPLATE: Customize this file for your deployment -->
# R-Awareness — SSoT Context Injection System
Updated: 2026-03-27

**Version:** 3.0
**Status:** Active
**Plugin:** `~/.openclaw/extensions/r-awareness/index.js` (277 lines)
**Manifest:** `~/.openclaw/extensions/r-awareness/openclaw.plugin.json`

| Field | Value |
|-------|-------|
| ID | SSOT-L1-R-AWARENESS-V3 |
| Created | 2026-02-16 |
| Updated | 2026-03-27 |
| Level | L1 (Architecture) |
| Replaces | R-Awareness V1 (disabled, renamed to `.v1-disabled`) |

---

## What It Is

R-Awareness is an OpenClaw plugin that injects SSoT (Single Source of Truth) documents into the AI's system prompt. Two injection modes:

1. **Always-on docs** — curated overviews loaded every turn (cacheable by providers)
2. **Compound keyword scanning** — multi-word phrases in user messages trigger specific SSoT docs per-turn

The AI sees injected content as part of its system prompt — knowledge it already has, not documents to read.

## Core Principle

> Silent success, visible errors. R-Awareness is infrastructure, not a conversational agent.

---

## Architecture (V3)

```
User message arrives
        ↓
before_prompt_build hook fires
        ↓
1. Always-on docs loaded (appendSystemContext — cacheable)
2. User message scanned for compound keywords
3. Matching keyword docs loaded within token budget
        ↓
AI receives: system prompt + always-on SSoT + keyword SSoT
```

### V3 vs V1

| Feature | V1 (Disabled) | V3 (Active) |
|---------|---------------|-------------|
| Hook | `before_agent_start` (legacy) | `before_prompt_build` (modern) |
| Format | OpenClaw extension (single .js) | Plugin with manifest (openclaw.plugin.json) |
| Keywords | Single words | Compound phrases (multi-word) |
| Always-on | coldStartDocs (turn 1 only) | appendSystemContext (every turn, cacheable) |
| TTL eviction | 15 turns per doc | No TTL — keyword docs cleared each turn |
| AI scanning | Disabled (feedback loop) | Removed entirely |
| Lines | 709 | 277 |

---

## Always-On Documents

Loaded every turn via `appendSystemContext` (cacheable by Anthropic, OpenAI, etc.):

| Doc | ~Tokens | Purpose |
|-----|---------|---------|
| RECENT-HEADERS.md | ~5,000 | Last 20 memory log headers (session continuity) |
| L0/SSOT-L0-OVERVIEW.ai.md | ~400 | Mission, philosophy, business plan |
| L1/SSOT-L1-SYSTEM-OVERVIEW.ai.md | ~1,200 | Full system architecture |
| L1/SSOT-L1-IDENTITY-STUB.ai.md | ~280 | ResonantOS identity |
| L1/OPENCLAW-INDEX.ai.md | ~230 | OpenClaw doc navigation |
| **Total** | **~7,100** | |

These docs re-read from disk every `refreshEveryNTurns` (default 10) turns for freshness.

---

## Compound Keyword Scanning

File: `~/.openclaw/extensions/r-awareness/keywords.json` (31 entries, 104 phrases)

Unlike V1's single-word matching (caused over-triggering on "memory", "system", "token"), V3 uses **multi-word compound phrases** mapped to specific SSoT docs.

Example entries:
```json
{
  "id": "shield",
  "phrases": ["shield system", "shield gate", "security layer", "shield daemon"],
  "doc": "L1/SSOT-L1-SHIELD.ai.md"
}
```

### Matching Rules
- Case-insensitive
- Scans user message only (no AI response scanning)
- Compound phrases must match as substrings (no word-boundary tricks)
- One match per keyword entry per message
- Matched docs loaded for current turn only (no accumulation)
- Zero keyword docs is valid — if no phrases match, only always-on docs load

### Budget Control
- `tokenBudget: 25000` — max total SSoT tokens (always-on + keywords)
- Always-on docs load first (guaranteed), keyword docs fill remaining budget
- If a keyword doc exceeds remaining budget, it's skipped

---

## Human Commands

Prefix: `/R` (configurable)

| Command | Action |
|---------|--------|
| `/R load <path>` | Force-load a document (path relative to ssotRoot) |
| `/R remove <path>` | Unload a manually-loaded document |
| `/R clear` | Remove all manually-loaded documents |
| `/R list` | Show all loaded documents (always-on + keyword + manual) |
| `/R refresh` | Force re-read all docs from disk |
| `/R help` | Show available commands |

Manually loaded docs persist across turns (not cleared like keyword docs).

---

## Configuration

Stored in `openclaw.json` under `plugins.entries.r-awareness`:

```json
{
  "enabled": true,
  "hooks": { "allowPromptInjection": true },
  "config": {
    "ssotRoot": "~/resonantos/ssot",
    "alwaysOnDocs": [
      "L1/RECENT-HEADERS.md",
      "L0/SSOT-L0-OVERVIEW.ai.md",
      "L1/SSOT-L1-SYSTEM-OVERVIEW.ai.md",
      "L1/SSOT-L1-IDENTITY-STUB.ai.md",
      "L1/OPENCLAW-INDEX.ai.md"
    ],
    "tokenBudget": 25000,
    "refreshEveryNTurns": 10,
    "commandPrefix": "/R"
  }
}
```

---

## File Locations

| File | Path | Purpose |
|------|------|---------|
| Plugin code | `~/.openclaw/extensions/r-awareness/index.js` | The code (277 lines) |
| Manifest | `~/.openclaw/extensions/r-awareness/openclaw.plugin.json` | Plugin metadata + config schema |
| Keywords | `~/.openclaw/extensions/r-awareness/keywords.json` | 31 compound keyword entries |
| Config | `~/.openclaw/openclaw.json` (plugins section) | Runtime config |
| SSoT root | `~/resonantos/ssot/` | Source documents |
| V1 (disabled) | `~/.openclaw/agents/main/agent/extensions/r-awareness.js.v1-disabled` | Old version, kept for reference |

---

## Relationship to Other Systems

- **LCM** occupies the `contextEngine` plugin slot (mutually exclusive). R-Awareness uses `before_prompt_build` — a different slot, no conflict.
- **Memory architecture** (4-layer): MEMORY.md → RECENT-HEADERS.md (via R-Awareness) → LCM → RAG. R-Awareness is the delivery mechanism for layer 2.
