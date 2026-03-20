# SSoT Quality Standard — What Valid SSoTs Look Like

| Field | Value |
|-------|-------|
| ID | SSOT-L1-SSOT-QUALITY-STANDARD-V1 |
| Level | L1 (Architecture — Truth) |
| Created | 2026-02-27 |
| Status | Active |
| Stale After | Review quarterly |
| Related | SSOT-L1-SYSTEM-OVERVIEW.md, SSOT-L1-AUTONOMOUS-DEVELOPMENT-PROTOCOL.md |

---

## The Problem

SSoT documents are the backbone of the system — they provide structured context to agents, guide decisions, and serve as the single source of truth. But there is no specification for what a *valid* SSoT looks like. Documents are created ad-hoc, with inconsistent structure, varying quality, and no machine-readable validation.

This means:
1. **The orchestrator is a bottleneck.** Only the orchestrator knows what "good" looks like, so only the orchestrator can write SSoTs.
2. **Onboarding agents can't produce SSoTs.** Without a quality standard, an onboarding agent has no target to aim at.
3. **Quality degrades over time.** Without validation, documents drift from the standard.

## The Solution: A Machine-Readable Quality Standard

Every SSoT document must be both human-readable (for Manolo) and agent-readable (for any AI that receives it). This standard defines the minimum structural requirements for each SSoT level.

## Universal Requirements (All SSoT Levels)

Every SSoT document MUST have:

### 1. Metadata Header (mandatory)

```markdown
| Field | Value |
|-------|-------|
| ID | SSOT-L{level}-{NAME}-V{version} |
| Level | L{0-4} ({level name} — {type}) |
| Created | YYYY-MM-DD |
| Status | Active / Draft / Deprecated |
| Stale After | {review cadence} |
| Related | {comma-separated list of related doc IDs} |
```

**Validation rules:**
- ID must match pattern: `SSOT-L[0-4]-[A-Z0-9-]+-V\d+`
- Level must be L0-L4
- Created must be valid ISO date
- Status must be one of: Active, Draft, Deprecated
- Stale After must be present (even if "N/A")
- Related can be empty but field must exist

### 2. Problem Statement (mandatory)

A section titled "The Problem" or "Problem" or "Why This Exists" that:
- States what gap or failure this document addresses
- Minimum 50 characters
- Must not be vague ("things could be better") — must be specific ("X fails because Y")

### 3. Solution Section (mandatory)

A section titled "The Solution" or "Architecture" or "Design" that:
- Describes the approach taken
- Minimum 100 characters
- Must reference concrete mechanisms, not aspirations

### 4. No Orphan References

Any document referenced in the "Related" field must exist. Any document referenced inline (e.g., "see SSOT-L1-SHIELD") must exist. Broken references are validation failures.

## Level-Specific Requirements

### L0 (Foundation — Philosophy, Vision, Business)

Additional requirements:
- **Audience section:** Who reads this and why
- **Principles section:** ≥3 enumerated principles with rationale
- **Review cadence:** Must be "Rare" or specific interval ≥6 months
- **Tone:** Declarative. States what IS, not what might be.

### L1 (Architecture — Truth)

Additional requirements:
- **Component table or architecture diagram:** Visual or tabular representation of system structure
- **Integration section:** How this component connects to others
- **Enforcement section (if behavioural):** How compliance is verified (deterministic preferred)
- **Change Log:** Table with date + change description
- **Anti-patterns section (recommended):** Common mistakes and why they fail

### L2 (Project — Active Work)

Additional requirements:
- **Status field:** Must be one of: Design, Building, Production, Paused, Deprecated
- **Current state section:** What exists now (not what's planned)
- **What's Next section:** Explicit next steps (≥1 item)
- **Performance metrics (if production):** Quantitative data on how it's performing
- **Version history table:** Date + version + key changes

### L3 (Draft — Work in Progress)

Relaxed requirements:
- Metadata header still mandatory but Status must be "Draft"
- Problem statement still mandatory
- Solution section can be partial or speculative (labelled as such)
- No enforcement or change log required
- **Promotion criteria:** Explicit statement of what must be true before promoting to L1 or L2

### L4 (Notes — Ephemeral)

Minimal requirements:
- Date in filename or header
- At least one structural element (heading, list, or table)
- No metadata header required (but recommended)
- No validation beyond existence

## Compressed Variants (.ai.md)

For every L0 and L1 document, a compressed `.ai.md` variant SHOULD exist:
- Filename: same as original but with `.ai.md` extension
- Must preserve ALL technical details, numbers, parameters, decisions
- Must remove filler, redundancy, conversational tone
- Target: 50-80% smaller than original
- Header: `[AI-OPTIMIZED] ~{tokens} tokens | src: {original filename}`

## Structural Patterns

### Good SSoT Pattern

```markdown
# {Title} — {Subtitle}

| Field | Value |
|-------|-------|
| ID | ... |
| ... | ... |

---

## The Problem
[Specific gap with evidence]

## The Solution: {Approach Name}
[Concrete mechanism description]

## Architecture / Design
[Tables, diagrams, component descriptions]

## Implementation
[What exists, how it works]

## What's Next
[Concrete next steps]

## Anti-Patterns
[What NOT to do and why]

## Change Log
| Date | Change |
|------|--------|
| ... | ... |
```

### Bad SSoT Patterns (Anti-Patterns)

| Pattern | Why It Fails |
|---------|-------------|
| No metadata header | Can't be indexed, versioned, or audited |
| "This document describes..." opening | Wastes tokens. State the problem directly. |
| Aspirational language ("we aim to", "in the future") | Agents can't execute against aspirations |
| Missing Related field | Creates orphan documents with no navigation |
| L3 content in L1 path | Speculative content in a "Truth" level misleads agents |
| Giant monolith (>5000 words at L1) | Compress to .ai.md or split into sub-documents |
| Tables with empty cells | Either fill them or remove the row |
| "See above" / "As mentioned" | Agent context may not include "above". Use explicit references. |

## Validation Rules Summary

| Rule | Level | Check Type |
|------|-------|-----------|
| Metadata header present | All | Regex (table pattern) |
| ID matches pattern | All | Regex |
| Status is valid enum | All | String match |
| Problem section exists (≥50 chars) | All | Regex + length |
| Solution section exists (≥100 chars) | All | Regex + length |
| No broken Related references | All | File existence check |
| Audience section | L0 | Regex |
| Principles section (≥3 items) | L0 | Regex + count |
| Component table or diagram | L1 | Regex (pipe table or code block) |
| Integration section | L1 | Regex |
| Change Log | L1 | Regex |
| Status field in metadata | L2 | Regex |
| Current state section | L2 | Regex |
| What's Next section | L2 | Regex |
| Promotion criteria | L3 | Regex |
| Date in filename/header | L4 | Regex |

**Deterministic audit:** 16/16 validation rules are fully deterministic (regex + file I/O). Zero AI required for structural validation.

## Implementation

### Phase 1: Validator Script (ssot-validator.js)
- Same pattern as delegation-gate.js: pure file I/O + regex
- Input: file path → Output: { valid, errors, warnings, level, score }
- Score: 0-100 based on how many rules pass
- Fail-closed: if level can't be detected, validate at L1 (strictest common level)

### Phase 2: Integration
- Shield Gate extension: validate before committing SSoT files
- Onboarding agent: run validator on every generated document
- Nightly audit: cron job validates all SSoT files, reports drift

### Phase 3: Compressed Variant Check
- For L0/L1: warn if no .ai.md exists
- For .ai.md: validate it preserves all technical details from original (AI-assisted check)

## Relationship to Other Documents

| Document | Relationship |
|----------|-------------|
| DELEGATION_PROTOCOL.md | TASK.md is the spec for code tasks; this is the spec for knowledge documents |
| SSOT-L1-AUTONOMOUS-DEVELOPMENT-PROTOCOL.md | The toolkit produces SSoTs; this standard validates them |
| SSOT-L2-ONBOARDING-AGENT.md | The onboarding agent uses this standard as its target quality bar |

## Change Log

| Date | Change |
|------|--------|
| 2026-02-27 | V1 created. Universal + level-specific requirements. 16 deterministic validation rules. Anti-patterns. Compressed variant spec. |
