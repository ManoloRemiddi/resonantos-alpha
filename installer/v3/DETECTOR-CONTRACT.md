# Detector Contract Spec

Status: Draft v0.1
Scope: ResonantOS Installer / OpenClaw detection assessment
Location: `installer/v3`

## 1) Purpose

The detector exists to:

- identify existing OpenClaw / ResonantOS install candidates
- identify whether each discovered OpenClaw instance already has ResonantOS installed
- turn those findings into a set of install options for the user
- allow the user to confirm the correct target
- pass a confirmed, structured handoff object with absolute paths into the installer

The detector does **not** exist primarily to generate JSON files.

## 2) Primary Source of Truth

The canonical output of the detector is a **structured object returned to the installer**.

Supporting outputs are secondary:

- JSON output = debug / reporting artifact
- Markdown / terminal output = human-readable operator output

The installer must consume the structured result, **not** scrape report files.

## 3) Detection Strategy

### Preferred strategy

- **Process-first detection** is the primary path.
- If a live process is found, the detector should try to resolve the instance/config from that process first.
- Filesystem search is a **bounded fallback**, not the main strategy.

### Non-running installs

If no live process is found, the detector may still surface a candidate when valid config / workspace / install evidence exists.

Reasoning:

- a user may have intentionally disabled or stopped the system during install prep
- “not running” does **not** mean “not a valid install target”

## 4) Candidate Classes

The detector may classify findings into these classes:

- **Running, high-confidence instance**
- **Not-running, high-confidence instance**
- **Low-confidence possible match**
- **Manual/custom path option**

## 5) User-Facing Option Behavior

The detector must support producing these installer options:

- install over existing instance
- install over another detected instance
- start a new install
- choose path manually

### Manual/custom option

The manual/custom path option must always be available.

## 6) Low-Confidence Handling

Low-confidence detections should still be surfaced, but they must be handled separately:

- shown in a dedicated **possible matches** section
- clearly marked with warnings
- not visually mixed with strong/recommended candidates

## 7) Recommendation Behavior

- candidates should be ranked
- one candidate may be marked **recommended** when the evidence justifies it
- all viable options must still be shown
- recommendation is advisory only
- user confirmation is authoritative

## 8) Confirmed Selection Handoff

After the user selects and confirms an option, the system must produce **one confirmed handoff object** for the installer.

### Balanced handoff payload

Required fields:

- `selectionType`
  - `existing`
  - `new`
  - `manual`
- `displayLabel`
- `configPath`
- `workspacePath`
- `installRoot`
- `runtimeKind`
- `isRunning`
- `confidence`

### Path rules

- any path handed into the installer must be **absolute**
- destructive or install-targeting actions must use **confirmed paths only**
- for `new` installs, fields may begin null/omitted at option-selection time, but the installer entry flow must collect and confirm the target install root/workspace paths before proceeding
- for `manual` existing-target selection, the installer entry flow must collect and confirm the user-supplied config/workspace paths before proceeding
- the installer must not proceed until all required target paths are confirmed

## 9) What the Installer May Trust

The installer may trust:

- the confirmed handoff object
- absolute paths inside that confirmed object
- the selected option type
- runtime classification and confidence as advisory metadata

The installer must **not** rely on:

- “latest JSON file in a folder” logic
- raw detector reports as authoritative state
- ambiguous or unconfirmed candidate paths

## 10) Non-Goals

The detector is not trying to:

- be a giant general-purpose inventory system
- preserve every weak signal as first-class output
- force the installer to interpret raw technical reports
- replace user confirmation where ambiguity exists

## 11) Acceptance Criteria

This contract is satisfied when:

- detector output is used for **installer decision support**
- the installer consumes a **structured object**, not report files
- **manual/custom path** is always available
- **low-confidence** matches are shown separately with warnings
- **not-running but valid** installs may still be offered
- all installer-used paths are **absolute and confirmed**
- one candidate may be **recommended**, but user choice wins

## 12) Notes for Follow-On Tasks

This contract intentionally leaves open the exact shape of:

- the installer option model
- the display model for recommendations / warnings
- the final UX flow for manual path selection

Those decisions belong to **T2 — Installer Option Model**.
