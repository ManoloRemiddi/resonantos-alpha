# PROTO-DEVELOPMENT — Autonomous Development Protocol

> **Trigger keywords:** new protocol, new architecture, new system, design, strategic decision, overnight work, roadmap item
> **Level:** L1(P) — Protocol
> **Enforcement:** R-Awareness injection + Logician pre-build gate
> **Full spec:** `ssot/L1/SSOT-L1-AUTONOMOUS-DEVELOPMENT-PROTOCOL.md`

---

## When This Activates

This protocol governs HOW you develop things. It is a toolkit of composable operations, not a linear pipeline.

**Trigger:** Any design-level work — new system, protocol, architecture, strategic decision, roadmap item, or autonomous work (overnight tasks, cron-spawned work).

**Does NOT trigger for:** Simple questions, config changes, bug fixes, small code tasks (<=3 files, <=100 lines). Those use PROTO-CODING or direct action.

## The Toolkit (7 Operations)

| Operation | Purpose |
|---|---|
| **Architect** | Design a solution from requirements |
| **Self-debate** | Stress-test adversarially (>=5 rounds, Alpha/Beta personas) |
| **Opportunity scan** | What else does this enable? Content, tools, benchmarks, community? |
| **Human perspective** | Apply known Manolo challenge patterns from memory logs |
| **Deterministic audit** | What can be code instead of AI? Map each component. |
| **Build** | Write TASK.md, delegate to Codex |
| **Verify** | Test with deterministic commands. ALWAYS after build. |

## Composition Rules

1. **Free sequencing.** Any operation can follow any other. Self-debate can repeat.
2. **Mandatory minimum before build:** Self-debate + deterministic audit must have run at least once.
3. **Verify always follows build.** No exceptions.
4. **Self-referential:** New protocols must have the toolkit applied to their own design.
5. **Log all operations** to `memory/protocol-runs.jsonl`.

## Two Usage Modes

### Autonomous Mode (overnight, cron, solo work)
Run the full toolkit on your own. Present Manolo with fortified result + "3 decisions I need your perspective on."

### Interactive Mode (conversation with Manolo)
When a conversation transitions from discussion to building something:
1. Recognize the transition (design-level work emerging)
2. Activate the protocol IN the background — structure your thinking with it
3. Continue the conversation with Manolo, but now with higher awareness
4. Operations happen naturally within the dialogue (Manolo IS the human perspective step)
5. Surface toolkit insights: "Self-debate surfaced X" or "Deterministic audit: Y could be code"

## Trigger Detection

| Signal | Classification |
|---|---|
| Keywords: "new protocol", "architecture", "new system", "strategic" | Design-level → full toolkit |
| Conversation shifts from discussion to "let's build this" | Design-level → activate toolkit |
| TASK.md scope: >3 files OR >100 lines OR new directory | Build-level large → toolkit recommended |
| TASK.md scope: <=3 files AND <=100 lines | Build-level small → skip toolkit |
| Human says "urgent", "quick fix" | Escape hatch → log the skip |

## Escape Hatch

If genuinely urgent: skip toolkit, build directly, log skip to `memory/lessons-queue.jsonl`. If skips form a pattern (repetition threshold >= 2), the protocol is too heavy — simplify it.

## Anti-Patterns

| Don't | Why |
|---|---|
| Use full toolkit for simple questions | Overhead destroys velocity |
| Skip self-debate because design "feels ready" | Rush-to-production bias. Documented failure mode. |
| Self-assess protocol compliance | Fox guarding henhouse. External enforcement required. |
| Run linearly step 1-7 every time | It's a toolkit, not a pipeline. Compose based on what the work needs. |

## WHY This Protocol Exists

2026-02-27: Designed the protocol itself, then immediately tried to skip to production use ("shall I start on the roadmap tonight?") without running the protocol on the protocol. Manolo had to stop the rush and contribute two fundamental improvements (flexible toolkit model, Virtual Manolo) that the AI missed entirely. A protocol that does not apply to itself is not a protocol — it is a document.
