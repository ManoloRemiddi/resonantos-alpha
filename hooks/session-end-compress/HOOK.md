---
name: session-end-compress
description: "Compresses session final state to CONTEXT.md before /new clears the session"
metadata: {"clawdbot":{"emoji":"📦","events":["command:new","command:reset"]}}
---

# Session End Compress Hook

Captures the final session state before `/new` or `/reset` clears it, ensuring decisions and outcomes are persisted to CONTEXT.md.

## Problem Solved

The Memory Agent normally compresses only the "older half" of sessions mid-session. This means when `/new` is issued, the recent portion (containing final decisions, resolutions) is lost.

## What It Does

1. Listens for `command:new` and `command:reset` events
2. **Before** the session is cleared, runs compression on the full remaining session
3. Uses a special prompt focused on "KEY DECISIONS, OUTCOMES, and FINAL STATE"
4. Writes the compressed context to CONTEXT.md in the agent's workspace
5. The session then resets normally

## How It Works

```
User sends /new
    ↓
Hook intercepts command:new event
    ↓
Extracts full session content
    ↓
Compresses via Haiku with decision-focused prompt
    ↓
Writes to CONTEXT.md
    ↓
Session reset continues normally
```

## Requirements

- Python 3 available
- session_monitor.py at expected path

## Configuration

No configuration needed. Enable the hook:

```bash
clawdbot hooks enable session-end-compress
```
