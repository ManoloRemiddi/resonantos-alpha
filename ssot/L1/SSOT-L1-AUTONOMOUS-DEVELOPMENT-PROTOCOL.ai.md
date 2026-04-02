[AI-OPTIMIZED] ~320 tokens | src: SSOT-L1-AUTONOMOUS-DEVELOPMENT-PROTOCOL.md | Updated: 2026-03-10

| Field | Value |
|-------|-------|
| ID | SSOT-L1-AUTONOMOUS-DEV-PROTOCOL-V1 |
| Level | L1 | Status | Active | Created | 2026-02-27 |
| Related | SSOT-L1-SELF-IMPROVEMENT-PROTOCOL, DELEGATION_PROTOCOL |
| Self-ref | Developed using itself (2 self-debates, 1 human perspective, 1 deterministic audit, 1 opportunity scan) |

## Problem
Ad-hoc design → AI action bias → skips stress-testing → weaker output → wastes human attention (scarcest resource).

## Composable Operations Toolkit (7 ops, not pipeline)

| Op | Purpose | Trigger |
|----|---------|---------|
| **Architect** | Design from requirements | Starting point |
| **Self-debate** | Adversarial stress-test (Alpha/Beta personas) | After arch. After opp-scan. After any major change. Can repeat. |
| **Opportunity scan** | What else does this enable? | After self-debate. After build. Any time. |
| **Human perspective** | Apply known challenge patterns from memory | After arch. Before build. After self-debate. |
| **Deterministic audit** | What can be code vs AI? | Before build. After human perspective. |
| **Build** | Write TASK.md → delegate Codex → review | When design stable. |
| **Verify** | Deterministic test of built thing | ALWAYS after build. Non-negotiable. |

## Composition Rules
1. Free sequencing — any op can follow any other
2. **Mandatory minimum (design-level):** self-debate + deterministic audit before build
3. **Verify always follows build** — no exceptions
4. Ops can chain-trigger each other
5. New protocols must have toolkit applied to own design before declared ready

## Trigger Levels

| Work Type | Requirement |
|-----------|-------------|
| Design-level | Full toolkit mandatory (min: self-debate + det. audit + verify) |
| Build-level large (>3 files or >100 lines) | Toolkit recommended. DELEGATION_PROTOCOL mandatory. |
| Build-level small (≤3 files, ≤100 lines) | DELEGATION_PROTOCOL only. Toolkit optional. |
| Urgent | Escape hatch: skip, log skip as lesson. Repeated skips → simplify protocol. |

## Detection (Deterministic)
"new protocol/architecture/system design/strategic" → Design-level
TASK.md >3 files OR >100 lines OR new dir → Build-large
≤3 files AND ≤100 lines → Build-small
"urgent/now/quick fix" → Escape hatch

## Enforcement
**Pre-Build Gate:** Check TASK.md references self-debate output AND contains deterministic audit table. Both present → proceed. Either missing → block, log, prompt. (Implemented in Shield Gate Direct Coding Gate.)
**Tracking:** `self-improver/protocol-runs.jsonl` — ts, subject, operation, rounds, tensionPoints, keyFindings.
**Quality Feedback:** After build → log success/failure → correlate with skipped ops → lesson to self-improvement engine.

## Virtual Manolo (Enhancement, Not Dependency)
Pattern types to extract from memory: challenge, reframe, accept, reject patterns.
Validation: Run on 5 past decisions, compare predicted vs actual challenges. ≥60% overlap → validated. Not required for protocol operation.

## Anti-Patterns
"I'll self-debate later" | 1-round debate (min 5) | Skip deterministic audit | Virtual Manolo as requirement | Full toolkit on trivial work | Self-assessing compliance (external gate required)
