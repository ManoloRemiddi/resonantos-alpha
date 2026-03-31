[AI-OPTIMIZED] ~380 tokens | src: SSOT-L1-OPENAI-CODEX.md | Updated: 2026-03-10

| Field | Value |
|-------|-------|
| ID | SSOT-L1-OPENAI-CODEX-V1 | Level | L1 | Status | Active |
| Created | 2026-02-22 | Stale After | 60 days |

## Overview
OpenAI Codex = full coding agent platform (not just CLI). 4 surfaces via one ChatGPT Pro account, zero marginal cost.

| Surface | Description | Use |
|---------|-------------|-----|
| **Codex CLI** | Local terminal agent (Rust, OSS) | Pair programming, `codex exec` from OpenClaw |
| **Codex Cloud** | Remote sandboxed VMs | Background/parallel tasks, PRs from cloud |
| **Codex Web App** | chatgpt.com/codex | Command center for cloud tasks |
| **GitHub Integration** | @codex in issues/PRs | Code review, task delegation |

## Models
| Model | Speed | Best For |
|-------|-------|----------|
| gpt-5.3-codex | Med | Complex coding/architecture (default) |
| gpt-5.3-codex-spark | Fast | Day-to-day coding (Pro only, research preview) |
| gpt-5.1-codex-mini | Fast | Routine tasks, ~4x usage extension |

## Pro Limits (per 5h window)
Local msgs: 300-1500 | Cloud tasks: 50-400 | Code reviews/week: 100-250
Use gpt-5.1-codex-mini for ~4x more messages.

## CLI Usage (via OpenClaw)
```bash
codex exec "prompt"                          # non-interactive (primary mode)
codex -m gpt-5.3-codex-spark exec "quick"   # model override
codex resume --last                          # resume session
codex exec resume --last "continue"          # non-interactive resume
```
Sessions stored: `~/.codex/sessions/`

## Approval Modes
Auto (default): read/edit/run in workdir | Read-only: browse only | --yolo: no restrictions

## Web Search
Default: cached | `--search` or `web_search="live"` for live | `"disabled"` to turn off

## Multi-Agent (Experimental)
Enable in `~/.codex/config.toml`: `[features] multi_agent = true`
Define roles with `[agents.reviewer]` etc., each with own model/mode/instructions.

## MCP
Codex connects to MCP servers and can run AS MCP server for other agents.

## GitHub Integration
1. chatgpt.com/codex/settings/code-review → enable auto-review per repo
2. Comment `@codex review` on any PR → Codex posts P0/P1 findings
3. Comment anything else → starts cloud task
4. Reads `AGENTS.md` — add review guidelines there

## AGENTS.md System
Precedence: `~/.codex/AGENTS.md` → git-root → cwd. Max 32KiB. Add build/test/style/security rules.

## Config (`~/.codex/config.toml`)
```toml
model = "gpt-5.3-codex"
model_reasoning_effort = "high"
web_search = "live"
[features]
multi_agent = true
project_doc_max_bytes = 65536
```

## Our Usage Patterns
| Task | Command |
|------|---------|
| Feature build | `codex exec "Build X. Read TASK.md and GOALS.md"` |
| Bug fix | `codex` → describe bug → propose + test |
| PR review | `@codex review` or `codex` → `/review` |
| Prototype from image | `codex -i mockup.png "Create this UI"` |

## Action Items
- [ ] Create `~/.codex/config.toml`
- [ ] Create `AGENTS.md` in resonantos-alpha/
- [ ] Connect GitHub, enable code review for both repos
- [ ] Test `@codex review` on a PR
- [ ] Explore Codex Cloud for parallel tasks
