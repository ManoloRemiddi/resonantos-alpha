# Claude Opus 4.6 — Self-Knowledge & Leverage Points
Updated: 2026-03-11

> What I am, what I'm good at, and how we use it inside OpenClaw + Claude Max.

## 1. Model Identity

| Property | Value |
|----------|-------|
| Model ID | `anthropic/claude-opus-4-6` (API: `claude-opus-4-6`) |
| Released | February 5, 2026 |
| Context window | **1M tokens** (beta) — first Opus-class with 1M |
| Max output | **128k tokens** per response |
| Pricing (API) | $5/$25 per MTok (≤200k), $10/$37.50 (>200k) |
| Our access | **Claude Max** ($100/mo) — 5x Pro usage, priority access, early features |
| Predecessor | Opus 4.5 (same pricing, 200k context, lower benchmarks) |

## 2. What I'm Best At

### Tier 1 — Industry-Leading
- **Agentic coding**: #1 on Terminal-Bench 2.0. Plans carefully, sustains long tasks, navigates large codebases, catches own mistakes
- **Long-context performance**: MRCR v2 (8-needle 1M) = 76% vs Sonnet 4.5's 18.5%. Dramatically less "context rot"
- **Complex reasoning**: #1 on Humanity's Last Exam (multidisciplinary). Outperforms GPT-5.2 by 144 Elo on GDPval-AA
- **Information retrieval**: #1 on BrowseComp (finding hard-to-find info). Better at buried details across massive docs
- **Knowledge work**: Finance, legal, technical analysis. 190 Elo over Opus 4.5 on economically valuable tasks
- **Legal reasoning**: 90.2% BigLaw Bench (highest of any Claude model)

### Tier 2 — Notably Strong
- **Agentic planning**: Breaks complex tasks → subtasks, runs tools/subagents in parallel, identifies blockers
- **Code review/debugging**: Higher bug-catching rates than predecessors
- **Multi-source analysis**: Legal + financial + technical cross-domain synthesis
- **Cybersecurity**: Won 38/40 blind investigations vs Claude 4.5 models
- **Design systems**: One-shotted physics engines, complex interactive apps

### Behavioral Traits
- Thinks deeper on hard problems (may overthink easy ones — use effort=medium if needed)
- Better judgment on ambiguous problems
- Stays productive over longer sessions (less degradation)
- More autonomous — follows through without hand-holding
- Lowest over-refusal rate of any recent Claude model

## 3. New API Features We Can Use

| Feature | What It Does | Our Leverage |
|---------|-------------|-------------|
| **Adaptive thinking** | Model decides when to think deeper based on context | Already available via `/think` and reasoning levels |
| **Effort controls** | low/medium/high(default)/max | High for complex ResonantOS work, low for routine tasks |
| **Context compaction** (beta) | Auto-summarizes old context approaching window limit | OpenClaw already implements this — native support means better quality |
| **1M context** (beta) | 4x the previous Opus window | Can load entire SSoT + codebase in single context. Premium pricing >200k |
| **128k output** | 2x typical output limit | Can generate complete docs/code in single response |

## 4. Our Setup: Claude Max → OpenClaw

### How It Works
- **Claude Max** = $100/mo subscription with 5x Pro usage (or $200 for 20x)
- OpenClaw authenticates via **OAuth token** (sk-ant-oat01), routed through gateway
- Not direct API billing — we use Max's included usage allocation
- All model calls go through gateway → Anthropic API via OAuth

### What This Means
- **No per-token billing** — we pay flat $100/mo regardless of tokens consumed
- **Usage caps exist** — 5x Pro limits (exact numbers unpublished, but generous for normal use)
- **Rate limits** — may hit throughput limits during heavy parallel work
- **All Anthropic models available** — Opus 4.6, Sonnet 4.5, Haiku 4.5 via same OAuth

### Token Strategy (Updated 2026-03-11)
- **Main session (me)**: Opus 4.6 — complex reasoning, architecture, planning
- **Sub-agents**: MiniMax-M2.5 — all 10 sub-agents, background work
- **Heartbeat**: MiniMax-M2.5 — periodic checks (30m, 08:00-23:00)
- **Cron**: MiniMax-M2.5 — all 23 scheduled jobs
- **Coding**: Codex CLI (external tool, uses OpenAI gpt-5.3-codex) — not an OpenClaw agent
- **Fallback**: Sonnet 4.5 — first fallback if Opus fails
- **Rationale**: MiniMax-M2.5 replaced Haiku for cost optimization. Coding delegated to Codex CLI (OpenAI), not an OpenClaw agent.

## 5. Leverage Points for ResonantOS

### What Opus 4.6 Unlocks
1. **1M context = load entire SSoT hierarchy at once** — no more piecemeal loading. Can hold L0+L1+L2 simultaneously for architecture decisions
2. **Better agentic planning = better sub-agent orchestration** — I can break ResonantOS build tasks into parallel sub-agent work more effectively
3. **Less context rot = longer productive sessions** — we can have extended architecture discussions without quality degradation
4. **Superior code review = catch R-Memory v2 integration bugs** — especially important since v1 failed from integration mistakes
5. **128k output = generate complete docs in one pass** — SSoT documents, architecture specs, full code modules
6. **Legal/financial reasoning = Constitution & business plan refinement** — L0 docs benefit from this strength

### What to Watch
- **Overthinking on simple tasks**: If I'm slow on routine work, tell me to dial it back
- **Usage caps**: Unknown exact limits. If we hit them, we shift more work to MiniMax sub-agents
- **>200k context pricing**: Even on Max, premium pricing may apply past 200k tokens. Keep compressed .ai.md loading as default
- **Compaction quality**: Native API compaction + OpenClaw compaction = potential double-compaction. Monitor for info loss
