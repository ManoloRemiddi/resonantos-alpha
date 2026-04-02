# Installer Flow Spec

Status: Draft v0.1
Depends on:
- `DETECTOR-CONTRACT.md`
- `INSTALLER-OPTION-MODEL.md`

Scope: Human-facing terminal flow for ResonantOS Installer v3

---

## 1) Purpose

This document defines the **paged installer flow** for ResonantOS Installer v3.

The goal is to replace the current wall-of-text experience with a guided terminal wizard that:

- starts scanning immediately on launch
- gives the user something useful to read while detection runs
- presents information in clean pages with clear separation
- adapts the flow for:
  - users with detected OpenClaw instances
  - users with no detected instances who are new
  - users with no detected instances who are not new
- collects and confirms paths cleanly before installation begins
- gets a new user to the ResonantOS dashboard with a setup agent ready as quickly and painlessly as possible

This flow remains **read-only** until the later install/mutation phase.

---

## 2) Design Principles

### 2.1 Scan starts immediately
The detection scan begins as soon as the installer launches.

Reasoning:
- every user benefits from the scan
- the scan may take time, so it should begin immediately
- the user can read the intro content while the scan runs

### 2.2 Paged experience
The installer should use distinct pages/screens rather than one continuous text dump.

Rules:
- clear the screen at the start
- clear the screen between major pages
- each page should contain one main job or question
- each page should be easy to read quickly

### 2.3 Show only what matters on each page
- if dependency checks are clean, do not show a dependency issues page
- if no instances are detected, do not dump instance-related detail blocks first
- if the user is new, do not confront them with unexplained dependency jargon too early

### 2.4 Recommendation, not auto-selection
- recommended choices should be highlighted
- nothing should be silently auto-selected for the user
- user confirmation remains authoritative

### 2.5 New users need guidance, not raw technical output
A new user should not need to understand OpenClaw internals before reaching ResonantOS.

The installer should carry enough setup burden that the user lands on the dashboard with a **setup agent ready to talk to them**.

### 2.6 Existing users need recovery tools
If the detector misses an install, the flow should help the user recover it quickly.

### 2.7 Complex topology requires an escape hatch
The installer must acknowledge that some users will discover their OpenClaw instance is on:
- a VPS
- another LAN machine
- a different host than the one running the installer

The flow must provide a clear “wrong machine / complex setup” guidance path and a tutorial link.

---

## 3) Global UX Rules

### 3.1 Screen clearing
- clear the terminal when the program begins
- clear the terminal between major pages
- when a page says it will clear, warn the user before waiting for input

### 3.2 Probe noise suppression
Raw probe noise should not leak into the user-facing flow.

Examples to suppress or hide:
- PowerShell progress bars
- network test noise
- low-level probe command output

The detection page should own the screen visually.

### 3.3 Navigation
There are two navigation styles in this flow:

#### A) Simple page continue
Used for:
- scan complete acknowledgement
- basic summaries

Prompt style:
- `Press any key to continue. This page will clear.`

#### B) Stateful wizard navigation
Used for onboarding and later decision trees.

Required capabilities:
- `Next`
- `Back`
- `Help`
- `Cancel / Exit`

### 3.4 Selection controls
Where the user is selecting among menu options, prefer:
- up/down arrow navigation
- a visible highlight/selector
- Enter to confirm

Avoid relying on freeform typed input for the main menu once the paged UX pass is implemented.

### 3.5 Input confirmation
When the user provides paths or other high-impact values:
- normalize the inputs
- validate them
- show a confirmation summary
- require explicit confirmation before proceeding

### 3.6 Cancel / rollback safety
The user should be able to cancel at any time.

Rules:
- if no changes have been applied yet, cancel should leave the system unaffected
- if the user has already approved dependency remediation or another reversible pre-install action, cancel should offer a clear rollback/removal path where supported
- if cancelling now would remove, downgrade, or reverse specific programs/components, the installer must tell the user exactly which ones before confirmation
- the installer should never leave a silent partial state behind on cancel

---

## 4) Top-Level Flow Overview

The installer has three top-level branches after scan:

1. **Detected instances found**
2. **No instances found + user says they are new**
3. **No instances found + user says they are not new**

High-level order:

1. Launch / scan intro page
2. Scan complete acknowledgement
3. Branch based on detection result
4. Proceed into either:
   - dependency issues + detected-instance flow
   - new-user onboarding
   - manual existing-target recovery flow

---

## 5) Page 1 — Launch / Detection Intro Page

### Purpose
Give the user useful reading material while the scan runs.

### Timing
- screen clears immediately on launch
- scan begins immediately
- page stays visible while the scan runs

### Content goals
The page should explain:
- the installer is scanning the PC for:
  - OpenClaw instances
  - Docker containers / Docker availability
  - key install signals and dependencies
- what the install process will do next
- that the scan may take **1–5 minutes**
- that the user can grab a coffee / please wait

### Example content shape
- welcome line
- one paragraph on what is being scanned
- one paragraph previewing what happens next
- one short note on likely paths:
  - install over existing instance
  - recover missed instance
  - start a new install

### End state
When the scan finishes, the page should show:

- `Scan complete.`
- `Press any key to continue. This page will clear, so finish reading first.`

---

## 6) Post-Scan Branching Rules

### 6.1 If one or more instances are detected
Flow order:
1. dependency issues page **only if needed**
2. detected instances page
3. install target selection
4. later pages such as Docker choice

### 6.2 If zero instances are detected
The installer should **not** jump straight into dependency issues.

Instead, show the dedicated no-instance question page first.

---

## 7) Page 2 (Zero Detections) — New or Existing User Question

### Purpose
Disambiguate between:
- truly new user
- existing user whose install was not detected

### Content rule
This page should contain only the following idea, with no clutter:

- `No detected instances of OpenClaw.`
- `Are you new to OpenClaw and ResonantOS?`

### Controls
- Yes
- No

### Meaning of answers
#### Yes
The user confirms they are new.

Result:
- skip the separate dependency issues page at this stage
- enter **new-user onboarding**

#### No
The user says they have used it before.

Result:
- do **not** send them into new-user onboarding
- route them into **manual existing-target recovery first**
- dependency issues will still matter for this existing-user flow

---

## 8) Dependency Issues Page

### Show conditions
Show this page only when there are actual issues relevant to the current branch.

### Hide conditions
If all dependency checks pass, skip this page entirely.

### Branch-specific behavior
#### New user branch
Do **not** show the generic dependency issues page immediately after “Yes, I’m new.”

Reasoning:
- a new user likely does not understand the dependencies yet
- some dependencies are optional or situational, especially Docker
- these choices should be explained in context during onboarding

#### Existing / detected-install branch
Show dependency issues in the standard flow when relevant.

### Content goals
- show only failing / relevant dependency issues
- explain what each issue means in plain language
- present likely resolution actions

### Remediation behavior
For non-Docker dependencies, the dependency page should support **fix-on-the-spot actions**.

Rules:
- the user should be able to choose a one-click install/update action
- the exact automation will be tailored to the current OS/runtime
- there are not expected to be many user-facing choices here beyond whether to proceed
- remediation should be presented as install/update of the dependency, not as a complex configuration wizard
- if the user later cancels and those dependency changes are reversible, the installer should warn clearly and offer rollback/removal with an explicit list of affected programs/components

Important:
- **Docker is not part of generic dependency remediation on this page**
- Docker install/update should be handled later, inside the Docker setup flow, when the user has actually chosen to use Docker

---

## 9) Detected Instances Page

### Purpose
Show the detected install targets clearly and make it easy to compare them.

### Presentation style
The page should use a set of **horizontal boxed cards / blocks** with spacing between them.

Each instance block should be easy to scan.

### Each instance block should show
- resolved instance label/name
  - prefer the identity/detected label found during detection
  - examples: `Atlas`, `Sentry`, `Helm`
- runtime status
- ResonantOS installed status
- config path
- workspace path
- install root
- gateway / port info where relevant
- confidence / evidence summary

### Label rule
Install-over menu labels should use the resolved detected label first.

Fallback if no good label exists:
- a readable path-based label
- never generic nonsense if a better identity is available

### Possible matches
Low-confidence results should appear separately and be clearly marked.

---

## 10) Main Install Target Menu

### Purpose
Convert the detected information above into a simple, intent-based menu.

### Interaction style
- up/down arrow selector
- highlight current row
- Enter to confirm

### Menu design rule
Menu items should be simple and user-oriented, not technical.

### Example menu items
- `Correct an instance detail`
- `Install over Atlas`
- `Install over Sentry`
- `Install over Helm`
- `Install new default path instance`
- `Install new custom path instance`

### Notes
- recommendation may affect which item is initially highlighted, but not silently selected
- menu text should reflect the resolved instance label
- detailed technical info remains in the cards above, not in the menu labels

---

## 11) Manual Existing-Target Recovery Flow

### Entry conditions
This flow is emphasized when:
- zero instances were detected
- user answers `No` to “Are you new?”

It may also be available from a `Correct an instance detail` path later.

### Recovery objective
Let the user point the installer at an existing OpenClaw install that the detector missed.

Important flexibility rule:
- if the user realizes from this recovery screen that they actually want a new install, they should be able to pivot directly into the new-install path without being sent back through earlier branch screens

### Flow steps
1. Ask the user for the location of `openclaw.json`
2. Provide a quick action to run **targeted detection on that one location only**
3. Build a proper instance card from that targeted result
4. Let the user confirm / install over that recovered instance
5. Also provide a direct path to start a new install from this same area if the user selected the wrong branch earlier

### Important behavior
This recovery pass should be quick because it is evaluating one directed target, not performing a wide scan again.

### Wrong-machine / complex-setup escape hatch
This is also the point where users may realize:
- they are installing on the wrong machine
- the real OpenClaw instance is on a VPS
- the real OpenClaw instance is on another LAN machine
- they are dealing with a more complex topology

The flow must provide a clear escape hatch page that says, in plain terms:
- this installer needs to run on the same machine as the target OpenClaw instance
- if the instance is elsewhere, stop here and run the installer on that machine instead
- for advanced setups, read the online tutorial

### Tutorial link
Include a link placeholder for a separate tutorial we will create later.

### Later-version note
A future version may add a dedicated repair-installation function.
For now, this flow should still surface whether the recovered/local instance already has ResonantOS installed.

---

## 12) New-User Onboarding Flow

### Entry condition
- zero instances detected
- user answers `Yes` to “Are you new?”

### Goal
Teach only what is necessary, in context, while moving the user toward a working ResonantOS install.

The onboarding should end with the user arriving at the dashboard with a **setup agent ready**.

### Navigation requirements
This flow must be a **stateful wizard** with:
- Help
- Back
- Next
- Cancel / Exit

### Help behavior
Each onboarding point should offer a help section explaining:
- the current decision
- why it matters
- the common/default recommendation

### First onboarding page after “Yes, I’m new”
The first page should be:
- `Recommended install`
- `Custom install`

This is a locked decision.

### Why this comes first
Most new users should not be forced into technical branching before they choose whether they want:
- the simple recommended path, or
- a more custom path

---

## 13) New-User Onboarding Suggested Page Sequence

### 13.1 Install style page
Choices:
- Recommended install
- Custom install

### 13.2 Docker page
Show Docker after install style selection.

Rules:
- Docker choices should be explained in plain language
- Docker is optional and should not be treated as assumed knowledge
- Docker content should be more prominent in Custom mode, but still available in Recommended mode if desired by product design
- once the user chooses to use Docker, the installer should check for Docker and either install it, update it, or confirm it is ready

### 13.3 Docker management page (conditional)
Only appears if Docker is enabled.

This page should be interactive and should:
- run Docker-related commands for the user based on the chosen setup
- show progress while Docker install/update/setup actions are running
- show a live state/intent summary so the user can see what the installer is preparing to do
- require a single explicit confirmation before the Docker setup actions are submitted

Docker-specific dependency behavior:
- Docker installation/update is handled here, not on the generic dependency page
- this is where the installer figures out the container-management shape the user wants
- this page must work for both:
  - reuse of existing instances, and
  - creation of new instances

### 13.4 Paths and ports page
Collect and confirm:
- install paths
- workspace paths
- port defaults with ability to modify

Rules:
- prefill sane defaults
- clearly distinguish defaults from custom values

### 13.5 OpenClaw / agent readiness page
This page handles enough setup that the user reaches the dashboard with a ready setup agent.

Important principle:
- the installer gets the user to the runway
- the dashboard onboarding takes over after landing

This page should link into the minimum required OpenClaw onboarding elements from inside the ResonantOS installer.

Minimum required OpenClaw onboarding elements:
- set model
- set OAuth or token/auth method
- set gateway

This page should offer two setup modes:

#### A) Auto mode
- the installer downloads a small local model
- that model is used as the setup agent
- the goal is the fastest path to a working first-run assistant

#### B) Manual mode
- the user chooses how to provide the model/backend
- options may include:
  - API key
  - OAuth
  - local model download from a curated menu of suitable models
- the installer then prepares that chosen model/backend so the setup agent is ready when installation completes

Outcome rule:
- regardless of mode, installation should finish with the setup agent prepared and ready for first interaction on the dashboard

### 13.6 Review page
Show a clean summary of:
- install style
- Docker choice
- paths
- ports
- OpenClaw setup state
- agent readiness

### 13.7 Install + launch
At the end of this flow:
- install executes in the later mutation phase
- the installer loads the user's default browser
- the browser opens the ResonantOS Dashboard
- the setup agent is already on screen and says welcome as the first experience

---

## 14) Existing / Detected-Install Flow

### Entry condition
One or more instances were detected.

### Suggested order
1. dependency issues page, only if needed
2. detected instances page with clear cards
3. simple menu of install intents
4. Docker choice page later, after install target choice
5. subsequent configuration pages

### Menu emphasis
Use install-over labels based on resolved instance names.

Examples:
- Install over Atlas
- Install over Sentry
- Install over Helm

---

## 15) Docker Choice Placement

Docker choice should **not** be the first thing the user sees.

Placement rule:
- for detected/existing-user install flows: Docker choice comes after install target selection
- for new-user onboarding: Docker choice comes after install style selection

Reasoning:
- install target / install style is easier for the user to understand first
- Docker is a deployment decision, not the opening question

---

## 16) State Management Rules for the Wizard

The installer should maintain wizard state across pages.

### Core rule
Changing an early answer should invalidate only the dependent later answers.

It should **not** blank unrelated parts of the flow.

### Examples
- if the user initially chooses Docker, later Docker pages/fields become active
- if the user goes back and deselects Docker, Docker-specific later pages should disappear
- Docker-specific stored values may be cleared or ignored, but unrelated choices should remain intact
- if the user changes install style, only dependent pages should be recalculated

### Hidden branch rule
If a branch is no longer valid due to an earlier answer, the branch should:
- stop being displayed
- stop driving later logic
- not corrupt unrelated state

---

## 17) Confirmation Rules

### Existing detected install
- confirm chosen instance label
- confirm config/workspace/install-root paths
- confirm any relevant runtime interpretation

### Manual existing-target recovery
- confirm the user-supplied `openclaw.json`
- confirm the targeted-detection-derived instance card
- confirm chosen target before proceeding

### New install
- confirm selected mode
- confirm planned install root / workspace / ports
- confirm any Docker choice
- confirm readiness to proceed to install phase

---

## 18) Error / Escape Handling

### Invalid path input
- show clear validation errors
- remain on the current page
- do not discard valid prior state unless necessary

### No TTY / non-interactive mode
If the installer is run in a non-interactive environment:
- fail clearly
- explain that interactive terminal mode is required for the paged wizard

### Wrong machine / remote topology
If the user is on the wrong machine or has a remote topology:
- explain the situation clearly
- stop them from proceeding down the wrong assumption path
- provide tutorial link

---

## 19) Implementation Notes for the Next UX Pass

The paged UX implementation will likely require:
- terminal screen clear helper
- page renderer(s)
- arrow-key selector menu
- stateful onboarding model
- targeted detection path for manual recovery from a provided `openclaw.json`
- suppression of noisy probe output from the detection phase

Reference baseline for real dashboard/installer linking work:
- use `https://github.com/ResonantOS/resonantos-alpha` branch `experimental/v0.6.0-linux-safe-bringup-20260402` as the current reference for:
  - dashboard element structure
  - installer element structure
  - linking expectations into the current ResonantOS experience
- if branch behavior and docs disagree, prefer `install/INSTALL_SPEC.yaml`

This is expected. The current terminal flow is functional groundwork, but not yet the final wizard UX.

---

## 20) Open Items / To-Do

These items are intentionally recognized but not yet fully specified:

- exact online tutorial URL/content for wrong-machine guidance
- exact Docker management choices and wording beyond the interactive submit/confirm/progress model
- exact setup-agent provisioning details during install
- exact curated model menu for manual mode
- exact visual style of boxed instance cards and selector highlight in the terminal

Visual priority rule:
- best effort on visuals
- function first

---

## 21) Acceptance Criteria

This flow spec is satisfied when the implementation provides:

- immediate scan start on launch
- readable intro content while scan runs
- scan complete acknowledgement before page clear
- clear paged navigation instead of a text wall
- no-instance branch before dependency issues
- `Yes, I’m new` → onboarding
- `No, I’m not new` → manual existing-target recovery first
- detected instances shown as readable blocks/cards
- simple install intent menu using resolved labels
- Docker choice later in the flow, not at the start
- help/back/next behavior for new-user onboarding
- dependent-state invalidation rather than full state wipe
- wrong-machine / remote-topology escape hatch with tutorial link placeholder

---

## 22) Current Product Decisions Locked In

The following decisions are currently locked for v3 flow design:

- scan starts immediately on launch
- intro page exists to give the user useful reading material during scan time
- scan may take 1–5 minutes; the installer should say so
- zero-detection branch happens before dependency issues
- if zero detections and user says `Yes`, skip generic dependency page and enter onboarding
- if zero detections and user says `No`, emphasize manual existing-target recovery first
- first new-user onboarding choice is `Recommended install` vs `Custom install`
- Docker choice comes later, not first
- install-over menu labels should resolve to the detected instance label/name where possible
- new users should ultimately land on the ResonantOS dashboard with a setup agent ready
