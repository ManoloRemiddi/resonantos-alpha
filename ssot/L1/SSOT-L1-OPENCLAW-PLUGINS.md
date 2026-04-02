# SSOT-L1: OpenClaw Plugin Architecture
Updated: 2026-03-27

**Level:** L1 (Architecture)
**Created:** 2026-03-15
**Status:** Active

## Overview

OpenClaw uses a **plugin system** for extending agent behavior. Plugins hook into the agent lifecycle at specific points and can modify, block, or observe events.

## Plugin Structure

Each plugin lives in `~/.openclaw/extensions/<plugin-name>/`:

```
~/.openclaw/extensions/<plugin-name>/
├── openclaw.plugin.json    # Plugin manifest (id, name, description, configSchema)
├── index.js                # Hook implementation (CommonJS or TypeScript)
└── package.json            # Optional (required for npm-installed plugins)
```

### openclaw.plugin.json (Manifest)
```json
{
  "id": "plugin-name",
  "name": "Human Readable Name",
  "description": "What it does",
  "version": "1.0.0",
  "configSchema": {
    "type": "object",
    "properties": {
      "enabled": { "type": "boolean" }
    }
  }
}
```

### Registration in openclaw.json
```json
{
  "plugins": {
    "entries": {
      "plugin-name": {
        "enabled": true,
        "config": { ... }
      }
    }
  }
}
```

## Available Hooks

| Hook | Type | When | Use Case |
|------|------|------|----------|
| `before_tool_call` | **Modifying** | Before any tool execution | Block/modify tool calls (Shield) |
| `agent_end` | **Void** | After AI response is sent | Post-response auditing, logging, background tasks |
| `subagent_ended` | **Void** | After sub-agent completes | Sub-agent lifecycle tracking |

### Hook Types
- **Modifying hooks** can alter the event data or block execution (return modified event or `{ blocked: true }`)
- **Void hooks** are fire-and-forget — they observe but cannot alter the event

### Hook Registration Pattern
Plugins export functions that OpenClaw calls. The exact export pattern follows the `before_tool_call` model in shield-gate. The hook runner is in the compiled source at `auth-profiles-*.js`.

## Installed Plugins (as of 2026-03-27)

| Plugin | Hook | Purpose | Status |
|--------|------|---------|--------|
| `shield-gate` | `before_tool_call` | Blocks destructive commands, enforces delegation gates | Active |
| `lossless-claw` (LCM) | Context engine slot | Lossless context management, DAG-based summarization | Active |
| `usage-tracker` | — | API usage tracking | Active |
| `coherence-gate` | `before_tool_call` | Task coherence enforcement | Active |
| `heuristic-auditor` | `agent_end` | Post-response philosophical heuristic audit | Active |

## Plugin Slots

Some plugins occupy named **slots** rather than hooking events:

```json
{
  "plugins": {
    "slots": {
      "contextEngine": "lossless-claw"
    }
  }
}
```

The `contextEngine` slot replaces OpenClaw's built-in context management. Only one plugin can occupy each slot.

## NPM-Installed vs Local Plugins

- **NPM plugins** (like LCM): installed via `openclaw plugin install`, have `package.json`, tracked in `plugins.installs`
- **Local plugins** (like shield-gate): manually created in `~/.openclaw/extensions/`, just need `openclaw.plugin.json`

Both are registered in `plugins.entries` for enable/disable and config.

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Plugin over extension | Old extension integrations broke when OpenClaw internals changed. Plugin API is stable. |
| Void hooks are async | `agent_end` runs fire-and-forget — never delays the next response |
| configSchema in manifest | Dashboard can render plugin settings UI automatically |
| Local plugins supported | Don't need npm packaging for custom plugins — just files in extensions/ |

## Lessons Learned

1. **Old extension integrations broke** because they hooked into OpenClaw internals. Plugin API is the correct, stable approach.
2. **Always use plugin API** for new functionality that hooks into the agent lifecycle.
3. **Void hooks for non-critical work** — auditing, logging, metrics should never block the main flow.
4. **Study existing plugins** before building new ones — shield-gate for `before_tool_call`, LCM for context engine slot.
