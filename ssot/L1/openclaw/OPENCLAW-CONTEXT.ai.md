[AI-OPTIMIZED] ~540 tokens | src: openclaw/docs/concepts/context.md
Updated: 2026-02-14

# Context

**Context** = everything OpenClaw sends to model, bounded by context window (token limit).

Components:
- System prompt (rules, tools, skills, time/runtime, injected workspace files)
- Conversation history (user + assistant messages)
- Tool calls/results + attachments (output, file reads, images/audio)

⚠️ Context ≠ memory (memory persists on disk; context = current window only)

## Inspect Context

| Command | Purpose |
|---------|---------|
| `/status` | Window fullness + session settings |
| `/context list` | Injected files + sizes (per-file + totals) |
| `/context detail` | Breakdown: per-file, tool schemas, skill entries, system prompt |
| `/usage tokens` | Per-reply token usage footer |
| `/compact` | Summarize old history, free window space |

See: [Slash commands](/tools/slash-commands), [Token use & costs](/token-use), [Compaction](/concepts/compaction).

### `/context list` Output Example
```
🧠 Context breakdown
Workspace: <workspaceDir>
Bootstrap max/file: 20,000 chars
Sandbox: mode=non-main sandboxed=false
System prompt (run): 38,412 chars (~9,603 tok) 
  Project Context: 23,901 chars (~5,976 tok)

Injected workspace files:
- AGENTS.md: OK | 1,742 chars (~436 tok)
- SOUL.md: OK | 912 chars (~228 tok)
- TOOLS.md: TRUNCATED | raw 54,210 | injected 20,962 chars (~5,241 tok)
- IDENTITY.md: OK | 211 chars (~53 tok)
- USER.md: OK | 388 chars (~97 tok)
- HEARTBEAT.md: MISSING | 0 chars
- BOOTSTRAP.md: OK | 0 chars

Skills (system prompt): 2,184 chars (~546 tok) | 12 skills
Tools (list): 1,032 chars (~258 tok)
Tool schemas (JSON): 31,988 chars (~7,997 tok)
Session tokens (cached): 14,250 total / ctx=32,000
```

### `/context detail` Output Example
```
Top skills (entry size):
- frontend-design: 412 chars (~103 tok)
- oracle: 401 chars (~101 tok)
… (+10 more)

Top tools (schema size):
- browser: 9,812 chars (~2,453 tok)
- exec: 6,240 chars (~1,560 tok)
… (+N more)
```

## What Counts Toward Context Window

- System prompt (all sections)
- Conversation history
- Tool calls + results
- Attachments/transcripts (images/audio/files)
- Compaction summaries, pruning artifacts
- Provider wrappers/hidden headers

## System Prompt Structure (OpenClaw-built, rebuilt each run)

- Tool list + descriptions
- Skills list (metadata; full skill SKILL.md loaded on-demand)
- Workspace location
- Time (UTC + user TZ if configured)
- Runtime metadata (host/OS/model/thinking)
- **Project Context**: injected bootstrap files

Full details: [System Prompt](/concepts/system-prompt)

## Injected Workspace Files (Project Context)

Default set (if present):
- `AGENTS.md`
- `SOUL.md`
- `TOOLS.md`
- `IDENTITY.md`
- `USER.md`
- `HEARTBEAT.md`
- `BOOTSTRAP.md` (first-run only)

Large files truncated per-file: `agents.defaults.bootstrapMaxChars` = 20,000 chars (default).
`/context` shows **raw vs injected** sizes + truncation status.

## Skills: Injection Model

System prompt includes compact **skills list** (name + description + location).
Skill instructions NOT included by default → model reads SKILL.md **on-demand only**.

## Tools: Two Context Costs

1. **Tool list text** in system prompt
2. **Tool schemas** (JSON) sent to model for calls; counted toward context (not visible as text)

`/context detail` breaks top tool schemas.

## Slash Commands & Directives

**Standalone**: message-only `/...` runs as command.

**Directives** (stripped before model sees message):
- `/think`, `/verbose`, `/reasoning`, `/elevated`, `/model`, `/queue`
- Directive-only msgs persist session settings
- Inline directives = per-message hints

**Inline shortcuts** (allowlisted senders): certain `/...` run immediately, stripped from remaining text.

Details: [Slash commands](/tools/slash-commands)

## Sessions, Compaction, Pruning

What persists:

| Mechanism | Behavior |
|-----------|----------|
| **Normal history** | Persists in transcript until compacted/pruned |
| **Compaction** | Summary persisted; recent msgs intact |
| **Pruning** | Removes old tool results from in-memory prompt only; transcript unchanged |

Docs: [Session](/concepts/session), [Compaction](/concepts/compaction), [Session pruning](/concepts/session-pruning)

## `/context` Reporting

Prefers latest **run-built** system prompt report (when available):
- `System prompt (run)` = captured from last embedded run, persisted in session store
- `System prompt (estimate)` = computed on-the-fly (no run report or CLI backend)

Reports sizes + top contributors. Does NOT dump full system prompt or schemas.
