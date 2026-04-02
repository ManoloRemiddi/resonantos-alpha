# ResonantOS Installer v3 — Build Runbook

Status: Active
Purpose: Execution guide for continuing the v3 build safely and consistently

---

## 1) How to Use This Runbook

On each build session or heartbeat:

1. Read:
   - `FULL-BUILD-SPEC.md`
   - `V3-MASTER-SPEC.md`
   - `INSTALLER-FLOW-SPEC.md`
   - `BUILD-STATUS.md`
2. Work the **highest-priority unblocked task**.
3. Make **one coherent change set** at a time.
4. Validate the change.
5. Update `BUILD-STATUS.md`.
6. In any progress update, cite the exact runbook phase/task id.

Progress update format:
- `Runbook: UX-1`
- `Status: complete | in_progress | blocked`
- `Next: <task-id>`

---

## 2) Guardrails

- Do not skip ahead to flashy later work while earlier structural UX tasks are still open.
- Do not perform install/mutation actions unless the scope explicitly moves beyond read-only.
- Preserve existing passing tests unless intentionally replacing them.
- Prefer small, reviewable commits/patches.
- If a task reveals a larger redesign need, record it in `BUILD-STATUS.md` instead of silently expanding scope.

---

## 3) Phase Map

## Phase FDN — Foundation (completed checkpoint)

These are already substantially complete:
- FDN-1 detector contract
- FDN-2 option model
- FDN-3 deterministic handoff
- FDN-4 error hardening
- FDN-5 process-first clarification
- FDN-6 missing-tool diagnostics
- FDN-7 command/quoting hardening
- FDN-8 safe cleanup pass
- FDN-9 installer options + confirmed selection
- FDN-10 tests
- FDN-11 interactive selection flow
- FDN-12 manual/new path completion
- FDN-13 flow spec drafting

Do not re-open foundation work unless needed by a later phase.

---

## Phase UX — Paged Wizard UX Pass

### UX-1 — Clear-screen page shell
Implement page clear helpers and major page boundaries.

Acceptance:
- installer clears screen on launch
- installer clears between major pages
- current output stops feeling like one long dump

### UX-2 — Detection intro / waiting page
Create the reading-material splash page that runs while detection is in progress.

Acceptance:
- scan starts immediately
- page explains what is being scanned
- page says scan may take 1–5 minutes
- page ends with scan-complete acknowledgement and continue prompt

### UX-3 — Suppress noisy probe output
Hide or suppress low-level probe noise from the user-facing flow.

Acceptance:
- probe progress bars/noise no longer pollute the UX
- detection page remains visually owned by the installer

### UX-4 — Branch ordering fix
Reorder the flow so zero-detection question comes before generic dependency issues.

Acceptance:
- no-instance question is shown before dependency issue handling
- branch logic matches product decisions

### UX-5 — Dependency issues page gating
Show dependency issues only when relevant, and only in the correct branch.

Acceptance:
- if all dependency checks pass, no dependency page appears
- new-user branch skips generic dependency page initially

### UX-5A — Non-Docker dependency remediation actions
Add one-click install/update actions for non-Docker dependencies.

Acceptance:
- dependency issues page can offer direct remediation for non-Docker dependencies
- remediation is tailored to OS/runtime
- Docker is not remediated here
- user explicitly chooses to run the remediation action

### UX-6 — Detected instance card renderer
Replace crude summaries with readable boxed/horizontal instance cards.

Acceptance:
- resolved labels are prominent
- details are grouped cleanly
- low-confidence matches are visually distinct

### UX-7 — Simple install intent menu
Replace technical menu output with simple intent labels.

Acceptance:
- menu items read like user intent
- install-over entries use resolved labels

### UX-8 — Arrow-key selector
Replace main typed-choice menu with highlight/selector navigation.

Acceptance:
- up/down navigation works
- highlighted selection is clear
- Enter confirms

---

## Phase REC — Existing-User Recovery Flow

### REC-1 — Zero-detection existing-user recovery entry
After zero detections + user says they are not new, route into recovery-first flow.

Acceptance:
- flow emphasis is on recovering an existing install
- not on sending them into new-user onboarding
- user can pivot directly into a new install from this recovery area without being sent back to earlier branching screens

### REC-2 — Directed `openclaw.json` prompt
Prompt for `openclaw.json` location in recovery flow.

Acceptance:
- clear prompt
- validation for path shape/presence

### REC-3 — Targeted single-location detection
Run fast detection against the supplied location and build instance card from it.

Acceptance:
- uses directed input rather than wide scan
- produces readable recovered instance card

### REC-4 — Wrong-machine / remote-topology escape page
Show guidance when the user is probably on the wrong machine or in a more complex topology.

Acceptance:
- explains that installer should run on same machine as target instance
- includes tutorial link placeholder
- offers a graceful exit path

---

## Phase NEW — New-User Onboarding Wizard

### NEW-1 — Recommended vs Custom page
Make this the first onboarding decision after “Yes, I’m new”.

Acceptance:
- exactly two clear choices
- wording is friendly and understandable

### NEW-2 — Wizard state model
Implement stateful page progression for onboarding.

Acceptance:
- answers persist
- state survives page transitions cleanly

### NEW-3 — Help / Back / Next navigation
Add support for guided navigation.

Acceptance:
- every onboarding step offers help
- back/next work predictably

### NEW-4 — Dependent-state invalidation
Changing earlier answers should invalidate only dependent later branches.

Acceptance:
- Docker-specific later steps disappear if Docker is turned off later
- unrelated state remains intact

### NEW-5 — Docker later in the flow
Place Docker after install-style selection, not before.

Acceptance:
- ordering matches product decision
- wording treats Docker as optional and explained

### NEW-5A — Docker install/update check
When the user chooses Docker, check whether Docker is present and either install it, update it, or confirm readiness.

Acceptance:
- Docker-specific remediation happens inside Docker flow
- Docker is not treated as a generic dependency page fix
- user sees what action will be taken

### NEW-5B — Interactive Docker setup page
Build the Docker setup/configuration page with state/intent summary, progress, and final confirmation.

Acceptance:
- page is interactive
- Docker commands/actions run from this page
- user can review intended Docker setup before submit
- a single explicit confirmation happens before submission

### NEW-6 — Paths / ports onboarding page
Collect defaults and allow edits in context.

Acceptance:
- defaults are obvious
- editable fields are clear

### NEW-7 — OpenClaw / setup-agent readiness page
Define the onboarding stage that ensures the user reaches the dashboard with a ready setup agent.

Acceptance:
- installer-side responsibilities are clear
- handoff to dashboard onboarding is defined
- the page links into the minimum required OpenClaw onboarding elements: model setup, OAuth/token setup, and gateway setup

### NEW-7A — Agent mode choice
Offer `Auto mode` vs `Manual mode` for setup-agent readiness.

Acceptance:
- user can choose between auto and manual setup-agent sourcing
- the two modes are clearly explained

### NEW-7B — Auto mode provisioning
Specify and implement the path where the installer downloads a small local model for setup-agent use.

Acceptance:
- auto mode is the fast path
- installer provisions the small local model for first-run setup-agent use

### NEW-7C — Manual mode provider/model onboarding
Specify and implement manual setup via API key, OAuth, or curated local model menu.

Acceptance:
- manual mode supports multiple backend choices
- model/backend choice is prepared before installation completes

---

## Phase REV — Review, Execution Prep, and Landing

### REV-1 — Review page
Summarize final chosen install mode, paths, ports, Docker, and readiness.

### REV-2 — Install-phase prep contract
Ensure the wizard exits with a complete confirmed install-ready payload for later mutation steps.

### REV-3 — Dashboard landing contract
Define the expected end state: the install finishes by opening the user's default browser to the ResonantOS Dashboard with the setup agent already on screen saying welcome.

---

## Phase CLN — Final Cleanup Pass

### CLN-1 — Remove residual rough edges
Trim any temporary scaffolding left over from earlier transitions.

### CLN-2 — Align docs and tests
Ensure docs reflect final behavior and tests cover the new UX-critical logic.

### CLN-3 — Final polish pass
Naming, comments, consistency, and minor usability cleanup.

---

## 4) Validation Rules

Minimum validation after each code change:
- syntax checks for changed Node files
- relevant existing tests
- if user-facing flow changed, one smoke path through the changed branch

If validation cannot run, record why in `BUILD-STATUS.md`.

---

## 5) Heartbeat Mode

Mode: **Active build mode**
Cadence target: **every 10 minutes**

Heartbeat exists to wake the system up, compare current implementation status against the alignment docs, and continue working.
It should not be treated as permission to sit idle until the next beat if safe work is already underway.

When used by heartbeat automation:
- read `FULL-BUILD-SPEC.md`, `BUILD-RUNBOOK.md`, and `BUILD-STATUS.md`
- choose the next unblocked task from `BUILD-STATUS.md`
- do not branch into unrelated work
- use subagents as needed for parallel research/implementation when safe, but avoid overlapping file edits without central coordination
- make one coherent change set at a time
- cite the exact task id in the progress update
- update `BUILD-STATUS.md` after meaningful progress

Blocked/test-failure recovery rule:
- if blocked or if tests fail, review the relevant runbook/spec section, then go back to the source files for truth/alignment and try again
- run a code-review-test loop until the tests pass
- if the same error repeats **5 times** with no change in error signature, stop and record a blocker
- if the error changes, reset the retry counter and continue

Validation rule during heartbeat work:
- run syntax checks for changed files
- run relevant tests
- if user-facing flow changed, run one smoke path through the changed branch

Stop conditions:
- if blocked after the retry policy, record the blocker and next recommended action
- if nothing safe/actionable remains, return `HEARTBEAT_OK`
