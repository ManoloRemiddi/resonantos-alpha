# ResonantOS Installer v3 — Start Here

This starts the installer entrypoint and runs the **detection assessment** first.

> Repo status: this installer is now vendored into the ResonantOS repo and wired to the current Linux-safe experimental branch.
>
> Scope status: the wizard is **real and tested**, but it is still **pre-install / read-only by default**. It confirms the target, gathers onboarding choices, and writes a deterministic handoff for the later execution phase.

## 1) Prerequisite
Install Node.js (v22+ recommended).

Check:

```bash
node -v
```

---

## 2) Run it from the repo root (recommended)

### Linux/macOS

```bash
cd /path/to/resonantos-alpha
./scripts/run-installer-v3.sh
```

### Windows

```powershell
cd <path to>\resonantos-alpha\installer\v3
node .\installer-entry.js
```

---

## 3) Run it directly from the installer folder

### Linux/macOS

```bash
cd /path/to/resonantos-alpha/installer/v3
npm start
```

### Windows

```powershell
cd <path to>\resonantos-alpha\installer\v3
node .\installer-entry.js
```

---

## 4) Where results go
When run through `installer-entry.js`, the detector writes:

- `reports/human-run/latest-handoff.json` — deterministic installer handoff for that run
- `reports/human-run/install-detect-*.json` — timestamped debug/report artifacts

The terminal output is the human-readable assessment. The later execution phase should use the handoff object, not "latest JSON in folder" logic.

Generated runtime report folders are intentionally git-ignored in the vendored repo copy.

---

## 5) What this does right now
- Detects OpenClaw/ResonantOS-related install signals
- Checks key dependencies and minimum gates
- Produces a readable assessment report
- Shows an interactive terminal selection flow
- Lets you choose one option by number or by `optionId`
- Re-runs detector handoff generation with your chosen `--select-option-id`
- Collects onboarding choices for Docker, paths/ports, and setup-agent readiness
- Ends on a compact final review page before the later mutation/install phase

### Current selection behavior
- Recommended options are highlighted, but not auto-selected
- Existing installs are shown with a dedicated details block so they stand out from generic options
- `Choose an existing install path manually` prompts for:
  - existing `openclaw.json` path (or its containing folder)
  - existing workspace path
  - validation + explicit confirmation before continuing
- `Start a new install` prompts for:
  - new install root path
  - new workspace path
  - validation + explicit confirmation before continuing
- New-install path confirmation checks that the planned `config/openclaw.json` does not already exist at that target
- The detector-produced confirmed selection remains the canonical handoff baseline for the later execution phase

## 6) Current branch contract
For this vendored copy, the installer should treat the following as authoritative:

- repo install contract: `install/INSTALL_SPEC.yaml`
- human-facing install guide: `INSTALL.md`
- current baseline branch: `experimental/v0.6.0-linux-safe-bringup-20260402`

If those docs and the installer assumptions disagree, prefer the repo-local install contract and update the installer docs/code instead of improvising.
