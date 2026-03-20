# SSOT-L2-SETUP-AGENT — ResonantOS Setup Agent

| Field | Value |
|-------|-------|
| **ID** | `SSOT-L2-SETUP-AGENT-V1` |
| **Created** | 2026-02-25 |
| **Updated** | 2026-02-25 |
| **Author** | Augmentor + Manolo |
| **Level** | L2 (Project) |
| **Status** | Alpha — First build |

---

## Purpose

An AI agent that ships with every ResonantOS installation and helps users configure their system through a structured conversational interview. Solves the "intent engineering" problem: instead of hoping users manually configure all files correctly, the Setup Agent extracts their intent, organizes their data, identifies gaps, and generates the configuration files that make ResonantOS aligned with THEIR specific goals.

## Why This Exists

1. **The Klarna Problem:** AI deployed without encoded intent optimizes for measurable goals (speed, cost) while destroying unmeasured goals (quality, trust, relationships). The Setup Agent forces intent configuration BEFORE the AI starts working.
2. **Configuration Complexity:** ResonantOS has SOUL.md, USER.md, INTENT.md, Creative DNA, SSoT hierarchy, Shield rules, Logician policies, R-Memory config, R-Awareness keywords. Manual setup is error-prone and incomplete.
3. **B0 Readiness:** The Benchmark Agent's B0 (System Readiness) gate measures alignment quality. The Setup Agent is what GETS users to high B0 scores.
4. **Democratization:** Compresses what took Manolo+Augmentor weeks of calibration into hours of structured conversation.

## Architecture

The Setup Agent is an OpenClaw agent (`setup`) that:
- Runs as a spawned sub-agent or direct conversation
- Has read/write access to the workspace
- Knows the ResonantOS file structure intimately
- Conducts a multi-phase interview
- Generates files in the correct locations
- Runs B0 readiness checks after configuration

## Interview Flow

### Phase 0: System Check
- Verify OpenClaw is running
- Check which ResonantOS components are installed (extensions, Logician, Shield)
- Report current state: "Your system has X installed, Y missing"

### Phase 1: INGEST
- "Upload everything: business plan, CV, projects, notes, goals, any existing docs"
- User provides raw materials (files, text, links)
- Agent organizes into SSoT hierarchy (L0-L4)
- Agent reads and analyzes all provided materials

### Phase 2: EXTRACT IDENTITY
From ingested materials, generate:
- `USER.md` — preferences, communication style, values, timezone, context
- SOUL.md customizations — what overrides matter to THIS user
- Creative DNA — creative identity, voice, aesthetic, influences
- `INTENT.md` — goals, tradeoffs, decision boundaries, escalation rules

### Phase 3: GAP ANALYSIS
Structured interview filling specific gaps:
- "I see your business plan but no decision framework — how do you prioritize when speed conflicts with quality?"
- "Your Creative DNA mentions authenticity but I don't have examples — show me 3 pieces of content you're proud of"
- "What are your absolute boundaries? Things your AI should NEVER do?"
- Shield rules: "What files/directories should be protected?"
- Logician policies: "Which agents should your system have? What trust levels?"

### Phase 4: CONFIGURE COMPONENTS
Based on gathered data:
- Generate Logician rules (agent registry, spawn control, tool permissions, cost policy)
- Configure Shield rules (protected paths, forbidden patterns)
- Set up R-Awareness keywords (what SSoT docs to inject and when)
- Configure R-Memory parameters (based on usage patterns)

### Phase 5: VALIDATE
- Present back: "Here's what I understand about you and your goals"
- User corrects, refines, approves
- Agent generates final docs
- Run B0 readiness check → confirm alignment score

### Phase 6: HANDOFF
- "Your system is configured. B0 score: X/12. Gaps: [if any]"
- Main orchestrator agent takes over with full context
- Setup Agent available for recalibration anytime

## Files Generated

| File | Location | Purpose |
|------|----------|---------|
| USER.md | workspace/ | Human identity and preferences |
| SOUL.md customizations | workspace/ | Behavioral overrides |
| INTENT.md | workspace/ | Goals, tradeoffs, decision boundaries |
| Creative DNA | ssot/L0/ or ssot/private/ | Creative identity |
| Business context | ssot/L0/ | Mission, strategy |
| Logician rules | logician/rules/production_rules.mg | Policy enforcement |
| Shield config | shield/ | File protection rules |
| R-Awareness keywords | r-awareness/keywords.json | Context injection mapping |
| R-Memory config | r-memory/config.json | Compression parameters |

## B0 Readiness Checks

After setup, the agent runs these checks:

### Human-System Alignment
- [ ] USER.md exists and is specific (not template)
- [ ] INTENT.md exists with structured goals
- [ ] Creative DNA documented (if applicable)
- [ ] Decision framework defined
- [ ] Boundaries and safety rules explicit

### Self-Awareness
- [ ] System knows it's running ResonantOS
- [ ] Memory architecture configured (R-Memory)
- [ ] SSoT hierarchy populated (at least L0, L1)
- [ ] Tool capabilities documented
- [ ] Orchestrator role defined

### Component Readiness
- [ ] Logician rules loaded and service running
- [ ] Shield active
- [ ] R-Awareness keywords configured
- [ ] Extensions installed (r-memory.js, r-awareness.js)

## Implementation

- Agent ID: `setup`
- Model: Uses defaults (Opus for quality — this is a one-time setup, worth the tokens)
- Workspace: Same as main agent (needs to write to the same locations)
- Distribution: Ships with `resonantos-alpha`, installed via `install.js`

## Revenue / Community Alignment

- **Free tier:** Basic setup (USER.md, simple SOUL.md, default Logician rules)
- **Alpha members:** Full intent engineering (Creative DNA, INTENT.md, custom Logician rules, Shield configuration)
- The B0 score difference between tiers IS the selling point

## References

- **Depends On:** SSOT-L2-INTERNAL-BENCHMARKS (B0 checks), SSOT-L1-LOGICIAN, SSOT-L1-SHIELD
- **Inspired By:** Dave Shapiro's "intent engineering" concept, Klarna case study
- **Related:** Benchmark Agent (measures what Setup Agent configures)
