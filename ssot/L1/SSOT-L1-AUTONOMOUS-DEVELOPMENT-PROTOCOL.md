# Autonomous Development Protocol — Architecture

| Field | Value |
|-------|-------|
| ID | SSOT-L1-AUTONOMOUS-DEV-PROTOCOL-V1 |
| Level | L1 (Architecture — Truth) |
| Created | 2026-02-27 |
| Status | Active |
| Stale After | Review quarterly |
| Related | SSOT-L1-SELF-IMPROVEMENT-PROTOCOL.md, DELEGATION_PROTOCOL.md |
| Self-Referential | This protocol was developed using itself. |

---

## The Problem

Design-level work (new systems, protocols, architectures) is done ad-hoc. The AI has a bias toward action: design something, immediately try to build/deploy it. This skips stress-testing, opportunity scanning, human perspective, and deterministic auditing. The result is weaker output that the human must then correct — wasting human attention, which is the scarcest resource.

## The Solution: Composable Operations Toolkit

Seven operations that compose dynamically. Not a pipeline — a toolkit. The AI selects operations based on what the work needs. Operations can repeat, branch, and trigger each other.

### Operations

| Operation | What it does | When to use |
|---|---|---|
| **Architect** | Design a solution from requirements | Starting point for new work |
| **Self-debate** | Stress-test from adversarial angles (Alpha/Beta personas) | After architecture. After opportunity scan. After any major change. Can repeat. |
| **Opportunity scan** | Look for what else this enables (content, tools, community, benchmarks) | After self-debate. After building. Any time new possibilities emerge. |
| **Human perspective** | Apply known challenge patterns from memory logs | After architecture. Before building. After self-debate. |
| **Deterministic audit** | What can be code instead of AI? Map each step. | Before building. After human perspective. |
| **Build** | Write TASK.md, delegate to Codex, review output | When design is stable. |
| **Verify** | Test the built thing with deterministic commands | ALWAYS after build. Non-negotiable. |

### Composition Rules

1. **Free sequencing.** Any operation can follow any other. Self-debate can run 3 times if each round surfaces new tension.
2. **Mandatory minimum (design-level work).** Before build: self-debate AND deterministic audit must have run at least once.
3. **Verify always follows build.** No exceptions.
4. **Operations can trigger each other.** Self-debate surfaces a gap → opportunity scan. Opportunity scan finds something → self-debate on that. Human perspective raises concern → deterministic audit.
5. **Self-referential requirement.** Any new protocol or system must have the toolkit applied to its own design before being declared ready.

### Trigger Levels

| Work type | Toolkit requirement | Examples |
|---|---|---|
| **Design-level** | Full toolkit mandatory (minimum: self-debate + deterministic audit + verify) | New protocol, new architecture, new system, strategic decision, new agent design |
| **Build-level (large)** | Toolkit recommended. DELEGATION_PROTOCOL.md mandatory. | >3 files, >100 lines, new feature |
| **Build-level (small)** | DELEGATION_PROTOCOL.md only. Toolkit optional. | Bug fix, config change, ≤3 files, ≤100 lines |
| **Urgent** | Escape hatch: skip toolkit, log skip as lesson. If skips repeat → protocol is too heavy → simplify. | Genuine emergency, time-critical fix |

### Detection (Deterministic)

How to classify work type automatically:

| Signal | Classification |
|---|---|
| Keywords: "new protocol", "architecture", "system design", "new agent", "strategic" | Design-level |
| TASK.md scope: >3 files OR >100 lines OR new directory | Build-level (large) |
| TASK.md scope: ≤3 files AND ≤100 lines | Build-level (small) |
| Human says "urgent", "now", "quick fix" | Urgent (escape hatch) |

## Enforcement

### Pre-Build Gate (Deterministic)

Before any Codex delegation for design-level work:

1. Check: does TASK.md reference a self-debate output? (file path or inline section)
2. Check: does TASK.md include a deterministic audit table? (step → deterministic Y/N)
3. If both present → proceed to build
4. If either missing → block delegation, log enforcement event, prompt: "This is design-level work. Self-debate and deterministic audit are required before building."

Implementation: extend Shield Gate's Direct Coding Gate to check TASK.md content before allowing `codex exec`.

### Operation Tracking (Deterministic)

Every operation execution is logged:

**File:** `self-improver/protocol-runs.jsonl`

```json
{
  "ts": "2026-02-27T10:00:00Z",
  "subject": "Autonomous Development Protocol",
  "operation": "self-debate",
  "rounds": 6,
  "tensionPoints": 6,
  "keyFindings": ["enforcement must be external", "mandatory vs optional ops", "two trigger levels"]
}
```

This enables: tracking which operations run most, which get skipped, whether skip patterns correlate with build failures.

### Quality Feedback Loop (Deterministic)

After any build governed by this protocol:
1. Log outcome: success/failure/needs-revision
2. If failure → which operations ran? Which were skipped?
3. If skipped operations correlate with failures → the skip pattern becomes a lesson → self-improvement engine processes it

## Virtual Manolo (Enhancement, Not Dependency)

The protocol works without Virtual Manolo. When pattern extraction from memory logs is validated, it becomes an additional operation.

**Current status:** Conceptual. Pattern types identified but not extracted.

**Pattern types to extract:**
- Challenge patterns: what Manolo pushes back on (human burden, unnecessary complexity, AI doing script work)
- Reframe patterns: how he sees opportunities inside problems
- Accept patterns: what he approves without friction (first-principles alignment, data-backed decisions)
- Reject patterns: what he blocks (hope-based enforcement, maintenance burdens)

**Validation criteria:** Run Virtual Manolo on 5 past design decisions where we have Manolo's actual response. Compare predicted challenges to actual challenges. If >60% overlap → validated, add to toolkit. If <60% → more pattern extraction needed.

## Self-Referential Verification

This protocol was developed using its own operations:

| Operation | Applied to this protocol? | Result |
|---|---|---|
| Architect | YES | V1 linear pipeline designed |
| Self-debate (round 1) | YES (7 rounds, pre-V1.2) | 6 blind spots found |
| Human perspective | YES (Manolo, live) | Repetition threshold, minimise human involvement, daily cadence |
| Opportunity scan | YES | Content opportunity, benchmark mapping, community tool potential |
| Self-debate (round 2) | YES (6 rounds, on V2) | Enforcement must be external, mandatory/optional split, trigger levels, Virtual Manolo as enhancement |
| Deterministic audit | YES | Trigger classification, operation gate, tracking = deterministic. Self-debate, opportunity scan = AI. |
| Build | NEXT | Engine + enforcement rules |
| Verify | NEXT | Test the gates |

## Anti-Patterns

| Anti-Pattern | Why it fails |
|---|---|
| "I'll self-debate later" | Action bias. Later = never. Gate enforces. |
| Running self-debate with 1 round | No tension emerged. Minimum 5 rounds per skill spec. |
| Skipping deterministic audit | Builds AI-dependent systems where scripts suffice. Costs more, less reliable. |
| Treating Virtual Manolo as requirement before it's validated | Blocks progress on unvalidated capability. Protocol must work without it. |
| Applying full toolkit to trivial work | Overhead kills velocity. Trigger levels exist for this reason. |
| Self-assessing protocol compliance | Fox guarding henhouse. External gate required. |

## Change Log

| Date | Change |
|------|--------|
| 2026-02-27 | V1 created. Toolkit model (7 operations, composable). Two trigger levels (design vs build). Self-referential verification. Pre-build gate. Virtual Manolo as enhancement. Developed using its own process (2 self-debates, 1 human perspective round, 1 deterministic audit, 1 opportunity scan). |
