# R-Awareness — SSoT Context Injection

| Field | Value |
|-------|-------|
| Version | 1.0 (Alpha) |
| Date | 2026-02-18 |
| Level | L1 (Architecture) |
| Type | OpenClaw Extension |

---

## What Is R-Awareness

A silent OpenClaw extension that injects SSoT documents into the AI's system prompt based on keyword detection in human messages. The AI sees injected content as native knowledge. The human chat experience is unchanged.

> Silent success, visible errors. Infrastructure, not agent.

---

## How It Works

```
Human message → keyword scan → load matching SSoT docs → inject into system prompt → AI responds with context
```

1. Human sends a message
2. R-Awareness scans the message text for configured keywords
3. Matching SSoT documents are loaded from disk
4. Documents are appended to the system prompt in XML tags
5. The AI responds with full project context — without the human needing to manually load anything

---

## Cold Start Mode

When `coldStartOnly: true` (recommended):
- **Turn 1:** No keyword scanning. Only loads a minimal identity document (whitelist). Agent starts clean and fast.
- **Turn 2+:** Normal keyword matching resumes. Documents load on-demand as conversation references them.

This prevents session flooding — docs load only when the conversation actually needs them.

---

## Keyword Configuration

### Manual Keywords (Primary)

File: `~/.openclaw/workspace/r-awareness/keywords.json`

```json
{
  "philosophy": "L0/PHILOSOPHY.md",
  "architecture": "L1/SYSTEM-ARCHITECTURE.md",
  "memory": "L1/R-MEMORY.md",
  "awareness": "L1/R-AWARENESS.md"
}
```

- Case-insensitive, word-boundary aware
- Multiple keywords can point to the same document
- Pure regex matching — zero token cost

### Auto-Generated Keywords (Optional)

When `autoKeywords: true`, R-Awareness scans the SSoT directory and generates keywords from filenames. Manual keywords always override auto-generated ones.

---

## SSoT Levels & Injection

| Level | Auto-inject | Purpose |
|-------|-------------|---------|
| L0 | ✅ via keywords | Vision, philosophy |
| L1 | ✅ via keywords | Architecture, specs |
| L2 | ✅ via keywords | Active projects |
| L3 | ❌ manual only | Drafts, WIP |
| L4 | ❌ manual only | Notes, ephemeral |

Priority: L0 > L1 > L2 (higher levels loaded first when budget is tight)

---

## Limits

| Limit | Default | Description |
|-------|---------|-------------|
| Max docs per turn | 10 | Maximum simultaneous documents |
| Token budget | 15,000 | Maximum SSoT tokens in system prompt |
| TTL | 15 turns | Documents expire after N turns without re-mention |

When budget is exceeded, higher-priority documents are loaded first; lower ones are skipped.

---

## /R Commands

Use these in chat to manually control document injection:

| Command | Action |
|---------|--------|
| `/R load <path>` | Force-load a document (bypasses level restrictions) |
| `/R remove <path>` | Unload a document |
| `/R clear` | Remove all loaded documents |
| `/R list` | Show loaded documents with level, tokens, TTL |
| `/R pause` | Disable auto-injection |
| `/R resume` | Re-enable auto-injection |

---

## Configuration

File: `~/.openclaw/workspace/r-awareness/config.json`

```json
{
  "enabled": true,
  "ssotRoot": "<path-to-your-ssot-directory>",
  "autoKeywords": false,
  "maxDocsPerTurn": 10,
  "tokenBudget": 15000,
  "ttlTurns": 15,
  "commandPrefix": "/R",
  "coldStartOnly": true,
  "coldStartDocs": ["L1/IDENTITY-STUB.ai.md"]
}
```

| Key | Default | Description |
|-----|---------|-------------|
| `enabled` | true | Master switch |
| `ssotRoot` | "" | Absolute path to your SSoT directory |
| `autoKeywords` | true | Auto-generate keywords from filenames |
| `maxDocsPerTurn` | 10 | Max simultaneous documents |
| `tokenBudget` | 15000 | Max SSoT tokens |
| `ttlTurns` | 15 | Turns before document eviction |
| `coldStartOnly` | false | Turn 1: whitelist only |
| `coldStartDocs` | [] | Documents to load on first turn |

---

## Relationship to R-Memory

Independent. R-Awareness handles **project knowledge** (SSoT injection). R-Memory handles **conversation length** (compression + eviction). Different hooks, installable independently.

---

## Diagnostics

```bash
tail -20 ~/.openclaw/workspace/r-awareness/r-awareness.log
```

| Symptom | Fix |
|---------|-----|
| No init log | Check extensions directory, restart gateway |
| Keywords match but no injection | Check token budget in log |
| Too many docs loading | Set `autoKeywords: false`, use manual keywords |
| Document content not updating | Re-mention the keyword to reload from disk |
