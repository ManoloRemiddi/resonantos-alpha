# SSOT-L1-OPENAI-PRO-VIA-CODEX
Updated: 2026-03-15

| Field | Value |
|-------|-------|
| **ID** | `SSOT-L1-OPENAI-PRO-VIA-CODEX-V1` |
| **Created** | 2026-02-22 |
| **Level** | L1 (Architecture) |
| **Status** | Active |
| **Stale After** | 90 days |

## Overview

We have an **OpenAI Pro subscription** accessed through the `openai-codex` provider in OpenClaw. This is NOT just a Codex coding tool. It is a gateway to the ENTIRE OpenAI model catalog, all included in the Pro subscription at zero marginal cost.

## How It Works

```
OpenAI Pro Subscription (paid monthly)
    ↓
ChatGPT OAuth (device-code flow)
    ↓
openai-codex provider in OpenClaw
    ↓
Routes through: https://chatgpt.com/backend-api
    ↓
Access to ALL OpenAI models
```

## Authentication

- **Provider ID**: `openai-codex`
- **Auth mode**: OAuth (ChatGPT login)
- **Profile**: `openai-codex:default` in `auth-profiles.json`
- **CLI login**: `openclaw models auth login --provider openai-codex`

## Available Models (via Pro subscription)

All OpenAI models are accessible through the `openai-codex` provider prefix:

| Model | Ref | Best For |
|-------|-----|----------|
| GPT-5.3 Codex | `openai-codex/gpt-5.3-codex` | Complex coding, architecture |
| GPT-4o | `openai-codex/gpt-4o` | General reasoning, multimodal |
| GPT-4o Mini | `openai-codex/gpt-4o-mini` | Lightweight tasks, heartbeats |
| o4-mini | `openai-codex/o4-mini` | Reasoning tasks, lightweight |
| o3 | `openai-codex/o3` | Deep reasoning |
| gpt-4o-mini-transcribe | via `profile: openai-codex:default` | Audio transcription |

**Key insight**: Only `gpt-5.3-codex` auto-routes from `openai/` to `openai-codex/`. For all other models, use the `openai-codex/` prefix explicitly.

## OpenClaw Configuration

### Adding models to allowlist

Models must be in the `agents.defaults.models` allowlist to be usable:

```json5
{
  agents: {
    defaults: {
      models: {
        "openai-codex/gpt-5.3-codex": {},
        "openai-codex/gpt-4o-mini": {},
        // Add more as needed
      }
    }
  }
}
```

### Assigning models to tasks

```json5
{
  agents: {
    defaults: {
      heartbeat: {
        model: "openai-codex/gpt-4o-mini"  // Lightweight, free via Pro
      }
    }
  }
}
```

### Audio transcription

Uses the Codex OAuth profile even though the provider shows as `openai`:

```json5
{
  tools: {
    media: {
      audio: {
        models: [{
          provider: "openai",
          model: "gpt-4o-mini-transcribe",
          profile: "openai-codex:default"  // Routes through Pro subscription
        }]
      }
    }
  }
}
```

## Cost Model

- **Monthly subscription**: Fixed cost (OpenAI Pro)
- **Per-token cost**: $0 (all usage included)
- **Implication**: Use OpenAI models freely for any task where they fit. No reason to use paid-per-token alternatives for lightweight work.

## Current Assignments (2026-02-22)

| Task | Model | Provider |
|------|-------|----------|
| Orchestrator (main) | claude-opus-4-6 | anthropic (Claude Max) |
| Heartbeat | gpt-4o-mini | openai-codex (Pro) |
| Audio transcription | gpt-4o-mini-transcribe | openai-codex (Pro) |
| Coding (Codex CLI) | gpt-5.3-codex | openai-codex (Pro) |

## What NOT to Do

1. **Do NOT use a separate `openai` provider with API key** when Pro subscription covers the same models
2. **Do NOT use Anthropic Haiku for lightweight tasks** when gpt-4o-mini is free via Pro
3. **Do NOT assume openai-codex only serves Codex models** - it serves ALL GPT models

## Relationship to Other Providers

- **anthropic**: Claude Max subscription (Opus for orchestration)
- **openai-codex**: OpenAI Pro subscription (all GPT models, coding, transcription)
- **openai** (API key): REMOVED. Not needed when Pro covers everything.

## References

- OpenClaw model providers: https://docs.openclaw.ai/concepts/model-providers
- OpenAI Codex docs: https://developers.openai.com/codex/models/
- Related: `private/OPENAI-CODEX-SELF-KNOWLEDGE.ai.md`
