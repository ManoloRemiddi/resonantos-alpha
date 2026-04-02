# ResonantOS Installer v3 — Full Build Spec

Status: Draft v0.1
Purpose: Consolidated end-to-end build specification for ResonantOS Installer v3
Supersedes: informal chat planning only (does not replace supporting docs)
Companion docs:
- `V3-MASTER-SPEC.md`
- `INSTALLER-FLOW-SPEC.md`
- `DETECTOR-CONTRACT.md`
- `INSTALLER-OPTION-MODEL.md`
- `BUILD-RUNBOOK.md`
- `BUILD-STATUS.md`

---

## 1) Executive Summary

ResonantOS Installer v3 is intended to become a **guided terminal installation wizard** that can serve both:

- **existing OpenClaw users** who want to install over, recover, or update an existing instance, and
- **new users** who have never used OpenClaw or ResonantOS before.

The installer should:

- begin detection immediately on launch
- provide useful reading material while detection runs
- avoid wall-of-text output
- present clean pages with clear branch logic
- support install-over, new install, and manual recovery paths
- detect whether each discovered OpenClaw instance already has ResonantOS installed
- teach only what matters when it matters
- prepare the user to arrive at the **ResonantOS Dashboard** with a **setup agent already on screen saying welcome**

This spec exists to make sure the **whole product vision** is captured, not just the next coding task.

---

## 2) Product Goal

The goal of v3 is:

> get the user to a correct, confirmed, install-ready ResonantOS setup with the least confusion possible, and for a new user, land them in the dashboard with a setup agent ready to guide the rest.

This means the installer is not merely a detector or a script launcher.
It is a **decision-support and onboarding bridge**.

---

## 3) User Types

The installer must explicitly support these user situations.

### 3.1 Existing local OpenClaw user, instance detected
The detector finds a usable existing install.

Needs:
- clear instance identification
- confidence in which install target is which
- easy install-over selection
- minimal unnecessary explanation

### 3.2 Existing local OpenClaw user, instance not detected
The detector misses their install.

Needs:
- recovery flow
- directed detection from `openclaw.json`
- a clear path to confirm the correct target
- the ability to start a new install from that same recovery screen if they realize that is what they actually want

### 3.3 New user with no existing install
No instances are found and the user confirms they are new.

Needs:
- onboarding, not jargon
- guidance in context
- Docker explained later, not first
- OpenClaw and setup-agent readiness handled by the installer
- a path into the minimum required OpenClaw onboarding elements inside the ResonantOS installer, including model setup, OAuth/token setup, and gateway setup

### 3.4 User on the wrong machine / remote topology
The target install is on a VPS, LAN machine, or elsewhere.

Needs:
- explanation that the installer must run on the same target machine
- a graceful stop/restart path
- tutorial/help link

### 3.5 Advanced user / custom setup user
May want Docker, custom paths, custom ports, or manual model/provider setup.

Needs:
- custom route
- reviewable decisions
- explicit confirmation before actions

---

## 4) Design Principles

### 4.1 Scan first, always
Detection starts immediately at launch.
Every user benefits from it.

### 4.2 Reading while waiting
Because detection can take 1–5 minutes, the intro page should give the user useful context instead of leaving them staring at dead air.

### 4.3 Paged wizard, not console dump
Major steps belong on distinct pages.
The user should never be asked to parse one giant scrollback blob.

### 4.4 Show only what matters now
If a page is not relevant, skip it.
If no dependency issues exist, do not show a dependency page.
If the user is new, do not front-load dependency jargon before context.

### 4.5 Recommend without hijacking
The installer may recommend an option, but the user must explicitly choose.

### 4.6 Function first, visuals second
Best-effort polish matters, but correctness and clarity come first.

### 4.7 Read-only by default until install phase
Everything up to final install execution should remain read-only / confirmatory **by default**.
The wizard gathers and validates state; it does not silently mutate early.

Exception:
- explicitly user-approved remediation actions, such as dependency install/update, may perform changes before the main install phase
- these actions must always be clear, intentional, and reversible where supported

### 4.8 Cancel any time, with safe rollback behavior
The user should be able to cancel at any time.

Rules:
- cancel should leave the system unaffected wherever no changes have yet been applied
- if earlier user-approved dependency remediation has changed the system, cancel should offer a clear rollback/removal path where supported
- if cancelling now would remove, downgrade, or reverse specific programs/components, the installer must say exactly what those are before proceeding
- cancel must never leave the user with a hidden half-state or silent partial mutation

---

## 5) Current Completed Foundation

The following base work is already substantially complete:

- detector contract defined
- normalized option model defined
- deterministic detector → installer handoff implemented
- entrypoint error handling hardened
- process-first detection clarified
- missing-tool diagnostics surfaced
- safer command execution / quoting landed
- safe dead-code cleanup completed
- installer options + confirmed selection structures implemented
- tests added and passing
- interactive selection flow implemented
- manual existing-target and new-install path completion flows implemented
- paged wizard flow design/spec work written

This means the remaining work is primarily **UX, orchestration, onboarding, and final integration logic**.

---

## 6) Locked Product Decisions

The following are treated as explicit product decisions.

### 6.1 Detection and opening behavior
- detection begins immediately on launch
- opening page exists to occupy the user while scanning runs
- scan duration should be described as approximately 1–5 minutes
- opening page should suggest the user can wait / grab a coffee
- screen should clear on launch and between major pages

### 6.2 Branch ordering
- after zero detections, ask whether the user is new **before** generic dependency issues
- if user says `Yes`, enter new-user onboarding and skip generic dependency page at that moment
- if user says `No`, route into manual existing-target recovery first
- from that recovery area, the user may pivot directly into a new install without being sent back through earlier branch screens

### 6.3 Detected instance presentation
- install-over labels should use resolved detected instance names where possible
- detection should surface whether each discovered OpenClaw instance already has ResonantOS installed
- detected instances should appear as readable card/block layouts
- low-confidence matches should be visually separated

### 6.4 Menu behavior
- menu items should be simple and user-oriented
- recommendation may be highlighted, but not silently selected
- arrow-key highlight menu is preferred for main selection UX

### 6.5 Dependency handling
- non-Docker dependencies should support one-click install/update actions
- Docker is not part of generic dependency remediation
- Docker install/update belongs inside the Docker setup flow

### 6.6 Docker flow
- Docker appears later, not first
- Docker setup page should be interactive
- it should run Docker-related commands based on user choices
- it should show progress
- it should show a live state/intent summary
- it should require one final confirmation before submit

### 6.7 New-user onboarding
- first onboarding choice is `Recommended install` vs `Custom install`
- onboarding should support `Help`, `Back`, and `Next`
- earlier answer changes should invalidate only dependent later state
- Docker-specific later content should disappear if Docker is later deselected

### 6.8 Setup-agent readiness
- setup-agent readiness is part of the installer’s responsibility
- the ResonantOS installer may link directly into the minimum required OpenClaw onboarding elements: model setup, OAuth/token setup, and gateway setup
- user should reach the dashboard with a setup agent ready
- the readiness stage should support:
  - `Auto mode`: installer downloads a small local model for setup-agent use
  - `Manual mode`: user chooses backend/model via API key, OAuth, or curated local model menu

### 6.9 Final landing state
At the end of the successful setup flow, the installer should:
- open the user’s default browser
- load the ResonantOS Dashboard
- present the setup agent already on screen
- have the setup agent already saying welcome

### 6.10 External implementation baseline
The current implementation baseline for this vendored installer copy is:
- repo: `https://github.com/ResonantOS/resonantos-alpha`
- branch: `experimental/v0.6.0-linux-safe-bringup-20260402`

For branch-specific behavior, prefer the repo-local install contract at `install/INSTALL_SPEC.yaml` over older installer assumptions.

---

## 7) System Boundaries

### In scope for this spec
- detector behavior as it affects installer decision-making
- installer terminal UX
- user-facing branch logic
- dependency handling strategy
- Docker setup flow placement and behavior
- path/port collection and confirmation
- manual recovery flow
- new-user onboarding flow
- setup-agent readiness decision point
- browser/dashboard landing behavior
- build phases and validation expectations

### Out of scope for current read-only phase
- actual install/mutation execution details in full depth
- final dashboard internal UX beyond the initial landing handshake
- final tutorial content for complex/remote setups
- permanent model catalog for manual setup mode

Those can be referenced and scaffolded, but not treated as already solved.

---

## 8) Top-Level User Journeys

## Journey A — Detected existing install
1. Launch / scan intro page
2. Scan completes
3. Continue page
4. Dependency issues page only if relevant
5. Detected instance cards page
6. Simple install intent menu
7. Docker page later if selected/relevant
8. Review / confirm
9. Later install execution phase
10. Browser opens dashboard with setup agent welcome

## Journey B — No install found, user is new
1. Launch / scan intro page
2. Scan completes
3. Continue page
4. No-instance yes/no page
5. User chooses `Yes`
6. Enter new-user onboarding wizard
7. Recommended vs Custom page
8. Docker decision later
9. Paths / ports page
10. OpenClaw / setup-agent readiness page
11. Review page
12. Later install execution phase
13. Browser opens dashboard with setup agent welcome

## Journey C — No install found, user is not new
1. Launch / scan intro page
2. Scan completes
3. Continue page
4. No-instance yes/no page
5. User chooses `No`
6. Manual existing-target recovery flow
7. Prompt for `openclaw.json`
8. Run targeted detection on that location only
9. Build recovered instance card
10. If wrong machine / remote topology is discovered, show escape hatch
11. If valid local target found, continue existing-user flow

---

## 9) Page-by-Page Functional Spec

## 9.1 Launch / Detection Intro Page

Purpose:
- occupy the user while the scan runs
- explain what the installer is doing
- explain what kind of choices will come next

Must include:
- that the installer is scanning for OpenClaw installs, Docker, and install signals
- that the scan may take 1–5 minutes
- that this is normal
- a brief preview of likely outcomes:
  - install over existing instance
  - recover missed instance
  - start a new install

Must end with, once scan completes:
- `Scan complete.`
- `Press any key to continue. This page will clear, so finish reading first.`

## 9.2 Zero-Detection Decision Page

If zero instances are found, show only:
- `No detected instances of OpenClaw.`
- `Are you new to OpenClaw and ResonantOS?`

Choices:
- Yes
- No

No clutter, no extra explanation, no dependency noise.

## 9.3 Dependency Issues Page

Show only when relevant.
Skip entirely when all checks pass.

Must:
- present only failing/relevant dependency issues
- explain them in plain language
- offer one-click install/update for non-Docker dependencies
- ask for confirmation before running remediation

Must not:
- treat Docker as a generic dependency fix item here

## 9.4 Detected Instances Page

Must render detected instances as readable horizontal cards/blocks with spacing.

Each card should show:
- resolved label/name
- running/not running
- ResonantOS installed status
- config path
- workspace path
- install root
- gateway / port info where relevant
- evidence summary / confidence

Low-confidence possible matches should be separated.

## 9.5 Main Install Intent Menu

Must be simple and user-oriented.

Example entries:
- Correct an instance detail
- Install over Atlas
- Install over Sentry
- Install over Helm
- Install new default path instance
- Install new custom path instance

Selection method target:
- up/down highlight
- Enter to confirm

## 9.6 Manual Existing-Target Recovery Flow

Purpose:
- recover an existing install the detector missed

Steps:
1. ask for location of `openclaw.json`
2. validate path entry
3. run fast targeted detection only on that location
4. build recovered instance card
5. allow user to confirm and continue
6. if the user realizes they actually want a new install instead, allow them to pivot directly into the new-install path from this same recovery area without sending them back to an earlier screen

Wrong-machine escape must appear here.

## 9.7 Wrong-Machine / Remote-Topology Escape Page

Show when the user discovers the actual target install is not on the current machine.

Must explain:
- the installer needs to run on the same machine as the target OpenClaw instance
- if the instance is on a VPS or another LAN machine, the user should stop and run the installer there instead
- advanced setups are supported by following a tutorial

Must include:
- tutorial link placeholder
- graceful exit/back behavior

## 9.8 New-User Onboarding Wizard

Stateful wizard with:
- Help
- Back
- Next
- Cancel / Exit

First page:
- Recommended install
- Custom install

Must preserve state across steps.
Changing earlier answers must invalidate only dependent later branches.

## 9.9 Docker Page

Shown after install-style selection, not before.

Must:
- explain Docker plainly
- let user choose whether to use it
- if yes, check Docker and install/update/confirm readiness

## 9.10 Docker Management Page

Conditional on Docker being enabled.

Must:
- run Docker-related commands for the user based on chosen config
- show progress
- show live state/intent summary
- require one final confirmation before submission

Must work for:
- existing-instance reuse
- new-instance creation

## 9.11 Paths and Ports Page

Must collect and confirm:
- install paths
- workspace path
- ports

Must:
- prefill sane defaults
- allow modification
- distinguish defaults from custom values clearly

## 9.12 OpenClaw / Setup-Agent Readiness Page

Purpose:
- bridge the user toward a ready first-run assistant experience
- link into the minimum required OpenClaw onboarding elements from inside the ResonantOS installer

Minimum required OpenClaw onboarding elements:
- set model
- set OAuth or token/auth method
- set gateway

Modes:
- Auto mode
- Manual mode

Auto mode:
- installer downloads a small local model
- model is used as setup agent
- fastest path

Manual mode:
- user selects backend/model source
- options may include API key, OAuth, curated local model menu
- installer prepares chosen backend/model before finish

## 9.13 Review Page

Must show a clean final summary of:
- chosen install mode
- target instance or new install path
- Docker choice/config
- paths and ports
- setup-agent readiness mode
- install-ready state

## 9.14 Install + Launch Page

This is the bridge to the later mutation phase.

Desired final outcome after installation succeeds:
- user’s default browser opens
- ResonantOS Dashboard loads
- setup agent is already on screen and saying welcome

---

## 10) Data and Decision Contracts

## 10.1 Detector contract
Canonical output is a structured object for installer consumption.
JSON/debug artifacts remain secondary.

## 10.2 Option contract
Installer options must support:
- existing
- possibleMatch
- new
- manual

With normalized fields for display, confidence, paths, and recommendation state.

## 10.3 Confirmed selection contract
Installer may only proceed on confirmed, absolute paths.

Required core fields:
- `selectionType`
- `selectedOptionId`
- `displayLabel`
- `configPath`
- `workspacePath`
- `installRoot`
- `runtimeKind`
- `isRunning`
- `confidence`
- `confirmedByUser`

Manual/new flows must collect missing paths before proceeding.

---

## 11) State Management Spec

The installer must behave like a stateful wizard, not a linear text script.

### Core rule
Changing an early answer invalidates only downstream state that depends on it.

### Examples
- if Docker was enabled, Docker-specific pages become active
- if Docker is later disabled, Docker-specific pages disappear
- unrelated settings remain intact
- if install style changes, only dependent downstream pages are recalculated

### Hidden branch rule
When a branch becomes invalid:
- stop showing it
- stop using it for later logic
- do not corrupt unrelated state

---

## 12) Validation and Safety Rules

### Path input
All installer-used paths must be absolute and validated.

### Confirmation
Any high-impact user choice should be summarized and confirmed.

### Non-interactive runs
If no TTY is present, fail clearly rather than pretending the wizard can run.

### Probe noise
Low-level probe output should be suppressed from user-facing UX.

### Dependency actions
One-click remediation should always be explicit and user-approved.

### Docker actions
Docker setup actions should show intent first, then require confirmation.

---

## 13) Open Questions / Remaining Explicit Placeholders

These are known and addressed, but not fully specified yet.

### 13.1 Wrong-machine tutorial URL/content
Status: placeholder intentionally
Handling: keep link slot in spec and flow until content exists

### 13.2 Exact Docker management wording/details
Status: partially defined
Handling: page behavior is locked, exact wording/details remain refinable

### 13.3 Setup-agent provisioning mechanics
Status: outcome is locked, exact implementation details still open
Handling: auto/manual split is locked; exact provisioning mechanics may vary

### 13.4 Curated model menu for manual mode
Status: open
Handling: manual mode exists in spec, curated model list remains to be defined

### 13.5 Final visual style
Status: open
Handling: best effort; function first

### 13.6 Browser-launch/dashboard-handshake mechanics
Status: outcome locked, exact implementation not yet specified
Handling: browser opening + welcome agent is required result even if mechanics evolve

### 13.7 ResonantOS-installed detection heuristics
Status: required outcome, exact implementation still open
Handling: the detector must surface whether each discovered OpenClaw instance already has ResonantOS installed, especially where multiple instances exist

### 13.8 Repair installation function
Status: deferred to later version
Handling: current detection and instance display should preserve enough ResonantOS-installed state that a future repair-install path can be added cleanly

---

## 14) Build Phasing

The work remaining should proceed in these groups.

### Phase UX
- clear-screen shell
- intro/waiting page
- noisy output suppression
- correct branch ordering
- dependency page gating
- dependency remediation actions
- instance cards
- simple menu
- arrow-key selector

### Phase REC
- zero-detection recovery entry
- `openclaw.json` prompt
- targeted single-location detection
- wrong-machine / topology escape page

### Phase NEW
- recommended vs custom page
- wizard state model
- help/back/next
- dependent-state invalidation
- Docker placement
- Docker check + install/update
- interactive Docker setup page
- paths/ports page
- setup-agent readiness
- auto/manual mode handling

### Phase REV
- review page
- install-phase prep contract
- dashboard landing contract

### Phase CLN
- residual cleanup
- docs/tests alignment
- final polish

---

## 15) Validation Requirements

Minimum validation after each meaningful change:
- syntax checks for changed Node files
- relevant existing tests
- one smoke path through changed user-facing branch

At broader checkpoints:
- `npm test` remains green
- no regression in detector handoff
- no regression in manual/new confirmation flow

---

## 16) Definition of Done

The build is done when:
- the installer is a clean paged wizard
- the scan intro/waiting behavior is correct
- no-instance branching is correct
- existing users can recover missed installs
- new users can onboard without being dumped into jargon too early
- non-Docker dependency fixes are available in place
- Docker flow is interactive and confirmed
- setup-agent readiness is handled through auto/manual modes
- the final experience opens the default browser to the dashboard with the setup agent welcoming the user
- tests still pass
- docs reflect the implemented behavior

---

## 17) Source of Truth Relationship

This document is the **single broad build narrative**.

Supporting docs still matter:
- `DETECTOR-CONTRACT.md` — detector/handoff rules
- `INSTALLER-OPTION-MODEL.md` — option/selection data model
- `INSTALLER-FLOW-SPEC.md` — detailed page behavior
- `BUILD-RUNBOOK.md` — execution order and task IDs
- `BUILD-STATUS.md` — current checkpoint and next task

If this spec and a supporting doc diverge, the divergence should be resolved explicitly rather than hand-waved.
