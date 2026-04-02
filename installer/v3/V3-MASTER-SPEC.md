# ResonantOS Installer v3 — Master Spec

Status: Draft v0.1
Purpose: End-to-end product + build scope for the v3 installer work
Depends on:
- `DETECTOR-CONTRACT.md`
- `INSTALLER-OPTION-MODEL.md`
- `INSTALLER-FLOW-SPEC.md`

---

## 1) Goal

ResonantOS Installer v3 should become a guided terminal installer that:

- starts detection immediately on launch
- presents a clean, paged experience instead of a wall of text
- detects and explains existing OpenClaw installs clearly
- supports install-over, new install, and manual recovery paths
- supports both existing users and totally new users
- teaches only what is necessary, in context
- gets a brand-new user to the ResonantOS dashboard with a **setup agent ready** as quickly and painlessly as possible

The installer should reduce confusion, not amplify it.

---

## 2) Product Principles

### 2.1 Immediate scan, useful waiting
Detection starts immediately. The user gets useful reading material while waiting.

### 2.2 Paged, readable UX
The installer should behave like a terminal wizard, not a technical dump.

### 2.3 Branch by user situation
The flow must adapt to:
- detected existing installs
- zero detections + new user
- zero detections + existing user whose install was missed

### 2.4 Recommendation without silent action
Recommend, highlight, guide — but do not silently choose for the user.

### 2.5 New users need onboarding, existing users need recovery
New users should be taught in context.
Existing users should get fast recovery tools.

### 2.6 The wrong-machine case is real
The installer must help the user recognize when the target OpenClaw instance is on a different machine and stop them from going down the wrong path.

### 2.7 Read-only by default until install phase
The current build scope remains read-only by default until the later mutation/install execution stage.

Exception:
- explicitly user-approved remediation actions, such as dependency install/update, may make changes before the main install phase
- these must be clear, intentional, and reversible where supported

### 2.8 Cancel any time
The user should be able to cancel at any point.

Rules:
- if no changes have been applied yet, the system should remain unaffected
- if earlier remediation actions changed the system, cancel should offer a clear rollback/removal path where supported
- if cancelling would remove, downgrade, or reverse specific programs/components, the installer must say exactly what those are before confirmation

---

## 3) Current State Snapshot

### Completed foundation
- Detector contract defined
- Installer option model defined
- Deterministic detector → installer handoff implemented
- File/JSON error handling hardened
- Process-first detection clarified
- Missing-tool diagnostics surfaced
- Command execution and quoting improved
- Dead-code cleanup pass completed for safe items
- Installer options and confirmed selection structures implemented
- Tests added and passing
- Interactive selection flow implemented
- Manual existing-target and new-install path completion flows implemented
- Flow spec for paged wizard UX written

### What still remains
The remaining work is mostly **UX + orchestration + onboarding** rather than raw detector plumbing.

---

## 4) Core User Journeys

### Journey A — Existing install detected
1. Intro / scan page
2. Scan complete acknowledgement
3. Dependency issues page only if needed
4. Detected instance cards
5. Simple install intent menu
6. Docker page later if relevant
7. Review / confirm
8. Later install execution phase

### Journey B — No install detected, user is new
1. Intro / scan page
2. Scan complete acknowledgement
3. No-instance yes/no page
4. User selects `Yes, I’m new`
5. New-user onboarding wizard
6. Recommended vs Custom install
7. Docker decision later
8. Paths / ports / OpenClaw setup
9. Setup agent readiness
10. Review / confirm
11. Later install execution phase
12. Dashboard opens with setup agent ready

### Journey C — No install detected, user is not new
1. Intro / scan page
2. Scan complete acknowledgement
3. No-instance yes/no page
4. User selects `No`
5. Manual existing-target recovery first
6. Prompt for `openclaw.json`
7. Run fast targeted detection on that location
8. Build instance card from directed result
9. If wrong machine / remote topology discovered, show escape hatch + tutorial link
10. If local target validated, continue existing-user install flow

---

## 5) Locked Product Decisions

The following decisions are locked unless changed explicitly:

- Detection starts immediately on launch.
- Intro page exists to occupy the user while scanning runs.
- Scan time should be described as roughly 1–5 minutes.
- After zero detections, the installer asks whether the user is new **before** generic dependency issues.
- If user says they are new, generic dependency issues are skipped at that point and explained later in onboarding.
- If user says they are not new, manual existing-target recovery is emphasized first, but the user may pivot straight into a new install from that recovery area if they chose the wrong branch.
- Install-over menu labels should use resolved detected identity labels where possible.
- Detection should surface whether each discovered OpenClaw instance already has ResonantOS installed.
- Detected instances should be shown as readable card/block layouts.
- Docker choice comes later, not first.
- The first new-user onboarding choice is `Recommended install` vs `Custom install`.
- New-user onboarding should support `Help`, `Back`, and `Next`.
- Earlier answer changes should only invalidate dependent later steps.
- Wrong-machine / VPS / LAN situations require an explicit guidance path and tutorial link.
- Generic dependency remediation should support one-click install/update actions for non-Docker dependencies.
- Docker install/update belongs inside the Docker setup flow, not the generic dependency page.
- The setup-agent readiness stage should offer `Auto mode` and `Manual mode`.
- The ResonantOS installer may link into the minimum required OpenClaw onboarding elements directly: model setup, OAuth/token setup, and gateway setup.
- New users should ultimately land on the dashboard with a setup agent ready.
- The final end-state should open the user's default browser to the ResonantOS Dashboard with the setup agent already on screen saying welcome.

---

## 6) Remaining Implementation Scope

### 6.1 Wizard shell UX
- screen clear helpers
- paged rendering
- scan intro page
- scan complete continue page
- suppression of probe noise

### 6.2 Page ordering and branching
- zero-detection branch before dependency page
- branch to onboarding vs recovery based on yes/no
- dependency-page gating so it only shows when needed

### 6.3 Instance presentation UX
- resolved display labels
- boxed/horizontal instance cards
- clearer card spacing/layout
- low-confidence separation

### 6.4 Menu UX
- move from typed selection toward arrow-key/highlight selector
- use user-intent menu wording
- preserve recommended highlighting without auto-selection

### 6.5 Manual existing-target recovery UX
- collect `openclaw.json`
- run fast targeted detection on the supplied location
- render recovered instance card
- confirm or redirect

### 6.6 Wrong-machine / remote-topology handling
- explain when the installer is on the wrong host
- stop invalid local assumptions
- provide tutorial link placeholder

### 6.7 Dependency remediation UX
- one-click install/update actions for non-Docker dependencies
- OS/runtime-tailored automation
- clear user confirmation before remediation runs

### 6.8 Docker setup UX
- Docker decision later in the flow
- interactive Docker setup/configuration page
- Docker install/update handled inside Docker flow
- progress view plus state/intent summary before submit
- single confirmation before Docker actions run

### 6.9 New-user onboarding wizard
- stateful wizard model
- recommended vs custom page
- context-sensitive dependency explanation
- Docker later in flow
- Help / Back / Next
- dependent-state invalidation model

### 6.10 OpenClaw / setup-agent readiness
- define how installer gets the user to a ready setup agent
- support `Auto mode` (small local model)
- support `Manual mode` (API key / OAuth / curated local model menu)
- define handoff into dashboard onboarding

### 6.11 Later install execution phase
Out of current read-only scope, but the wizard must gather the right confirmed inputs for it.

### 6.12 Final cleanup and consolidation
- remove residual rough edges after UX changes land
- align docs/comments/tests with final behavior

---

## 7) Dependencies / Unknowns Still Open

These items are known but not fully solved yet:

- exact Docker management choices and wording
- exact online tutorial URL/content for wrong-machine guidance
- exact setup-agent provisioning mechanics during install
- exact curated model menu for manual agent mode
- exact ResonantOS-installed detection heuristics/status display
- future repair-installation path design (deferred, but should be supported by current detection/status data)
- final visual formatting details for cards and selector highlighting

Visual priority rule:
- best effort on visuals
- function first

These should be resolved in implementation passes, not left as accidental behavior.

---

## 8) Definition of Done for v3

v3 is considered feature-complete when:

- the installer runs as a clean paged terminal wizard
- scan starts immediately and presents useful intro content
- no-instance users are routed correctly before dependency clutter
- existing installs are shown as clear cards with resolved labels
- menu choices are simple, user-oriented, and easy to navigate
- manual recovery supports targeted directed detection from `openclaw.json`
- wrong-machine / remote-topology escape guidance exists
- new-user onboarding is stateful and navigable
- non-Docker dependency issues can be remediated in-place with user approval
- Docker appears later in the flow rather than as the opening question
- Docker setup provides interactive configuration, progress, and a final confirmation before actions run
- setup-agent readiness supports both auto and manual modes
- manual/new/existing selections all end in confirmed install-ready path state
- the wizard can hand a new user toward a dashboard with a setup agent ready
- tests still pass after the UX work

---

## 9) Source of Truth Files

Use these docs together:

- `FULL-BUILD-SPEC.md` — consolidated end-to-end product/build narrative
- `DETECTOR-CONTRACT.md` — detector contract and confirmed-path rules
- `INSTALLER-OPTION-MODEL.md` — normalized option objects and selection rules
- `INSTALLER-FLOW-SPEC.md` — detailed paged wizard behavior
- `BUILD-RUNBOOK.md` — build execution rules and phase/task order
- `BUILD-STATUS.md` — current checkpoint and next unblocked work

This file is the umbrella scope document for the rest of the build.

---

## 10) External Reference Baseline

For the actual ResonantOS dashboard and installer element structure, the current implementation baseline is:

- Repository: `https://github.com/ResonantOS/resonantos-alpha`
- Branch: `experimental/v0.6.0-linux-safe-bringup-20260402`

Usage rule:
- prefer the repo-local install contract at `install/INSTALL_SPEC.yaml` for current branch behavior
- use this branch as the working reference for:
  - current installer behavior
  - linking structure
  - dashboard integration assumptions

When a newer Linux-safe install branch supersedes this one, update the baseline here.
