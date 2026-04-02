<!-- TEMPLATE: Customize this file for your deployment -->
Updated: 2026-03-27
[AI-OPTIMIZED] ~400 tokens | src: SSOT-L1-R-AWARENESS.md | Updated: 2026-03-27

# R-Awareness V3 — SSoT Context Injection

**Plugin:** `~/.openclaw/extensions/r-awareness/index.js` (277 lines)
**Hook:** `before_prompt_build` → `appendSystemContext` (cacheable)

## Two Injection Modes

### 1. Always-On Docs (~7,100 tokens, every turn)
| Doc | ~Tokens |
|-----|---------|
| RECENT-HEADERS.md | ~5,000 |
| L0-OVERVIEW.ai.md | ~400 |
| L1-SYSTEM-OVERVIEW.ai.md | ~1,200 |
| L1-IDENTITY-STUB.ai.md | ~280 |
| OPENCLAW-INDEX.ai.md | ~230 |

Re-read from disk every 10 turns.

### 2. Compound Keywords (31 entries, 104 phrases)
Multi-word phrases in user message → specific SSoT doc. Cleared each turn. Zero matches = only always-on loads. Budget: 25K tokens total.

Keywords file: `~/.openclaw/extensions/r-awareness/keywords.json`

## Commands
`/R load|remove|clear|list|refresh|help`

## Config (in openclaw.json)
`plugins.entries.r-awareness`: ssotRoot, alwaysOnDocs (5 paths), tokenBudget (25000), refreshEveryNTurns (10)

## V3 vs V1
V1 disabled (.v1-disabled). Key changes: modern plugin format, compound phrases (not single words), no TTL/AI scanning, 277 vs 709 lines.

## Relationships
- LCM owns contextEngine slot — R-Awareness uses separate `before_prompt_build` (no conflict)
- Delivers layer 2 of 4-layer memory stack (MEMORY.md → Headers → LCM → RAG)
