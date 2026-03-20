# Onboarding Agent — Project SSoT (L2)

| Field | Value |
|-------|-------|
| ID | SSOT-L2-ONBOARDING-AGENT-V1 |
| Level | L2 (Project) |
| Created | 2026-02-27 |
| Status | Design |
| Stale After | Review monthly |
| Related | SSOT-L1-SSOT-QUALITY-STANDARD.md, SSOT-L1-SYSTEM-OVERVIEW.md, SSOT-L1-AUTONOMOUS-DEVELOPMENT-PROTOCOL.md |

---

## The Problem

When a new user installs ResonantOS (or OpenClaw with ResonantOS extensions), the system starts empty. No SSoT documents, no SOUL.md calibrated to the user, no delegation rules, no memory structure. The user must either:

1. Write all configuration documents manually (unrealistic — they don't know the format)
2. Copy templates and modify them (better but still requires understanding the system)
3. Wait for the orchestrator to build everything over time (slow, ad-hoc, inconsistent)

None of these produce reliable results. The system's power is proportional to the quality of its specification documents. Poor initial setup means poor performance, which means the user concludes "this doesn't work" and leaves.

**Manolo's directive:** We shouldn't rely on the human's capabilities to achieve high augmentation. The AI must master specification engineering so the human doesn't have to.

## The Solution: A First-Run Onboarding Agent

A lightweight agent that runs on first installation (or on demand) and produces the minimum viable document set for a functional ResonantOS system. The agent interviews the user through a short structured conversation, then generates validated documents.

## Architecture

```
User installs ResonantOS
    ↓
First run detected (no SOUL.md exists)
    ↓
Onboarding agent spawned (isolated session)
    ↓
Structured interview (5-10 questions)
    ↓
Document generation (templates + user input)
    ↓
Validation (ssot-validator.js on every generated doc)
    ↓
User review + approval
    ↓
Documents committed to workspace
```

### Interview Structure

The interview is NOT freeform. It's a structured sequence designed to extract the minimum information needed for document generation. Each question maps to specific document fields.

| Question | Maps To | Example |
|----------|---------|---------|
| What's your name? | USER.md name, SOUL.md boundaries | "Manolo" |
| What do you do professionally? | USER.md context, SOUL.md philosophy | "Composer, photographer, AI strategist" |
| How do you prefer to communicate? (short/detailed, formal/casual) | SOUL.md style section | "Short, direct, no filler" |
| What are your top 3 values? | SOUL.md core principles | "Logic, honesty, data-driven decisions" |
| What annoys you about AI assistants? | SOUL.md anti-patterns, behaviour constraints | "Sycophancy, filler, fake confidence" |
| What's your primary project or goal? | Initial L2 SSoT | "Building a decentralised AI governance system" |
| What tools do you use daily? | TOOLS.md, initial integrations | "VS Code, Terminal, Telegram" |
| What's your timezone? | USER.md, cron scheduling | "Europe/Rome" |

### Document Generation

From the interview, the agent generates:

| Document | Source | Validated By |
|----------|--------|-------------|
| SOUL.md | Interview Q2-Q5 + templates | Manual review (identity doc) |
| USER.md | Interview Q1, Q6-Q8 | ssot-validator.js (structural) |
| IDENTITY.md | System detection + Q1 | ssot-validator.js |
| TOOLS.md | Interview Q7 + system scan | ssot-validator.js |
| AGENTS.md | Default template (standard) | ssot-validator.js |
| HEARTBEAT.md | Default template + timezone | ssot-validator.js |
| DELEGATION_PROTOCOL.md | Standard (copied) | Already validated |
| ssot/L0/ initial docs | Interview Q2, Q4 + templates | ssot-validator.js (L0 rules) |

### Generation Rules

1. **Templates, not freeform.** Each document starts from a validated template. The agent fills in user-specific values. This ensures structural compliance.
2. **Validator runs on every output.** Before presenting any document to the user, `ssot-validator.js` checks it. If validation fails, the agent fixes the document (up to 3 attempts) before presenting.
3. **User reviews all identity documents.** SOUL.md and USER.md are always shown for approval. The user can edit them. Other documents are generated silently unless the user asks to review.
4. **Defaults are opinionated.** The agent doesn't ask "do you want a heartbeat?" — it sets up heartbeats with sensible defaults. The user can change later. Decision bias: good defaults > choice paralysis.
5. **System scan for TOOLS.md.** The agent runs `which` checks for known tools (git, gh, docker, node, python, ffmpeg, etc.) and pre-populates TOOLS.md with what's available.

### Quality Enforcement

The onboarding agent embodies all four prompting disciplines from the video analysis:

| Discipline | How the Agent Applies It |
|------------|------------------------|
| Prompt Craft | Templates are pre-structured with correct headings, sections, and minimum content |
| Context Engineering | Interview extracts exactly the tokens needed — no more, no less |
| Intent Engineering | SOUL.md generation encodes the user's values, communication style, and anti-patterns as explicit constraints |
| Specification Engineering | Every generated document passes ssot-validator.js — machine-readable from birth |

### Escalation Triggers

The onboarding agent stops and asks the user if:
- Any answer is too short to generate meaningful content (<10 chars for a values question)
- The user's stated preferences contradict each other
- The system scan detects unusual environment (no git, no shell access)
- Validator fails 3 times on the same document (structural issue in template)

## Current State

**Status: Design phase.** No code exists yet.

**Dependencies ready:**
- ✅ ssot-validator.js (built today)
- ✅ SSoT Quality Standard (L1 doc, built today)
- ✅ DELEGATION_PROTOCOL.md v2 (tiered, built today)
- ✅ Template documents (SOUL.md, USER.md, AGENTS.md exist as references)

**Dependencies needed:**
- Template files in a `templates/` directory (extracted from current workspace files)
- Onboarding agent registered in OpenClaw agent config
- Interview script (structured conversation flow)

## What's Next

1. **Extract templates** from current workspace files (SOUL.md → soul-template.md, etc.)
2. **Build interview script** as a structured conversation flow (state machine, not freeform)
3. **Build generation engine** that fills templates from interview answers
4. **Wire to ssot-validator.js** for output validation
5. **Test with fresh workspace** (empty directory, simulate new user)
6. **Register as OpenClaw agent** with appropriate model (cheap — gpt-4o-mini sufficient)

## Anti-Patterns

| Anti-Pattern | Why It Fails |
|---|---|
| Freeform conversation ("tell me about yourself") | Extracts vague, unstructured data that doesn't map to document fields |
| Generating SOUL.md without user review | Identity documents must have human approval |
| Asking 20+ questions | User abandons onboarding. 8 questions max. |
| Generating documents without validation | Structural errors propagate and degrade system performance |
| Using expensive model for onboarding | One-time task, template-based — gpt-4o-mini is sufficient |
| Skipping system scan | Miss available tools, produce incomplete TOOLS.md |

## Metrics (Post-Launch)

- Onboarding completion rate (% of users who finish all 8 questions)
- Document validation pass rate (% of generated docs that pass on first attempt)
- Time to first useful interaction (from install to first real task delegation)
- User edit rate on generated docs (high = templates need improvement)

## Change Log

| Date | Change |
|------|--------|
| 2026-02-27 | V1 created. Interview-based architecture. 8 questions, 8 document outputs. Validator-gated. Template-first generation. |
