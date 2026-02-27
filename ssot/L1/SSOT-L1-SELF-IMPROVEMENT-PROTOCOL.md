# Self-Improvement Protocol — Architecture

| Field | Value |
|-------|-------|
| ID | SSOT-L1-SELF-IMPROVEMENT-PROTOCOL-V1 |
| Level | L1 (Architecture — Truth) |
| Created | 2026-02-27 |
| Status | Active |
| Stale After | Review quarterly |
| Related | SSOT-L1-ALIGNMENT-PROTOCOL.md, SSOT-L1-SYSTEM-OVERVIEW.md |

---

## The Problem

Lessons are learned constantly during work. Currently they are written to MEMORY.md and daily logs. This is hope-based enforcement: it relies on the AI reading and remembering lessons across sessions. The 42% Wall applies — LLMs override documented lessons unless enforcement is rigid and procedural.

Additionally, stopping work to process every lesson breaks flow and causes drift. Manolo cannot pause every productive session to formalise a lesson. But unprocessed lessons decay — they get compacted, forgotten, or repeated.

The system needs to capture lessons during work (zero friction), classify them automatically, and route them to the correct enforcement layer without human intervention.

**Design constraint (SOUL.md deterministic-first):** Every step that CAN be done by code/script MUST be done by code/script. AI is called only for steps that genuinely require reasoning. This makes the pipeline reliable (no hallucination), cheap (no token cost for mechanical steps), and resistant to the 42% Wall (deterministic steps cannot be overridden by training priors).

## The Solution: Continuous Self-Improvement Loop

### Core Principles

1. **Repetition is the signal, not occurrence.** A problem that happens once is tracked, not enforced. A problem that happens twice is a pattern. Patterns get rules. One-offs that never repeat cost nothing. This is the natural filter that eliminates noise.

2. **Minimise human involvement.** The human cannot micromanage improvement at this velocity. Three tiers:
   - **Technical/optimisation:** AI decides, implements, logs. No human involvement. (e.g., "send media from workspace, not Desktop")
   - **Behavioural pattern:** Daily digest. Silence = consent. Human can override. (e.g., "error explanation enforcer graduated to soft block")
   - **Major behavioural shift:** Explicit human approval required. (e.g., "new rule blocks all direct code writing")

3. **Daily cadence, not weekly.** Lessons are processed nightly. The human gets a 10-second morning digest. Not a weekly review session that becomes a maintenance burden.

4. **Audit existing rules.** Rules that never trigger are dead weight. Rules with high false positives are harmful. Periodic audit removes both.

### The Loop

```
Work happens
  |
  v
Mistake/insight detected → captured to queue (zero friction)
  |
  v
[Nightly] Archivist processes queue:
  |
  +-- First occurrence? --> Track. No action yet.
  |
  +-- Second occurrence (pattern detected)?
  |     |
  |     +-- Already enforced? --> Enforcement Failure. Debug rule. Patch.
  |     |
  |     +-- Enforceable + Personal? --> Auto-generate rule (advisory mode)
  |     |     +-- Technical? --> Deploy silently, log in digest
  |     |     +-- Behavioural? --> Log in digest, silence = consent
  |     |     +-- Major shift? --> Escalate to human for approval
  |     |
  |     +-- Enforceable + Organisational? --> Queue for smart contract design
  |     |
  |     +-- Unenforceable? --> Document, schedule for cold case review
  |
  v
[Daily] Morning digest to human (10 seconds to read)
  |
  v
[Weekly] Rule audit: dead rules, false positives, effectiveness
```

### Deterministic vs AI Map

Every step in the pipeline is classified. Deterministic steps are implemented as code (scripts, extensions, data queries). AI is invoked only where reasoning is genuinely required.

| Step | Engine | Why |
|---|---|---|
| Capture Source B: detect human corrections | **Deterministic** (regex) | Keyword patterns: "you should have", "why didn't you", "that's wrong", corrections. Catches 80%+. AI fallback for ambiguous cases only. |
| Capture Source C: detect tool errors + silent retries | **Deterministic** (log parsing) | Tool call logs have structured error fields. Pattern: error status → next tool call ≠ message(send) → captured. Pure grep. |
| Capture Source C: extract lesson text from transcript | **AI** | Messy conversation → structured lesson. Requires reasoning. |
| Repetition detection | **Deterministic** (embedding cosine distance) | Pre-computed embeddings, cosine similarity > 0.8 threshold. Math, not reasoning. |
| Occurrence counting | **Deterministic** (JSONL query) | `grep + wc` or structured data query. |
| Classification: scope | **AI** | Requires understanding whether a lesson is personal vs organisational. |
| Classification: enforceability | **Partially deterministic** | If lesson involves tool call patterns → deterministic (regex-matchable). Novel patterns → AI. |
| Rule candidate generation | **AI** | Designing the detection pattern requires reasoning about the failure mode. |
| Rule deployment | **Deterministic** (file write + config) | Write rule to Shield Gate config, restart if needed. Script. |
| Rule graduation | **Deterministic** (counter + threshold) | Track catches in JSONL, compare to threshold, promote. Pure arithmetic. |
| Daily digest | **Deterministic** (template + data) | Query JSONL for counts, fill template, send via message tool. Zero AI. |
| Rule audit | **Deterministic** (data query) | Count catches, false positives, last-triggered date. Arithmetic + thresholds. |
| Trend detection | **Deterministic** (group-by + count) | Group lessons by category, count per time window, flag if > threshold. |
| Cold case review | **AI** | Re-evaluate with current capabilities requires reasoning. |

**Result: 8/14 steps fully deterministic. 3/14 partially. 3/14 require AI.**

The self-improver agent runs the deterministic pipeline as a script. It calls AI only 3 times per nightly run (lesson extraction, scope classification, rule candidate design). Everything else is code that cannot fail, hallucinate, or be overridden by training priors.

## Architecture

### 1. Capture Layer (Three Sources)

Lessons are captured from three independent sources. No single source is trusted alone.

**Source A: AI self-detection (during work).** When the AI recognises a mistake or insight, append one line to the queue. No analysis. Back to work.

**Source B: Human feedback parsing.** Any correction, critique, or "you should have" from the human is a lesson signal. Mandatory capture. The AI does not get to decide whether Manolo's feedback is worth logging. It always is.

**Source C: Archivist retroactive extraction (nightly).** The Memory Archivist diffs the day's conversation for patterns that look like mistakes: tool errors followed by silent retries, human corrections, repeated attempts, topics revisited after failure. Auto-generates candidate lesson entries from raw transcript. This is the safety net: if Source A and B both miss a lesson, Source C catches it from the evidence.

**Why three sources:** Source A depends on AI self-awareness (weakest, subject to 42% Wall). Source B depends on human availability (Manolo cannot watch everything). Source C depends on pattern detection quality (may have false positives). Together they cover each other's blind spots.

**File:** `~/.openclaw/workspace/memory/lessons-queue.jsonl`

**Format:**
```json
{
  "ts": "2026-02-27T09:43:00Z",
  "source": "human-feedback",
  "lesson": "Error surfaced to user without explanation. Silently retried instead of explaining.",
  "context": "Tool returned error on message send (wrong directory). Fixed by copying file. User saw error but got no explanation.",
  "existingRule": "MEMORY.md lesson: always explain errors that surface to user",
  "severity": "standard",
  "category": null,
  "status": "pending"
}
```

**Severity levels:**
- `critical`: Data exposure, repo separation, destructive commands. Skip graduation, hard block immediately.
- `standard`: Operational errors, process failures. Advisory-first graduation.
- `low`: Stylistic, preference, optimisation. Advisory only, may never graduate.

### 2. Repetition Detection Layer

Before classification, the archivist checks: has this lesson (or a substantially similar one) been seen before?

**Similarity check:** Compare new lesson against all tracked lessons using semantic similarity (embedding distance) and keyword overlap. Threshold: >0.8 similarity = same lesson.

| Occurrence count | Action |
|---|---|
| **1st** | Track. Tag `status: tracked`. No classification, no rule generation. Zero cost. |
| **2nd** | Pattern detected. Proceed to classification. Tag `status: pattern-detected`. |
| **3rd+** | Escalate priority. If no rule exists yet, this is an enforcement gap. |

**Exception:** Critical severity lessons (data exposure, repo separation) skip the repetition threshold. One occurrence = immediate classification and enforcement. These are too dangerous to wait for a second occurrence.

**Why this matters:** Most one-off mistakes are contextual and never repeat. The repetition threshold eliminates 60-80% of noise without losing any signal. Only patterns that actually recur consume classification resources and generate rules.

### 3. Classification Layer (Async, Validated)

Runs during nightly archivist. Processes only lessons with `status: pattern-detected` or `severity: critical`.

**Classification matrix:**

| Question | If YES | If NO |
|----------|--------|-------|
| Is there an existing rule that should have caught this? | **Enforcement Failure** — debug and patch the rule | Continue to scope classification |
| Does this affect only this Augmentor and its human? | **Personal** — Shield Gate or Logician | Continue |
| Does this affect any agent interacting with any human or organisation? | **Organisational** — smart contract candidate | Continue |
| Does this affect the entire ecosystem's standards? | **Ecosystem** — Alignment Protocol amendment | Continue |
| Can this be detected by pattern matching (regex, file path, command structure)? | **Enforceable** — generate rule candidate | **Unenforceable** — document only |

**Output:** Each lesson gets tagged with:
- `scope`: personal | organisational | ecosystem
- `enforceable`: true | false
- `layer`: shield-gate | logician | smart-contract | alignment-protocol | documentation
- `escalation`: none | digest | human-approval
- `existingRuleId`: null or reference to rule that failed
- `candidateRule`: auto-generated rule specification (if enforceable)
- `status`: pattern-detected | classified | implemented | verified

**Human involvement classification (determines escalation):**

| Rule type | Escalation | Human action needed |
|---|---|---|
| Technical/optimisation (file paths, tool usage, retry logic) | `none` — AI deploys, logs in digest | None unless human objects |
| Behavioural pattern (communication, delegation, workflow) | `digest` — reported in daily digest | Silence = consent. Override if wrong. |
| Major behavioural shift (new blocking rules, scope changes) | `human-approval` — explicit approval | Must approve before deployment |

**Classification validation:** Dual-pass disagreement detection. If two classification passes disagree on scope or enforceability, flag for human review in the digest rather than auto-routing. Consensus = auto-route. Disagreement = human decides.

### 3. Enforcement Failure Tracking

When a lesson matches an existing rule that should have caught it:

**File:** `~/.openclaw/workspace/memory/enforcement-failures.jsonl`

```json
{
  "ts": "2026-02-27T09:43:00Z",
  "lesson": "Error not explained to user",
  "existingRule": "MEMORY.md: always explain errors that surface to user",
  "ruleLayer": "documentation",
  "failureReason": "Rule exists only in MEMORY.md (hope-based). No Shield Gate layer enforces it.",
  "fix": "Promote to Shield Gate: track tool errors, require message before next tool call",
  "status": "pending"
}
```

This is the critical feedback loop. Enforcement failures are higher priority than new lessons because they represent known problems with broken fixes.

### 4. Rule Generation Layer

For enforceable lessons, auto-generate a candidate rule specification.

**Personal scope candidates (Shield Gate):**

```json
{
  "layer": "shield-gate",
  "name": "error-explanation-enforcer",
  "trigger": "after_tool_call returns error status",
  "condition": "next tool call is not message(action=send)",
  "action": "inject warning: 'A tool error was visible to the user. Explain before continuing.'",
  "mode": "advisory",
  "graduation": "After 5 successful advisory catches with zero false positives, promote to blocking"
}
```

**Organisational scope candidates (Smart Contract):**

```json
{
  "layer": "smart-contract",
  "name": "budget-enforcement",
  "trigger": "agent transaction exceeds allocated budget",
  "condition": "transaction amount > budget_cap PDA value",
  "action": "transaction rejected by Solana VM",
  "mode": "blocking (from day one — on-chain is always blocking)",
  "spec": "Queue for Anchor programme design"
}
```

### 6. Trend Detection Layer

Individual lessons miss systemic drift. The nightly archivist analyses the lesson queue for recurring patterns:

- **Category clustering:** If 3+ lessons in a 7-day window share the same category or root cause, flag as a behavioural trend. Example: "3 delegation failures this week" is not 3 separate lessons. It is one trend that needs a systemic fix.
- **Drift detection:** Compare lesson categories over 30-day windows. If a category that was resolved starts reappearing, the enforcement degraded.

Note: The repetition detection layer (Section 2) already handles individual lesson recurrence. Trend detection operates at the category level — catching systemic patterns that individual repetition checks miss.

Output: `memory/trend-reports.jsonl` (one entry per detected trend, linked to constituent lessons).

### 7. Retroactive Mining (One-Time + Periodic)

**One-time pass:** Read all historical memory files (`memory/2025-*.md`, `memory/2026-*.md`). Extract anything that reads like a lesson, mistake, correction, or "should have". Run through the classification pipeline. This mines 9 months of documented-but-never-enforced lessons.

**Monthly cold case review:** Re-scan lessons previously classified as "unenforceable". Reassess with current tooling. A pattern that was undetectable 3 months ago may now be catchable due to new Shield Gate capabilities or new Logician rules.

### 8. Graduation Path

Rules start advisory (warn, do not block) and graduate to blocking after proving reliability. **Severity determines starting point.**

| Severity | Starting stage | Graduation |
|----------|---------------|------------|
| **Critical** (data exposure, repo separation, destructive) | Hard block immediately | Already at maximum |
| **Standard** (operational errors, process failures) | Advisory | Advisory -> Soft block -> Hard block |
| **Low** (stylistic, preference) | Advisory | May stay advisory permanently |

**Standard graduation criteria:**

| Stage | Behaviour | Criteria to advance |
|-------|-----------|-------------------|
| **Advisory** | Log warning, allow action | 5+ catches, 0 false positives |
| **Soft block** | Warn and require explicit override | 10+ catches, 0 false positives in advisory |
| **Hard block** | Block action, no override | Human approval after soft block proves stable |

Smart contracts skip graduation entirely. On-chain enforcement is blocking from deployment. The graduation path applies only to personal-scope rules (Shield Gate, Logician) where false positives would block legitimate work.

### 9. Scope Boundaries

| Scope | Enforcement layer | Who maintains | Examples |
|-------|------------------|--------------|----------|
| **Personal** | Shield Gate, Logician, Coherence Gate | This Augmentor | Explain errors, verify before claiming fixed, delegate coding |
| **Organisational** | Smart contracts (Solana programmes) | Entity governance | Budget caps, task escrow, revenue splits, multi-sig requirements |
| **Ecosystem** | Alignment Protocol (on-chain attestation) | DAO governance | Core principles, red lines, contribution quality floor |

**The boundary rule:** If a lesson applies ONLY to the relationship between this specific Augmentor and this specific human, it is personal. If it would apply to ANY Augmentor-human pair or ANY agent in the ecosystem, it is organisational or ecosystem scope.

Personal rules are local. They never touch the blockchain. They live in Shield Gate extensions and Logician rule files on this machine.

Organisational rules are on-chain. They enforce behaviour across all participants. They require smart contract design, audit, and deployment.

Ecosystem rules are constitutional. They require governance proposals and multi-chamber approval.

### 10. Dedicated Self-Improvement Agent

The orchestrator should not process lessons. A dedicated lightweight agent handles it.

**Agent:** `self-improver` (cron-based, cheap model — gpt-4o-mini or equivalent)

| Schedule | Task |
|---|---|
| **Nightly** (22:55, after Memory Archivist) | Process lesson queue: repetition detection, classification, rule candidate generation, daily digest preparation |
| **Weekly** (Sunday night) | Rule audit: effectiveness metrics, dead rule detection, false positive review |
| **Monthly** (1st of month) | Cold case review: re-evaluate unenforceable lessons with current tooling |

**Why a dedicated agent:**
- Keeps the orchestrator free for Manolo (core lesson from 2026-02-21)
- Cheap model is sufficient for pattern matching and classification
- Isolated session means lesson processing does not pollute main context
- Can be audited independently (its own conversation logs show reasoning)

**Daily digest format (delivered to Telegram, morning):**

```
🔄 Self-Improvement Digest — Feb 28

Captured: 5 lessons (3 AI, 1 human, 1 archivist)
New patterns: 1 (media path error — 2nd occurrence → rule candidate generated)
Rules deployed: 1 technical (advisory, auto-deployed)
Escalations: 0
Active rules: 12 (11 healthy, 1 under review)
```

Manolo reads in 10 seconds. Silence = consent. If something looks wrong, he says so.

### 11. Rule Audit

Rules are not permanent. They degrade, become irrelevant, or cause false positives. Periodic audit keeps the rule set healthy.

**Weekly audit (automated):**

| Check | Action if triggered |
|---|---|
| Rule has 0 catches in 30 days | Flag as potentially dead. If 0 in 60 days, recommend removal. |
| Rule has >20% false positive rate | Demote from blocking to advisory. Investigate trigger pattern. |
| Rule was overridden by human >3 times | The rule is wrong. Revise or remove. |
| Two rules cover the same pattern | Merge or remove the weaker one. |

**Monthly audit (with cold case review):**
- Review all "unenforceable" lessons: can current tooling now catch them?
- Review organisational-scope lessons: have any been implemented as smart contracts?
- Check if the lesson capture rate is declining (sign that Source A is degrading)

**Audit output:** Appended to weekly digest. Human sees: "2 dead rules flagged, 1 rule revised, 0 removals."

## Implementation Plan

### Phase 1: Bootstrap (This Week)

1. ~~Create `memory/lessons-queue.jsonl`~~ DONE
2. ~~Create `memory/enforcement-failures.jsonl`~~ DONE
3. AI captures lessons during work from day one (Source A + B). No waiting.
4. Nightly: manual end-of-day review of conversation to catch missed lessons (Source C, human-in-the-loop until automated)
5. Daily digest delivered to Telegram each morning (manual format until agent exists)

### Phase 2: Retroactive Mining (One-Time, This Week)

1. Sub-agent reads all `memory/2025-*.md` and `memory/2026-*.md` files
2. Extracts lessons, mistakes, corrections, "should have" patterns
3. Outputs to `lessons-queue.jsonl` with `source: "retroactive"`
4. Run repetition detection across the retroactive set. Patterns that already appeared multiple times in history = immediate rule candidates.
5. This seeds the system with months of data and surfaces the highest-value lessons first.

### Phase 3: Self-Improver Agent (Week 2)

1. Create `self-improver` cron agent (nightly, cheap model)
2. Implements: Source C extraction, repetition detection, classification, rule candidate generation
3. Generates daily digest (auto-delivered to Telegram)
4. Human involvement: read digest, override if needed, silence = consent

### Phase 4: Rule Generation + Graduation (Week 2-3)

1. Build first Shield Gate rule from highest-repetition pattern
2. Implement advisory mode with graduation tracking (severity-based)
3. Technical rules: auto-deploy, log in digest
4. Behavioural rules: report in digest, wait for consent window (24h silence = approved)
5. Major shifts: explicit approval required

### Phase 5: Audit + Organisational Queue (Week 3-4)

1. Weekly rule audit (automated by self-improver agent)
2. Create `ssot/L3/smart-contract-candidates.md` for organisational-scope lessons
3. Monthly cold case review of unenforceable lessons
4. First effectiveness report after 30 days of operation

### Metrics (Ongoing)

Track:
- Lessons captured per day (by source: self/human/archivist)
- One-offs vs patterns (repetition threshold filter rate)
- Rules generated, deployed, graduated
- False positive rate per rule
- Dead rules flagged and removed
- Human overrides (signal that a rule was wrong)
- Time from second occurrence to rule deployment (target: <48h for personal technical)
- Capture completeness (lessons found by archivist that self-detection missed)

## Anti-Patterns

| Anti-Pattern | Why |
|-------------|-----|
| Stop work to process every lesson immediately | Breaks flow, causes drift. Capture is instant; classification is async. |
| Create a rule from the first occurrence | One-offs are noise. Wait for repetition. Only critical severity skips this. |
| Create blocking rules without advisory period | False positives block legitimate work. Graduate first (except critical). |
| Put personal rules on-chain | Wastes compute and governance bandwidth. Local rules stay local. |
| Require human approval for technical fixes | The human cannot micromanage. Technical rules auto-deploy, log in digest. |
| Weekly review sessions | Too slow, too much work. Daily digest, 10 seconds, silence = consent. |
| Skip enforcement failure tracking | Broken rules that look like they work are worse than no rules. |
| Keep rules forever without auditing | Dead rules accumulate. Weekly audit catches them. |
| Classify everything as "unenforceable" | Lazy. Most behavioural patterns have a detectable trigger. Challenge the classification. |
| Process lessons in the main session | Use the dedicated self-improver agent. Keep the orchestrator free. |

## Relationship to Existing Architecture

### Four-Layer Enforcement Stack
This protocol adds a feedback loop TO the stack. The stack is static (rules coded at build time). This protocol makes it dynamic (rules generated from operational experience).

### Alignment Protocol
The Alignment Protocol enforces contributor alignment to ecosystem principles. This protocol enforces the Augmentor's alignment to its own operational lessons. Same pattern, different scope. An Augmentor that runs this protocol produces better alignment reports because it has fewer unforced errors.

### Memory Archivist
The nightly archivist already processes daily logs and updates MEMORY.md. Phase 1 adds lesson classification to that existing process. No new cron job needed.

## Files

- This document: `ssot/L1/SSOT-L1-SELF-IMPROVEMENT-PROTOCOL.md`
- Lesson queue: `memory/lessons-queue.jsonl` (created on first capture)
- Enforcement failures: `memory/enforcement-failures.jsonl` (created on first failure)
- Shield Gate: `~/.openclaw/extensions/shield-gate/index.js`
- Smart contract candidates: `ssot/L3/smart-contract-candidates.md` (Phase 3)

## Self-Debate Findings (2026-02-27)

Ran adversarial self-debate (7 rounds) before implementation. Six blind spots identified and patched:

1. **Single-source capture dependency.** Original design relied solely on AI self-detection. Added three-source model (AI + human feedback + archivist retroactive).
2. **Classification as single point of failure.** No validation on classifier output. Added dual-pass disagreement detection and weekly human review.
3. **No trend detection.** Individual lessons missed systemic drift. Added trend detection layer (7-day and 30-day windows).
4. **No retroactive mining.** 9 months of memory logs unprocessed. Added one-time mining pass and monthly cold case review.
5. **Uniform graduation speed.** Critical rules (data exposure) should not wait for 5+ catches in advisory. Added severity-based graduation: critical = hard block immediately.
6. **No safety net for capture failures.** If AI forgets to log, lesson is lost. Archivist now serves as safety net, detecting lessons from raw conversation evidence.

**Remaining unresolved:** Archivist lesson extraction quality from messy transcripts. False lesson detection rate. Actual lessons-per-day rate (Phase 0 measures this before building automation).

## Change Log

| Date | Change |
|------|--------|
| 2026-02-27 | V1 created. Capture + classify + generate + graduate architecture. Four-scope model (personal/org/ecosystem/unenforceable). Enforcement failure tracking. Advisory-first graduation. |
| 2026-02-27 | V1.1 (post-debate). Six blind spots patched: three-source capture, classification validation, trend detection, retroactive mining, severity-based graduation, archivist safety net. Phase 0 (data collection) added before automation. |
| 2026-02-27 | V1.2 (Manolo feedback). Three design changes: (1) Repetition threshold — one-offs tracked, not enforced; patterns (2+ occurrences) get rules. (2) Minimise human involvement — three-tier escalation (technical=silent, behavioural=digest, major=approval), daily digest not weekly review, silence=consent. (3) Dedicated self-improver agent + periodic rule audit. Removed Phase 0 wait; start capturing immediately. |
| 2026-02-27 | V1.3 (deterministic-first). Mapped all 14 pipeline steps: 8 fully deterministic, 3 partial, 3 AI-only. Pipeline implemented as script with AI called only 3 times per nightly run. Deterministic steps: repetition detection, counting, graduation, digest, audit, trend detection, rule deployment. AI steps: lesson extraction from transcripts, scope classification, rule candidate design. |
