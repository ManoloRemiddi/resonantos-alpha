[AI-OPTIMIZED] ~380 tokens | src: openclaw/docs/concepts/compaction.md
Updated: 2026-02-14

---
summary: "Context window + compaction: how OpenClaw keeps sessions under model limits"
title: "Compaction"
---

# Context Window & Compaction

Every model has a **context window** (max tokens). Long-running chats accumulate messages/results; OpenClaw **compacts** older history to stay within limits.

## What compaction is

Compaction summarizes older conversation into a compact summary entry, preserves recent messages. Summary stored in JSONL history; future requests use compaction + recent messages.

Config: `agents.defaults.compaction`

## Auto-compaction (default on)

Triggers when session nears/exceeds model context window. OpenClaw compacts and may retry original request with compacted context.

Before compaction: **silent memory flush** can store durable notes to disk. See [Memory](/concepts/memory) for config.

## Manual compaction

```
/compact [optional instructions]
```

Example: `/compact Focus on decisions and open questions`

## Context window source

Model-specific, from configured provider catalog.

## Compaction vs pruning

| Aspect | Compaction | Pruning |
|--------|-----------|---------|
| Scope | Summarizes entire history | Trims old tool results |
| Persistence | Stored in JSONL | In-memory, per-request |

Large tool outputs already truncated; pruning further reduces buildup.

## Commands

- `/compact` — force compaction pass
- `/new` or `/reset` — fresh session id (if needed)
- `/status` — shows `🧹 Compactions: <count>`
