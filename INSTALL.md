# ResonantOS Alpha v0.6.0 — Installation Guide

> **Status:** Experimental Linux install/handoff branch.
>
> If you are an OpenClaw agent or an operator guiding one, read `install/INSTALL_SPEC.yaml` before executing installation work. Treat that YAML file as the canonical install contract for this branch, and use this document as the human-facing guide.

## Prerequisites

- [OpenClaw](https://docs.openclaw.ai) installed and running
- A Telegram bot token (or other supported channel)
- An LLM provider API key (OpenAI, Anthropic, MiniMax, or local model)

## Quick Start

### 1. Clone into your OpenClaw workspace

```bash
git clone https://github.com/ResonantOS/resonantos-alpha.git ~/.openclaw/workspace
cd ~/.openclaw/workspace
```

### 2. Fill placeholders

This repo uses `{{PLACEHOLDER}}` tokens where personal data belongs. Find them all:

```bash
grep -rn '{{[A-Z_]*}}' --include="*.md" --include="*.js" --include="*.json" --include="*.py" | sort -u
```

Key placeholders to fill:

| Placeholder | Description | Example |
|---|---|---|
| `{{OWNER_NAME}}` | Your name | `Alice` |
| `{{OWNER_EMAIL}}` | Your email | `alice@example.com` |
| `{{OWNER_CHAT_ID}}` | Your Telegram chat ID | `123456789` |
| `{{OWNER_DOMAIN}}` | Your personal domain (if any) | `example.com` |
| `{{OWNER_HANDLE}}` | Your username/handle | `alicebuilds` |
| `{{OWNER_LINKEDIN}}` | Your LinkedIn URL | `linkedin.com/in/alice` |
| `{{HOST_IP}}` | Your orchestrator's local IP | `192.168.1.100` |
| `{{GPU_SERVER_IP}}` | GPU server IP (if applicable) | `192.168.1.200` |
| `{{HOSTNAME}}` | Your machine's hostname | `my-mac.local` |
| `{{SSH_USER}}` | SSH username for orchestrator | `admin` |
| `{{BOT_TOKEN_DEFAULT}}` | Telegram bot token | `123:ABC...` |

You can do a bulk replace:

```bash
# Example: replace all instances of a placeholder
find . -type f \( -name "*.md" -o -name "*.js" -o -name "*.json" -o -name "*.py" \) \
  -exec sed -i '' 's/{{OWNER_NAME}}/Alice/g' {} +
```

### 3. Configure OpenClaw

Ensure your `openclaw.json` has:
- At least one LLM provider configured
- Telegram (or other channel) plugin enabled
- Your agent definitions pointing to this workspace

Refer to [OpenClaw docs](https://docs.openclaw.ai) for channel and provider setup.

### 4. Explore the SSoT

The Single Source of Truth lives in `ssot/`:

| Level | Purpose | Start here |
|---|---|---|
| `L0/` | Foundation — philosophy, identity, roadmap | `SSOT-L0-OVERVIEW.md` |
| `L1/` | Architecture — system specs, protocols, security | `SSOT-L1-SYSTEM-OVERVIEW.md` |
| `L1/protocols/` | Procedural triggers for common tasks | `PROTO-CODING.md` |
| `L1/openclaw/` | OpenClaw-specific configuration guides | Browse all |

### 5. Customize

ResonantOS is a framework, not a finished product. Key files to personalize:

- `ssot/L0/SSOT-L0-CREATIVE-DNA.md` — Your identity, skills, portfolio
- `ssot/L0/SSOT-L0-CONSTITUTION.md` — Your governance rules
- `ssot/L1/SSOT-L1-SHIELD.md` — Security gates and policies
- `ssot/L1/SSOT-L1-SYSTEM-OVERVIEW.md` — Your infrastructure topology

## What's Included

- **SSoT L0** — Philosophy, brand, roadmap, world model, creative DNA
- **SSoT L1** — Architecture specs, security (Shield), reasoning (Logician), protocols, alignment
- **Dashboard** — Flask web interface (port 19100)
- **Shield** — Security gate extension
- **Solana Toolkit** — Symbiotic wallet + protocol marketplace (DevNet)
- **Extensions** — Shield gate, execution envelopes

## What's NOT Included

- Memory files, daily logs, conversation history
- API keys, bot tokens, SSH credentials
- L2/L3/L4 SSoT (project-specific, drafts, notes)
- Personal cron jobs or heartbeat configuration

## Support

- Docs: https://docs.openclaw.ai
- Community: https://discord.com/invite/clawd
- Source: https://github.com/ResonantOS/resonantos-alpha
