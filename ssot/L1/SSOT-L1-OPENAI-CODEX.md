# SSOT-L1-OPENAI-CODEX
Updated: 2026-03-15

| Field | Value |
|-------|-------|
| **ID** | `SSOT-L1-OPENAI-CODEX-V1` |
| **Created** | 2026-02-22 |
| **Level** | L1 (Architecture) |
| **Status** | Active |
| **Stale After** | 60 days |
| **Source** | https://developers.openai.com/codex |

## Overview

OpenAI Codex is a **full coding agent platform**, not just a CLI tool. It operates across four surfaces, all connected by one ChatGPT account, included in the Pro subscription at zero marginal cost.

## The Four Surfaces

| Surface | What It Is | When to Use |
|---------|-----------|-------------|
| **Codex CLI** | Local terminal agent (Rust, open source) | Pair programming, scripted automation, `codex exec` from OpenClaw |
| **Codex Cloud** | Remote sandboxed environment | Background tasks, parallel work, PRs from cloud |
| **Codex Web App** | chatgpt.com/codex | Command center for cloud tasks |
| **GitHub Integration** | @codex in issues/PRs | Code review, task delegation from GitHub |

## Models Available

| Model | Speed | Best For | Access |
|-------|-------|----------|--------|
| **gpt-5.3-codex** | Medium | Complex coding, architecture (default) | All plans |
| **gpt-5.3-codex-spark** | Fast | Day-to-day coding, quick iteration | Pro only (research preview) |
| **gpt-5.2-codex** | Medium | Legacy, succeeded by 5.3 | All plans |
| **gpt-5.1-codex-mini** | Fast | Routine tasks, 4x usage extension | All plans |
| **gpt-5.2** | Medium | General agentic tasks | All plans |

Switch models: `codex -m gpt-5.3-codex-spark` or `/model` during session.

## Pro Plan Rate Limits (per 5-hour window)

| Resource | Pro Limits |
|----------|-----------|
| Local messages | 300-1500 |
| Cloud tasks | 50-400 |
| Code reviews/week | 100-250 |

Limits vary by task complexity. Use gpt-5.1-codex-mini for ~4x more messages. Credits available if limits hit.

---

## 1. CLI Features (What We Use via OpenClaw)

### Core Commands

```bash
# Interactive session
codex

# Non-interactive execution (what OpenClaw uses)
codex exec "your prompt"

# With specific model
codex -m gpt-5.3-codex-spark exec "quick fix"

# With image input
codex -i screenshot.png "Implement this UI"

# Resume previous session
codex resume --last
codex exec resume --last "Continue from where you left off"

# Code review (local)
codex  # then type /review

# Cloud task from CLI
codex cloud exec --env ENV_ID "Summarize open bugs"
```

### Approval Modes

| Mode | Behavior |
|------|----------|
| **Auto** (default) | Read, edit, run commands in working directory. Asks before going outside scope. |
| **Read-only** | Browse files only. No changes without approval. |
| **Full Access** (`--yolo`) | No restrictions. Use sparingly. |

### Session Resume

Codex stores transcripts locally (`~/.codex/sessions/`). Resume any previous session:
- `codex resume` -- picker of recent sessions
- `codex resume --last` -- most recent session
- `codex exec resume --last "New instructions"` -- non-interactive resume

### Web Search

- Default: cached (OpenAI index, safer)
- `--search` flag or `web_search = "live"` in config for live results
- `web_search = "disabled"` to turn off

### Multi-Agent (Experimental)

Enable in `~/.codex/config.toml`:

```toml
[features]
multi_agent = true
```

Spawns specialized sub-agents in parallel. Define roles:

```toml
[agents.reviewer]
description = "Find security, correctness, and test risks."
config_file = "agents/reviewer.toml"

[agents.explorer]
description = "Fast codebase explorer for read-heavy tasks."
config_file = "agents/custom-explorer.toml"
```

Role config overrides (e.g., `agents/reviewer.toml`):

```toml
model = "gpt-5.3-codex"
model_reasoning_effort = "high"
sandbox_mode = "read-only"
developer_instructions = "Focus on high priority issues."
```

### MCP (Model Context Protocol)

Connect external tools via MCP servers in `~/.codex/config.toml`. Codex can also run AS an MCP server for other agents.

---

## 2. GitHub Integration (Code Review)

### Automatic PR Review

1. Go to https://chatgpt.com/codex/settings/code-review
2. Turn on **Code review** for your repository
3. Optionally enable **Automatic reviews** (reviews on every PR open)

### Manual Review

Comment on any PR:
```
@codex review
```

Codex reacts with eyes emoji, then posts a standard GitHub code review (P0/P1 issues only by default).

Focused review:
```
@codex review for security regressions
```

### Review Guidelines via AGENTS.md

Codex reads `AGENTS.md` files in the repo. Add a review section:

```markdown
## Review guidelines

- Don't log PII.
- Verify that authentication middleware wraps every route.
- Treat typos in docs as P1.
```

Codex applies the closest `AGENTS.md` to each changed file. Nested AGENTS.md files override parent ones.

### Task Delegation from GitHub

Comment anything other than "review" to start a cloud task:
```
@codex fix the CI failures
```

---

## 3. Codex Cloud

- Runs tasks in isolated cloud environments (sandboxed VMs)
- Creates PRs directly from cloud results
- Parallel execution: multiple tasks run simultaneously
- `--attempts 1-4` for best-of-N solutions
- Environment setup via https://chatgpt.com/codex (Codex web app)

### From CLI:
```bash
codex cloud exec --env ENV_ID "Summarize open bugs"
codex cloud exec --env ENV_ID --attempts 3 "Refactor auth module"
```

---

## 4. AGENTS.md System

Codex reads AGENTS.md before every task. Precedence chain:

1. **Global**: `~/.codex/AGENTS.md` (or `AGENTS.override.md`)
2. **Project**: Git root down to cwd, one file per directory
3. **Merge**: Concatenated root-down; deeper files override earlier ones

Max combined size: 32 KiB (configurable via `project_doc_max_bytes`).

### Our Setup

We should create `AGENTS.md` in `resonantos-alpha/` root with:
- Build/test commands
- Code style conventions
- Review guidelines
- Security rules (no PII logging, wallet key handling)

---

## 5. Configuration

### Config file: `~/.codex/config.toml`

```toml
model = "gpt-5.3-codex"
model_reasoning_effort = "high"
web_search = "live"

[features]
multi_agent = true

# Fallback instruction files
project_doc_fallback_filenames = ["TEAM_GUIDE.md"]
project_doc_max_bytes = 65536

# Agent roles
[agents.reviewer]
description = "Code review specialist."
config_file = "agents/reviewer.toml"
```

### Feature Flags

```bash
codex features list
codex features enable unified_exec
codex features enable multi_agent
```

---

## 6. How We Use Codex (Current Architecture)

### Via OpenClaw (Primary)

OpenClaw spawns Codex CLI in PTY mode for coding tasks:

```bash
# Background task
codex exec --full-auto "Build feature X"

# With model override
codex -m gpt-5.3-codex-spark exec "Quick fix"
```

OpenClaw orchestrator (Opus) writes TASK.md + GOALS.md, delegates to Codex, reviews output.

### Via GitHub (To Enable)

Enable automatic PR review on `resonantos-alpha` and `resonantos-alpha`:

1. Connect GitHub account at https://chatgpt.com/codex
2. Enable code review per repo at https://chatgpt.com/codex/settings/code-review
3. Add `AGENTS.md` with review guidelines to repo root
4. Optionally enable auto-review on PR open

### Via Codex Cloud (Future)

Set up cloud environments for parallel background tasks that don't need local machine resources.

---

## 7. Workflow Patterns

### Bug Fix (CLI)
```
codex
> Bug: [description]. Repro: [steps]. Constraints: [limits].
> Start by reproducing, then propose a patch and run checks.
```

### Feature Build (CLI exec via OpenClaw)
```bash
codex exec "Build [feature]. Read TASK.md and GOALS.md for requirements."
```

### Code Review (Local)
```
codex
> /review
```
Options: review against branch, uncommitted changes, specific commit, or custom instructions.

### Code Review (GitHub)
```
@codex review
@codex review for security vulnerabilities
```

### Prototype from Screenshot
```bash
codex -i mockup.png "Create this UI. Use React + Tailwind."
```

### Multi-Agent Parallel Review
```
Spawn one agent per review dimension:
1. Security
2. Code quality
3. Bugs
4. Race conditions
5. Test flakiness
6. Maintainability
```

---

## 8. Action Items

- [ ] Create `~/.codex/config.toml` with our preferences (model, reasoning effort, multi-agent)
- [ ] Create `AGENTS.md` in `resonantos-alpha/` root with build/test/review guidelines
- [ ] Connect GitHub at chatgpt.com/codex and enable code review for both repos
- [ ] Enable auto-review on PRs for `resonantos-alpha` (public repo)
- [ ] Test `@codex review` on a PR
- [ ] Explore Codex Cloud for parallel background tasks

## Related

- `SSOT-L1-OPENAI-PRO-VIA-CODEX.md` -- Provider routing and model access
- OpenClaw coding-agent skill: `/opt/homebrew/lib/node_modules/openclaw/skills/coding-agent/SKILL.md`
- Codex CLI source: https://github.com/openai/codex
- Full docs: https://developers.openai.com/codex