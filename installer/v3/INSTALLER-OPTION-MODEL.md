# Installer Option Model

Status: Draft v0.1
Depends on: `DETECTOR-CONTRACT.md`
Scope: User-facing install choices produced from detector results

## 1) Purpose

This document defines how raw detector findings are converted into a clean set of installer choices.

The goal is to:

- present a **small, understandable list of options** to the user
- make it easy to visually distinguish **discovered instances** from their supporting details
- allow the user to explicitly select the correct target
- produce one confirmed selection object for the installer to consume

This model is intentionally focused on **decision support**, not technical reporting.

## 2) First Choice Screen Model

The first installer choice screen should be a **single flat list of options**.

Option groups should appear in this order:

1. **Recommended existing install** (if present)
2. **Other detected existing installs**
3. **Possible matches** (low confidence, warning-labelled)
4. **Start a new install**
5. **Choose path manually**

### UX rule

The screen should be easy to scan at a glance:

- each option should have a short, readable title
- each option should have a compact summary line
- detailed technical fields should be visually secondary
- instance details should be grouped and indented under the option, not mixed into the title

## 3) Visual / Formatting Rules

Each option should be rendered like a **card or clearly separated block**, not as a dense blob of JSON-like text.

### Each option should contain

- **Title**
  - e.g. `Install over existing OpenClaw instance`
- **Label**
  - human-readable instance label
  - e.g. `OpenClaw on D:\openclaw-backup\gateway`
- **Badges / markers**
  - `Recommended`
  - `Running`
  - `Not running`
  - `ResonantOS installed`
  - `ResonantOS not detected`
  - `Possible match`
  - `Manual`
  - `New install`
- **Short summary**
  - one sentence explaining what this option means
- **Details section**
  - config path
  - workspace path
  - install root
  - runtime kind
  - confidence / evidence summary

### Presentation rules

- strong options should be visually distinct from low-confidence options
- low-confidence options must include an explicit warning line
- recommendation should be highlighted, but **not auto-selected**
- the user must always make an explicit choice

## 4) Option Types

The system must support these option types.

### A) Existing detected install

Represents a detected install target that appears real enough to offer directly.

Required behavior:

- may be recommended
- may be running or not running
- must include absolute paths where available
- may be selected directly by the user

### B) Possible match

Represents a lower-confidence candidate.

Required behavior:

- shown separately from strong options
- must include warning text
- may still be selected by the user
- should encourage review of details before confirmation

### C) New install

Represents creating a new installation instead of targeting an existing one.

Required behavior:

- always available
- should not require existing-instance metadata
- may require path selection later in the flow

### D) Manual path selection

Represents manually selecting an **existing install target**.

Chosen behavior for this project:

- `Choose path manually` means manual selection of an **existing install target only**
- `New install` remains a separate option and handles its own path selection later

## 5) Normalized Option Object

Each user-facing choice should be produced from a normalized object.

## Required fields

- `optionId`
- `optionType`
  - `existing`
  - `possibleMatch`
  - `new`
  - `manual`
- `title`
- `displayLabel`
- `summary`
- `recommended`
- `isRunning`
- `runtimeKind`
- `confidence`
- `warningLevel`
  - `none`
  - `info`
  - `warning`
- `configPath`
- `workspacePath`
- `installRoot`
- `evidenceSummary`

### Optional fields

- `gatewayPort`
- `gatewayUrl`
- `processInfo`
- `serviceInfo`
- `dockerInfo`
- `notes`
- `warnings`

## 6) Recommended Display Content by Option Type

### Existing detected install

Display:

- title: `Install over existing OpenClaw instance`
- label: specific instance label
- badges: `Recommended` if applicable, plus `Running` or `Not running`
- summary: plain-language explanation
- details:
  - config path
  - workspace path
  - install root
  - runtime kind

### Possible match

Display:

- title: `Possible existing install match`
- badge: `Possible match`
- summary: plain-language warning that this result is less certain
- warning text must be prominent
- details should emphasize why it was matched

### New install

Display:

- title: `Start a new install`
- badge: `New install`
- summary: creates a fresh install path instead of reusing a detected one
- no existing-instance details required

### Manual path selection

Display:

- title: `Choose an existing install path manually`
- badge: `Manual`
- summary: user supplies the install target directly if detection missed it or ambiguity remains

## 7) Sorting Rules

Options should be sorted in this order:

1. recommended existing install
2. other high-confidence existing installs
3. low-confidence possible matches
4. new install
5. manual existing-target selection

Within each section:

- sort by confidence descending
- then by stronger evidence (running process, resolved config, resolved workspace)
- then by deterministic path/name ordering

## 8) Confirmation Flow

The user must explicitly choose an option.

### Recommended behavior

- recommendation is highlighted only
- recommendation is **not auto-selected**
- after selection, a confirmation step should restate the chosen target clearly

### Confirmation output

Once the user confirms, the system must produce one **confirmed selection object** for installer handoff.

## 9) Confirmed Selection Object

This object is produced **after** the user chooses an option.

Required fields:

- `selectionType`
  - `existing`
  - `new`
  - `manual`
- `selectedOptionId`
- `displayLabel`
- `configPath`
- `workspacePath`
- `installRoot`
- `runtimeKind`
- `isRunning`
- `confidence`
- `confirmedByUser`

Rules:

- all installer-used paths must be absolute
- paths must be validated before continuing
- if `selectionType = new`, the terminal flow should collect install root + workspace target paths, derive the planned config path, validate them, and require explicit user confirmation before install begins
- if `selectionType = manual`, the terminal flow should collect an existing config path + workspace path, normalize and validate them, derive install root, and require explicit user confirmation before continuing

## 10) Example Option Set

Example first-choice screen structure:

### Recommended
- Install over existing OpenClaw instance
  - Label: `OpenClaw on D:\openclaw-backup\gateway`
  - Badges: `Recommended`, `Running`
  - Summary: Existing running instance with resolved config and workspace
  - Details:
    - Config: `D:\openclaw-backup\gateway\openclaw.json`
    - Workspace: `D:\openclaw-backup\repo`
    - Runtime: `windows-service`

### Other detected installs
- Install over existing OpenClaw instance
  - Label: `OpenClaw in C:\Users\Sam\.openclaw`
  - Badges: `Not running`
  - Summary: Valid config found; install appears currently stopped

### Possible matches
- Possible existing install match
  - Badges: `Possible match`
  - Summary: Config-like path found but runtime/workspace linkage is incomplete
  - Warning: Review carefully before selecting

### Other options
- Start a new install
- Choose an existing install path manually

## 11) Acceptance Criteria

T2 is complete when:

- the first-choice screen is defined as a **flat, easy-to-scan list**
- detected installs are visually distinct from their detailed metadata
- recommendation is highlighted but not preselected
- `New install` and `Manual existing-target selection` are both available
- low-confidence matches are separated and warning-labelled
- a normalized option object is defined
- a confirmed selection object is defined for installer handoff
- sorting rules are deterministic and recommendation-friendly

## 12) Implications for Existing v3 Artifacts

The current reporting artifacts appear oriented toward technical detection output rather than installer decision objects.

This means later tasks will likely need to:

- preserve the current JSON/report outputs for debugging
- add a new structured **option model output** for installer use
- stop treating report files as the primary runtime handoff

This is expected and consistent with the detector contract.
