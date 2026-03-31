[AI-OPTIMIZED] ~160 tokens | src: SSOT-L1-OPENAI-PRO-VIA-CODEX.md | Updated: 2026-03-10

| Field | Value |
|-------|-------|
| ID | SSOT-L1-OPENAI-PRO-VIA-CODEX-V1 | Level | L1 | Status | Active |
| Created | 2026-02-22 | Stale After | 90 days |

## Overview
OpenAI Pro subscription accessed via `openai-codex` provider in OpenClaw. NOT just Codex — gateway to ENTIRE OpenAI catalog at zero marginal cost.

## Auth Chain
`OpenAI Pro → ChatGPT OAuth (device-code) → openai-codex provider → https://chatgpt.com/backend-api → all OpenAI models`

**Provider ID:** `openai-codex` | **Auth:** OAuth (ChatGPT login) | **Profile:** `openai-codex:default` in auth-profiles.json
**CLI login:** `openclaw models auth login --provider openai-codex`

## Available Models (prefix: `openai-codex/`)
| Model | Best For |
|-------|----------|
| gpt-5.3-codex | Complex coding/architecture |
| gpt-4o | General reasoning, multimodal |
| gpt-4o-mini | Lightweight tasks, heartbeats |
| o4-mini | Reasoning, lightweight |
| o3 | Deep reasoning |
| gpt-4o-mini-transcribe | Audio transcription |

**Key:** Only `gpt-5.3-codex` auto-routes from `openai/`. All others need explicit `openai-codex/` prefix.

## OpenClaw Config
```json5
{
  agents: { defaults: { models: { "openai-codex/gpt-5.3-codex": {}, "openai-codex/gpt-4o-mini": {} } } },
  // heartbeat: { model: "openai-codex/gpt-4o-mini" }
  // audio: { provider: "openai", model: "gpt-4o-mini-transcribe", profile: "openai-codex:default" }
}
```

## Cost Model
Monthly fixed (OpenAI Pro). Per-token: $0. Use freely for any task where fit.

## Current Assignments (2026-02-22)
| Task | Model | Provider |
|------|-------|----------|
| Orchestrator | claude-opus-4-6 | anthropic (Claude Max) |
| Heartbeat | gpt-4o-mini | openai-codex (Pro) |
| Audio transcription | gpt-4o-mini-transcribe | openai-codex (Pro) |
| Coding (Codex CLI) | gpt-5.3-codex | openai-codex (Pro) |

## Rules
- DO NOT use separate `openai` API-key provider (Pro covers same models)
- DO NOT use Anthropic Haiku for lightweight tasks (gpt-4o-mini is free via Pro)
- DO NOT assume openai-codex = Codex models only
- `openai` API-key provider: REMOVED
