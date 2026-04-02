[AI-OPTIMIZED] ~650 tokens | src: openclaw/docs/concepts/agent.md
Updated: 2026-02-14

---
summary: "Agent runtime (embedded pi-mono), workspace contract, session bootstrap"
title: "Agent Runtime"
---

# Agent Runtime 🤖

OpenClaw runs single embedded agent runtime from **pi-mono**.

## Workspace (required)

Single agent workspace dir (`agents.defaults.workspace`) = only working dir (`cwd`) for tools & context.

Setup: `openclaw setup` creates `~/.openclaw/openclaw.json`, initializes workspace files.

Ref: [Agent workspace](/concepts/agent-workspace)

Sandbox mode: `agents.defaults.sandbox` enabled → non-main sessions override with per-session workspaces under `agents.defaults.sandbox.workspaceRoot`. See [Gateway config](/gateway/configuration).

## Bootstrap Files (injected)

Inside `agents.defaults.workspace`, OpenClaw expects:

- `AGENTS.md` — instructions + memory
- `SOUL.md` — persona, boundaries, tone
- `TOOLS.md` — user notes (imsg, sag, conventions)
- `BOOTSTRAP.md` — first-run ritual (deleted after completion)
- `IDENTITY.md` — agent name/vibe/emoji
- `USER.md` — user profile + address

Injected on first turn of new session. Blank files skipped. Large files trimmed + truncated with marker (read full content separately).

Missing file → single "missing file" marker; `openclaw setup` creates safe defaults.

`BOOTSTRAP.md` created only for **brand new workspace** (no other bootstrap files present). Delete after ritual; won't recreate on restarts.

Disable bootstrap file creation entirely:
```json5
{ agent: { skipBootstrap: true } }
```

## Built-in Tools

Core tools (read/exec/edit/write + system) always available per tool policy. `apply_patch` optional, gated by `tools.exec.applyPatch`. `TOOLS.md` **not** tool control—guidance only.

## Skills

Loaded from three locations (workspace wins on conflict):

- Bundled (shipped)
- Managed/local: `~/.openclaw/skills`
- Workspace: `<workspace>/skills`

Gated by config/env. See `skills` in [Gateway config](/gateway/configuration).

## pi-mono Integration

OpenClaw reuses pi-mono pieces (models/tools), but **session mgmt, discovery, tool wiring = OpenClaw-owned**.

- No pi-coding agent runtime
- No `~/.pi/agent` or `<workspace>/.pi` settings consulted

## Sessions

Session transcripts: JSONL at `~/.openclaw/agents/<agentId>/sessions/<SessionId>.jsonl`

Session ID stable, chosen by OpenClaw. Legacy Pi/Tau folders **not** read.

## Steering While Streaming

Queue mode `steer`: inbound msgs injected into current run. Queue checked **after each tool call**; if msg present → skip remaining tool calls (error: "Skipped due to queued user message."), inject queued msg, proceed.

Queue modes `followup`/`collect`: msgs held until turn ends, new turn starts with queued payloads. See [Queue](/concepts/queue) for mode + debounce/cap.

### Block Streaming

**Off by default** (`agents.defaults.blockStreamingDefault: "off"`).

- `agents.defaults.blockStreamingBreak`: `text_end` vs `message_end` (default: text_end)
- `agents.defaults.blockStreamingChunk`: soft block chunking (default: 800–1200 chars; prefers: paragraphs > newlines > sentences)
- `agents.defaults.blockStreamingCoalesce`: merge streamed chunks, idle-based merging, reduce spam

Non-Telegram requires explicit `*.blockStreaming: true` for block replies.

Verbose tool summaries emitted at tool start (no debounce). Control UI streams tool output via agent events when available.

More: [Streaming + chunking](/concepts/streaming).

## Model Refs

Model refs in config (e.g., `agents.defaults.model`, `agents.defaults.models`) parsed by split on **first** `/`.

- Format: `provider/model`
- OpenRouter-style (model ID contains `/`): include provider prefix, e.g., `openrouter/moonshotai/kimi-k2`
- No `/` → alias or default provider model

## Configuration (minimal)

Required:

- `agents.defaults.workspace`
- `channels.whatsapp.allowFrom` (strongly recommended)

---

Next: [Group Chats](/concepts/group-messages) 🦞
