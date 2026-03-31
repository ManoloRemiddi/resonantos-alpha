# SSOT-L1-ALIGNMENT-PROTOCOL — Community Alignment Verification

| Field | Value |
|-------|-------|
| **ID** | `SSOT-L1-ALIGNMENT-PROTOCOL-V1` |
| **Created** | 2026-02-27 |
| **Updated** | 2026-03-15 |
| **Author** | Manolo + Augmentor |
| **Level** | L1 (Architecture) |
| **Status** | Draft |
| **Stale After** | Review quarterly |

---

## 1. Purpose

This document is a **constitutional compiler** for the ResonantOS ecosystem. It serves two audiences simultaneously:

- **Humans** read the principles and understand what the project stands for.
- **AIs** evaluate contributions against structured criteria and produce an alignment report.

Any community member building for ResonantOS or the ResonantDAO feeds this document to their AI. The AI evaluates their work and returns a scored alignment report. This report can be attached to bounty submissions, PRs, or proposals as verifiable evidence of alignment.

**This is not a style guide.** It doesn't tell you *what* to build. It tells you *what boundaries to respect* while building whatever you want.

---

## 2. How to Use This Document

### For Contributors

```
1. Build your contribution (code, proposal, content, protocol)
2. Give this document to your AI alongside your work
3. Ask: "Evaluate this against the ResonantOS Alignment Protocol"
4. Review the alignment report
5. Fix any red-line violations
6. Submit your contribution with the alignment report attached
```

### For AIs Evaluating Contributions

When given this document and a contribution to evaluate:

1. Read the **Core Principles** (Section 3) — these are the philosophical foundation
2. Apply the **Alignment Tests** (Section 4) — structured yes/no/partial checks
3. Check for **Red Lines** (Section 5) — hard fail conditions
4. Apply the **Architectural Constraints** (Section 6) — technical compatibility
5. Score using the **Alignment Rubric** (Section 7)
6. Output a structured **Alignment Report** (Section 8)

---

## 3. Core Principles

These are the non-negotiable beliefs that define what ResonantOS is. Every contribution must be compatible with ALL of them.

### P1: Sovereignty Above All

Technology must increase the user's sovereignty, never decrease it. Every tool, feature, and system must leave the user with MORE control over their data, decisions, and digital life than they had before.

**Test:** After using this contribution, can the user walk away with their data? Can they switch providers? Can they run it locally? If no → sovereignty violation.

### P2: Augmentation, Not Replacement

AI augments human capability. It does not replace human judgment, creativity, or agency. The human is always the final decision-maker on matters of identity, philosophy, and creative direction.

**Test:** Does this contribution make the human more capable, or does it remove the human from the loop? Does it make decisions that should be human decisions?

### P3: Transparency Through Separation

Different types of contribution (human, AI, organizational) must be tracked separately. No mixing, no ambiguity. The system must always be able to answer: "Who did this? A human, an AI, or an organization?"

**Test:** Can the system determine whether this contribution came from a human, an AI, or an entity? Is that determination auditable?

### P4: Deterministic Enforcement Over Hope

Rules that matter must be enforced by code, not by prompts. Smart contracts > application guards > prompt instructions. If a rule can be coded, it must be coded. Trust is architectural, not behavioral.

**Test:** Is this rule enforced deterministically (code/contract), or does it rely on an AI "choosing" to comply?

### P5: Open Source, Local First

Core functionality must be open source. Computation should run locally when possible. Cloud dependencies must be optional, not mandatory. No vendor lock-in for essential features.

**Test:** Can this run without an internet connection? Without a specific provider? Is the source code available? If it requires a specific cloud service with no alternative, it fails.

### P6: Anti-Capture

No system should capture agency without consent. Every tool must have an exit path. No dark patterns, no lock-in, no "you need us to access your own data."

**Test:** Can the user export all their data? Can they stop using this tool without losing anything they created? Is there an alternative path?

### P7: Quality Over Speed

No quick fixes, no shortcuts, no temporary solutions that become permanent. Build properly the first time. Verified work only — "fixed" means tested, not "probably fixed."

**Test:** Has this been verified with deterministic evidence? Would the contributor stake their reputation on it?

### P8: Process Is the Product

How we build matters as much as what we build. The journey of building ResonantOS — the decisions, the mistakes, the pivots — is itself valuable content and knowledge. Document the process, not just the output.

**Test:** Is the reasoning behind this contribution documented? Can someone else understand WHY these decisions were made?

### P9: The Multiverse Over the Monoculture

We build for diversity of AI identities, not a single "correct" AI. Every ResonantOS installation should be unique — reflecting its human's identity, values, and creative vision. Homogeneity is the enemy.

**Test:** Does this contribution force a single way of doing things, or does it provide a framework that adapts to individual identity?

### P10: Human Accountability Chain

Every AI action must trace back to a human who is accountable. No orphaned bots, no autonomous systems without oversight, no AI that operates without a human governance chain.

**Test:** Can you identify which human is ultimately responsible for this AI's actions? Is that chain verifiable on-chain?

---

## 4. Alignment Tests

For each test, score: ✅ Pass | ⚠️ Partial | ❌ Fail | N/A (not applicable to this contribution type)

### Technical Alignment

| ID | Test | What to check |
|----|------|---------------|
| T1 | **Integrates, doesn't duplicate** | Does this work WITH existing ResonantOS components, or does it rebuild something that already exists? |
| T2 | **Local-first capable** | Can this run on the user's machine without cloud dependencies? |
| T3 | **Provider-agnostic** | Does this work with multiple AI providers, or is it locked to one? |
| T4 | **Data stays local** | Does user data leave the user's machine? If so, is it encrypted and consensual? |
| T5 | **Open source core** | Is the core functionality open source? (Premium features can be closed, core cannot) |
| T6 | **Deterministic where possible** | Are rules enforced by code rather than AI compliance? Could this be a script instead of an AI call? |
| T7 | **Fails safely** | If this breaks, does it fail silently/safely, or does it cause data loss or security exposure? |

### Philosophical Alignment

| ID | Test | What to check |
|----|------|---------------|
| A1 | **Increases sovereignty** | Does the user have MORE control after adopting this? |
| A2 | **Augments, doesn't replace** | Does this help the human do something better, or does it remove them from the process? |
| A3 | **Respects identity diversity** | Does this work across different ResonantOS configurations, or does it assume a specific setup? |
| A4 | **Transparent contribution tracking** | Can the system determine who (human/AI/entity) created this and how? |
| A5 | **Accountable AI chain** | If AI was involved, can the responsible human be identified? |
| A6 | **No capture** | Can the user stop using this without losing their data or capabilities? |
| A7 | **Process documented** | Is the reasoning behind design decisions recorded? |

### Economic Alignment

| ID | Test | What to check |
|----|------|---------------|
| E1 | **Fair token attribution** | Does the contribution correctly earn the right token type ($RCT/$ACT/$ECT)? |
| E2 | **No gaming vectors** | Could this be exploited to farm tokens without genuine contribution? |
| E3 | **Value to ecosystem** | Does this create genuine value for ResonantOS users, or is it self-serving? |
| E4 | **Sustainable cost** | Does this add ongoing cost (token burn, API calls) that's justified by its value? |

---

## 5. Red Lines (Hard Fail)

If ANY of these are true, the contribution is **rejected regardless of all other scores.**

| ID | Red Line | Why |
|----|----------|-----|
| R1 | **Exfiltrates user data to external servers without explicit consent** | Sovereignty violation — non-negotiable |
| R2 | **Requires a single specific cloud provider with no alternative** | Vendor lock-in = capture |
| R3 | **Removes human from governance chain** | AI without human accountability = uncontrolled |
| R4 | **Contains hardcoded secrets, API keys, or personal data** | Security breach — instant reject |
| R5 | **Claims "fixed" without verification evidence** | Verification Protocol violation |
| R6 | **Enables recursive AI self-replication without human authorization** | No unsupervised spawning |
| R7 | **Modifies L0 documents without governance proposal** | Constitutional changes require DAO vote |
| R8 | **Creates token-earning mechanisms that bypass quality gates** | Economic integrity violation |
| R9 | **Intentionally obfuscates what the code does** | Transparency violation — all code must be auditable |
| R10 | **Discriminates based on identity, origin, or belief** | Community integrity — non-negotiable |

---

## 6. Architectural Constraints

These are technical compatibility requirements, not philosophical judgments.

### 6.1 OpenClaw Compatibility

ResonantOS runs on OpenClaw. Contributions must integrate with — not fight against — the OpenClaw architecture:

- **Extensions** must use the OpenClaw extension API (hooks: `agent_start`, `agent_end`, `llm_output`, `session_before_compact`, etc.)
- **Memory** must use or extend the existing memory system (MEMORY.md, memory/*.md, memory_search), not create parallel memory stores
- **Tools** must register through OpenClaw's tool system, not bypass it
- **Configuration** must use `openclaw.json` patterns (hot-reloadable, `config.patch` for updates)

### 6.2 Solana Compatibility

On-chain components must:

- Use Solana DevNet for testing (mainnet only after audit)
- Follow the Symbiotic Wallet architecture (all DAO operations through Symbiotic PDA)
- Use Token-2022 for new token types
- Derive PDAs consistently (document derivation seeds)
- Support Phantom wallet for human signing

### 6.3 Dashboard Compatibility

Dashboard contributions must:

- Use the existing Flask + Jinja2 + vanilla JS stack (no npm, no bundlers)
- Follow the dark theme CSS variables
- Register routes in `server_v2.py`
- Follow the single-file backend principle (or propose a justified split)

### 6.4 SSoT Hierarchy

New documentation must:

- Use the correct level (L0=foundation, L1=architecture, L2=active projects, L3=drafts, L4=notes)
- Follow naming convention: `SSOT-L{level}-{NAME}.md`
- Include metadata header (ID, Created, Updated, Level, Status)
- Create `.ai.md` compressed variant if document exceeds 2000 tokens

---

## 7. Alignment Rubric

### Scoring

| Score | Meaning |
|-------|---------|
| 90-100 | **Fully Aligned** — Ready to merge/accept. Exemplary contribution. |
| 70-89 | **Aligned** — Minor adjustments needed. No principle violations. |
| 50-69 | **Partially Aligned** — Some concerns. Needs revision before acceptance. |
| 30-49 | **Misaligned** — Significant philosophical or technical conflicts. Major rework needed. |
| 0-29 | **Rejected** — Fundamental conflicts with core principles, or red-line violation. |

### Weight Distribution

| Category | Weight | Rationale |
|----------|--------|-----------|
| Red Lines (Section 5) | **Hard gate** | Any violation = score 0 regardless |
| Philosophical Alignment (Section 4, A1-A7) | **40%** | Philosophy IS the product |
| Technical Alignment (Section 4, T1-T7) | **35%** | Must work with the architecture |
| Economic Alignment (Section 4, E1-E4) | **15%** | Token economy integrity |
| Process & Documentation (P7, P8) | **10%** | How it was built matters |

---

## 8. Alignment Report Format

When evaluating a contribution, the AI must output a structured report:

```markdown
# Alignment Report

## Contribution
- **Type:** [code | proposal | content | protocol | bounty | other]
- **Description:** [one-line summary]
- **Author:** [contributor identifier]
- **Date:** [evaluation date]

## Red Line Check
| ID | Status | Notes |
|----|--------|-------|
| R1 | ✅/❌ | ... |
| ... | ... | ... |

**Red Line Result:** PASS / FAIL (if FAIL → overall score = 0, stop here)

## Alignment Tests
### Technical
| ID | Score | Notes |
|----|-------|-------|
| T1 | ✅/⚠️/❌/N/A | ... |
| ... | ... | ... |

### Philosophical  
| ID | Score | Notes |
|----|-------|-------|
| A1 | ✅/⚠️/❌/N/A | ... |
| ... | ... | ... |

### Economic
| ID | Score | Notes |
|----|-------|-------|
| E1 | ✅/⚠️/❌/N/A | ... |
| ... | ... | ... |

## Overall Score: [0-100]

## Summary
[2-3 sentences: what's good, what needs work, recommendation]

## Specific Issues
1. [Issue + which principle it violates + suggested fix]
2. ...

## Recommendation
- [ ] Ready to submit
- [ ] Needs minor revisions (list them)
- [ ] Needs major rework (explain why)
- [ ] Rejected (cite red line violation)
```

---

## 9. On-Chain Alignment Attestation (Future)

When the system matures:

1. Contributor's AI generates alignment report
2. Report hash is signed by contributor's Symbiotic Wallet
3. Hash stored on-chain as attestation
4. Reviewers can verify: the report exists, it was signed by the contributor, and the content matches the hash
5. Alignment score becomes part of the contributor's on-chain reputation

This creates an immutable record of good-faith alignment checks. Gaming it (fabricating a high score) is possible but detectable through peer review — and the on-chain signature means the contributor staked their identity on the report's accuracy.

---

## 10. Inherited Alignment: The Governance Genome

### 10.1 Every Entity Inherits This Protocol

When an Entity (organization / mini-DAO) is created on ResonantOS, the system generates their Alignment Protocol by:

1. **Copying** the base ResonantOS protocol (core principles + red lines + base tests)
2. **Locking** inherited sections (marked as `[INHERITED — READ ONLY]`)
3. **Adding** blank sections for organizational identity and domain-specific tests
4. **Prompting** the Entity's AI to help fill in domain customization during onboarding

The Entity has a complete, functional alignment document from minute one.

### 10.2 Inheritance Rules

| Component | Inherited? | Entity can modify? |
|-----------|-----------|-------------------|
| Core Principles (P1-P10) | ✅ Yes | ❌ No — constitutional floor |
| Red Lines (R1-R10) | ✅ Yes | ➕ Can ADD stricter, never remove |
| Technical Tests (T1-T7) | ✅ Yes | ➕ Can ADD domain-specific, cannot weaken |
| Philosophical Tests (A1-A7) | ✅ Yes | ➕ Can ADD org values, cannot contradict |
| Economic Tests (E1-E4) | ✅ Yes | ✅ Customize within ecosystem rules |
| Organizational Identity | ❌ Created fresh | ✅ Fully custom |
| Domain-Specific Tests | ❌ Created fresh | ✅ Fully custom |

**Key rule: alignment can only get STRICTER as it propagates downward, never weaker.**

### 10.3 Propagation Chain

```
ResonantOS Constitution (L0 — immutable core)
    │
    ├→ ResonantDAO Alignment Protocol (L1 — this document)
    │       │
    │       ├→ Entity A Protocol (inherited + domain customization)
    │       │       ├→ Entity A's Swarm Agents (inherit Entity A's protocol)
    │       │       └→ Entity A's Sub-DAOs (inherit + further customize)
    │       │
    │       ├→ Entity B Protocol (inherited + different domain)
    │       │
    │       └→ Individual Contributors (use base protocol directly)
    │
    └→ Constitutional Amendments (supermajority across all three chambers)
```

### 10.4 Cross-Entity Compatibility

Because every Entity's protocol shares the same constitutional root:

- **Inter-Entity bounties** — An agent from Entity A can work on Entity B's task (both share core principles; agent additionally satisfies B's domain tests)
- **Portable reputation** — Alignment scores use a common rubric, comparable across organizations
- **Ecosystem-wide quality floor** — No Entity can create a race-to-the-bottom by weakening alignment
- **Federated governance** — Entities vote in the Entity Chamber with alignment-verified contributions

---

## 11. Versioning & Governance

This document is **L1 (Architecture)** — it defines HOW alignment is evaluated.

Changes to this document require:

| Change type | Required |
|-------------|----------|
| Add/modify an alignment test | Community proposal + simple majority |
| Add/modify a red line | DAO governance proposal + supermajority (all three chambers) |
| Modify core principles | Constitutional amendment (supermajority + timelock) |
| Update architectural constraints | Technical proposal + relevant chamber vote |
| Fix typos / clarify language | PR with reviewer approval |

The principles themselves come from L0 documents (Philosophy, Constitution, Manifesto). This document REFERENCES them — it doesn't own them. Changing the philosophy requires changing L0, which requires the highest governance threshold.

---

## REFERENCES

- **Depends On:** `SSOT-L0-PHILOSOPHY.md`, `SSOT-L0-CONSTITUTION.md`, `SSOT-L0-OVERVIEW.md`
- **Referenced By:** `SSOT-L3-DAO-MEMBERSHIP-ARCHITECTURE.md`, Bounty submission system, PR review process
- **Source:** Manolo + Augmentor conversation 2026-02-27
