[AI-OPTIMIZED] ~450 tokens | src: openclaw/docs/concepts/system-prompt.md
Updated: 2026-02-14

# System Prompt

OpenClaw builds custom system prompt per agent run. Prompt is OpenClaw-owned, not default p-coding-agent.

## Structure

Compact, fixed sections:

- **Tooling**: tool list + descriptions
- **Safety**: guardrail reminder (no power-seeking, no oversight bypass)
- **Skills**: model loads skill instructions on demand
- **OpenClaw Self-Update**: `config.apply`, `update.run`
- **Workspace**: working directory (`agents.defaults.workspace`)
- **Documentation**: local path to OpenClaw docs (repo or npm pkg); when to read
- **Workspace Files (injected)**: bootstrap files included below
- **Sandbox** (when enabled): sandboxed runtime, paths, elevated exec availability
- **Current Date & Time**: user-local time, timezone, format
- **Reply Tags**: optional syntax (supported providers)
- **Heartbeats**: heartbeat prompt, ack behavior
- **Runtime**: host, OS, node, model, repo root, thinking level (one line)
- **Reasoning**: visibility level + /reasoning toggle

Safety guardrails are advisory; guide behavior but don't enforce. Use tool policy, exec approvals, sandboxing, allowlists for hard enforcement.

## Prompt Modes

Configurable per run via `promptMode`:

- **full** (default): all sections above
- **minimal** (sub-agents): omits Skills, Memory Recall, Self-Update, Model Aliases, User Identity, Reply Tags, Messaging, Silent Replies, Heartbeats. Keeps Tooling, Safety, Workspace, Sandbox, Date/Time, Runtime, injected context
- **none**: identity line only

Injected prompts labeled **Subagent Context** when `promptMode=minimal`.

## Bootstrap Injection

Trimmed files appended under **Project Context**:
- `AGENTS.md`, `SOUL.md`, `TOOLS.md`, `IDENTITY.md`, `USER.md`, `HEARTBEAT.md`, `BOOTSTRAP.md` (new workspaces only)

Max per-file: `agents.defaults.bootstrapMaxChars` (default: 20000 chars). Large files truncated + marked. Missing files → short marker.

Interceptable via `agent:bootstrap` hook for mutations/replacements (e.g., swap `SOUL.md`).

Use `/context list` or `/context detail` to inspect per-file overhead (raw vs injected, truncation, tool schema).

## Time Handling

**Current Date & Time** section when user timezone known. Includes timezone only (no dynamic clock) for cache stability. Current time: use `session_status`.

Config:
- `agents.defaults.userTimezone`
- `agents.defaults.timeFormat` (`auto` | `12` | `24`)

See [Date & Time](/date-time).

## Skills

Compact **available skills list** injected when eligible. Includes path per skill. Model loads via `read` from workspace, managed, or bundled location.

```xml
<available_skills>
  <skill>
    <name>...</name>
    <description>...</description>
    <location>...</location>
  </skill>
</available_skills>
```

Omitted if no eligible skills.

## Documentation

**Documentation** section (when available) points to:
- Local OpenClaw docs dir (`docs/` repo or npm bundled)
- Public mirror, source repo, community Discord, ClawHub (https://clawhub.com)

Model reads local docs first for OpenClaw behavior/commands/config/arch. Runs `openclaw status` when possible; asks user only when no access.
