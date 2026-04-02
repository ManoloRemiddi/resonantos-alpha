# SSoT Template v0.6.0

Use this template for public Single Source of Truth documents that belong in the Alpha repository.

## Rules

- Keep content public, portable, and product-relevant.
- Do not include personal profiles, secrets, chat transcripts, machine-specific paths, or live operational residue.
- Prefer concise decisions over narrative process logs.

## Template

```markdown
# [Title]
<!-- One-line description -->

| Field | Value |
|-------|-------|
| **ID** | `SSOT-L[0-2]-[NAME]-V1` |
| **Created** | YYYY-MM-DD |
| **Updated** | YYYY-MM-DD |
| **Level** | L0 / L1 / L2 |
| **Type** | Truth / Working / Research |
| **Status** | Draft / Active / Deprecated / Archived |
| **Stale After** | [N days] or Never |

## Purpose

[Why this document exists and who it serves.]

## Scope

- Covers: [what is in scope]
- Excludes: [what is intentionally out of scope]

## Decisions

| Decision | Rationale | Date |
|----------|-----------|------|
| [decision] | [why] | YYYY-MM-DD |

## Specification

[Clear, buildable details.]

## Constraints

- [hard rule]
- [hard rule]

## Relationships

- Depends On: `[SSOT-ID]`
- Related To: `[SSOT-ID]`
- Supersedes: `[SSOT-ID]`

## Change Log

| Date | Change |
|------|--------|
| YYYY-MM-DD | Initial version |
```

## Suggested Layout

- `ssot/L0/` for public foundation documents.
- `ssot/L1/` for public architecture documents.
- `ssot/L2/` for public project-level documents when needed.
<!-- SSOT-LOG-YYYY-MM-DD | Agent: [name] -->

## HEADER
| Field | Value |
|-------|-------|
| Date | YYYY-MM-DD |
| Time | HH:MM - HH:MM |
| Agent | [agent-name] |
| Session | [session-id] |
| Tokens | ~NNNk |

---

## PART 1: PROCESS LOG (History Record)

### Human Input
[What did the operator ask/direct?]

### Agent Analysis
[How did I interpret and approach it?]

### The Struggle
[Decisions made, pivots taken, failures encountered]

### Artifacts Produced
[What was created/modified?]
- File: path/to/file.md
- Commit: abc123

### System Upgrades
[Any improvements to how we work?]

---

## PART 2: STABILITY CHECK

### Failure Events
[What went wrong?]

### Root Cause
- [ ] F1: Misunderstanding (wrong interpretation)
- [ ] F2: Capability gap (couldn't do it)
- [ ] F3: Process failure (forgot step, wrong order)

---

## PART 3: LEARNING (Fine-Tuning Data)

### DNA Sequence: [SHORT_NAME]

**Context:** [What triggered this learning?]

**Mechanism:** [Why did I fail/succeed internally?]
- "I prioritized X over Y"
- "I assumed Z without checking"
- "I correctly anticipated..."

**Violation/Success:** [What was the bad/good output?]

**Corrected Policy:** [What's the right approach?]

<!-- Repeat for each distinct learning -->

---

## COMPRESSION METADATA
<!-- For R-Memory processing -->
| Field | Value |
|-------|-------|
| Compress Priority | High / Medium / Low |
| Key Terms | [term1, term2, term3] |
| Related SSoT | [links] |
```

---

## Quick Reference

**Creating new SSoT:**
1. Determine level (L1-L4)
2. Choose category prefix
3. Copy appropriate template section
4. Fill header completely
5. Add to correct directory
6. Commit (L1-L2) or save locally (L3-L4)

**Updating SSoT:**
1. Check current status (Active? Deprecated?)
2. Update CHANGE LOG
3. Update "Updated" date
4. For Truth SSoT: ensure no contradictions introduced
5. Commit

**Retiring SSoT:**
1. Set Status = "Deprecated" or "Archived"
2. Add "Supersedes" link in replacement SSoT
3. Move to archive/ if L3-L4
4. Keep in place if L1-L2 (git history preserves)
