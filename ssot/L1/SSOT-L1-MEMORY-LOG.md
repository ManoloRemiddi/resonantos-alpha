# SSOT-L1-MEMORY-LOG — Memory Log Format Guidelines
Updated: {{GENERATED_DATE}}

## Purpose
Memory logs capture high-quality session summaries in a structured 3-part format: Process Log + Trilemma + DNA. These logs serve as:
- Session continuity across context resets
- Training data for fine-tuning
- Audit trail for decisions
- Failure analysis database

## Format: 3-Part DNA

### Part 1: Process Log
Strategic view of the session — what happened, why it matters, what was learned.

**Structure:**
```markdown
## PART 1: PROCESS LOG

### Context
What was the starting state?

### Work Done
What actions were taken?

### Decisions Made
What choices were made and why?

### Results
What was the outcome?

### Key Insights
What was learned?
```

**Quality bar:** Focus on WHY, not just WHAT. Capture reasoning, not just actions.

---

### Part 2: Trilemma Diagnosis
For failures or problems, classify the root cause:

- **F1 (Wrong Approach):** The method/strategy was incorrect
- **F2 (Missing Data):** Lacked necessary information
- **F3 (Bad Prompt):** Instructions were unclear or wrong

**Structure:**
```markdown
## PART 2: TRILEMMA DIAGNOSIS

**Failure event:** [description]

- **F1 (rule gap):** [if applicable]
- **F2 (protocol violation):** [if applicable]
- **F3 (bad prompt):** [if applicable]

**Root cause:** [single sentence]

**Partial mitigation:** [what was done]
```

**Skip this section if:** No failures occurred in the session.

---

### Part 3: DNA Sequencing
Extract reusable patterns from the session.

**Structure:**
```markdown
## PART 3: DNA SEQUENCING

### [DNA: PATTERN_NAME]
**Context:** [when this pattern appeared]
**Mechanism:** [how it works]
**Prompt violation:** [what assumption was wrong]
**Corrected policy:** [what to do instead]
```

**Quality bar:**
- Each DNA entry must be actionable
- Focus on novel learnings, not obvious facts
- Include enough context to apply the pattern later

---

## File Naming Convention
`MEMORY-LOG-YYYY-MM-DD[-suffix].md`

Examples:
- `MEMORY-LOG-2026-03-27.md` (single log for the day)
- `MEMORY-LOG-2026-03-27-MORNING.md` (multiple logs)
- `MEMORY-LOG-2026-03-27-ALPHA-WORK.md` (topic-specific)

## Storage Location
`{{WORKSPACE_PATH}}/memory/shared-log/`

## Generation Triggers

### Manual
Write a memory log when:
- Natural pause in work (topic change, user steps away)
- Major decision made
- Failure occurred and was resolved
- End of session

### Automatic
Cron jobs generate memory logs:
- **intraday-memory-log:** Every 3 hours (live session data)
- **daily-memory-log-dna:** 04:30 daily (safety net from session history)

## Breadcrumbs (Real-Time Capture)
During work, append to `{{WORKSPACE_PATH}}/memory/breadcrumbs.jsonl`:

```json
{"ts":"ISO","event":"what happened","broke":"what went wrong (if anything)","fcode":"F1|F2|F3|null","dna_tag":"SHORT_TAG"}
```

Breadcrumbs feed into memory log generation.

---

## Quality Examples

### Good Memory Log
- Captures WHY decisions were made
- Includes failure analysis with root cause
- Extracts reusable patterns (DNA)
- Enough context to understand 6 months later

### Bad Memory Log
- Just lists actions taken ("did X, then Y, then Z")
- No reasoning or insights
- Generic patterns that don't help future work
- Missing context

---

_This document defines the memory log format. Update as the format evolves._
