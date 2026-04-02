# ResonantOS Installer v3 — Build Status

Status: Active
Last updated: 2026-04-03

---

## Current Checkpoint

Completed foundation work:
- deterministic handoff
- process-first detector improvements
- missing-tool diagnostics
- safer command execution transport
- option model and confirmed selection
- tests passing
- interactive selection flow
- manual/new path completion
- paged flow design/spec work

Recent progress:
- `UX-1` complete: added TTY-aware clear-screen page shell in `installer-entry.js`
- major flow boundaries now render as distinct pages: assessment, target choice, manual/new path entry, and final confirmation
- `UX-2` complete: added a detection intro / waiting page that starts the scan immediately, explains what is being scanned, sets 1–5 minute expectations, and pauses on a scan-complete / press-any-key gate before clearing to results
- `UX-3` complete: suppressed lower-level probe noise by hiding spawned Windows child windows and forcing PowerShell probes into quiet/non-interactive mode so host progress/warning noise does not leak into the installer UI
- `UX-4` complete: zero-detection flow now branches through a dedicated new/existing-user question before any dependency page, with separate follow-on screens for new-user start vs existing-user recovery-first routing
- `UX-5` complete: generic dependency output is now gated behind a dedicated dependency-issues page that only appears for relevant non-Docker issues and is skipped for the new-user zero-detection branch
- `UX-5A` complete: the dependency page now offers explicit one-click non-Docker remediation actions with OS-aware commands, confirmation before execution, Docker exclusion, and assessment rerun after a successful fix
- `UX-6` complete: detected-instance rendering now uses readable boxed cards with prominent resolved labels, grouped details, gateway/evidence summaries, and a separate possible-match section when weaker results exist
- `UX-7` complete: install-target menu labels are now plain-language intent labels that use resolved instance names directly, while the technical detail stays in the cards above
- `UX-8` complete: the primary install-target menu now uses an arrow-key highlight selector with Enter-to-confirm, while typed number / option-id input remains available as a fallback path
- `REC-1` complete by verification: the zero-detection existing-user branch already lands on a recovery-first page, keeps the user out of new-user onboarding, and preserves the direct pivot into a fresh install from the same recovery area
- `REC-2` complete by verification: the manual existing-target recovery path already prompts directly for `openclaw.json`, normalizes/validates it, and rejects obviously bad path input before continuing
- `REC-3` complete: manual recovery now re-runs the detector in directed-config mode using the user-supplied `openclaw.json`, skips wide-scan discovery for that recovery run, and renders a recovered instance card before confirmation when a reusable target is found
- `REC-4` complete by verification: recovery now exposes a wrong-machine / remote-topology escape page, explains that the installer must run on the same host as the target OpenClaw instance, shows a tutorial placeholder, and supports both back and clean exit behavior
- `NEW-1` complete: the new-user branch now enters a dedicated onboarding page for `Recommended install` vs `Custom install`, stores the choice in onboarding state, and carries that state forward with the confirmed new-install selection
- `NEW-2` complete: onboarding state now tracks wizard metadata (`version`, `currentStep`, timestamps, `stepHistory`, invalidation entries) and is snapshotted into the confirmed new-install selection so later pages can build on persistent state cleanly
- `NEW-3` complete: new-user onboarding now runs as a two-step wizard (`install-style`, `docker-choice`) with consistent `Help` / `Back` / `Next` / `Cancel` framing, step summaries, explicit continue behavior, and exported state helpers covered by focused onboarding tests
- `NEW-4` complete: onboarding invalidation now reconciles active vs hidden steps explicitly, clears only dependent downstream choices, removes hidden branches from active step flow, and preserves unrelated state (including provider choices when Docker-only state is turned off)
- `NEW-5` complete by verification: Docker already appears after install-style selection in the new-user wizard, is presented as an explicit optional step, and is explained in plain language before any Docker-specific setup work
- `NEW-5A` complete: Docker-enabled onboarding now enters a dedicated readiness step that probes local Docker availability/readiness, summarizes the detected state in plain language, records the intended Docker action (`install`, `fix-or-update`, or ready), and keeps that remediation logic inside the Docker flow instead of the generic dependency page
- `NEW-5B` complete: the Docker branch is now an interactive setup page with selectable Docker plan modes, intent/progress summaries, and a single explicit confirmation gate before the Docker plan is accepted into onboarding state
- `NEW-6` complete in implementation: onboarding now includes a dedicated paths / ports page with visible defaults, editable install root/workspace/gateway port fields, reset-to-default behavior, and new-install confirmation prefilled from the collected onboarding state instead of forcing a blind re-entry
- `NEW-7` complete: onboarding now includes a setup-agent readiness page that defines installer-side responsibility for model/auth/gateway handoff, records auto vs manual setup-agent intent in onboarding state, and carries the gateway/dashboard handoff details forward into the confirmed selection summary
- `NEW-7A` complete by verification: the readiness page now presents a clear `Auto mode` vs `Manual mode` choice, explains the difference in plain language, and persists the chosen setup-agent sourcing mode into onboarding state
- `NEW-7B` complete: auto mode now creates a structured setup-agent provisioning plan with the small local model profile, explicit provisioning steps, local gateway handoff, and a dashboard welcome summary that downstream review/install phases can display directly
- `NEW-7C` complete: manual mode now branches into explicit provider/model onboarding with API key, OAuth, and curated local model paths, and persists a structured `manualProvisioning` plan that downstream review/install phases can summarize directly
- validation passed: `node --check installer-entry.js`, `node --check detector-cli.js`, `npm test` (13/13), and a focused onboarding smoke harness confirming Manual mode persists a full `manualProvisioning` object for the curated local model path

Primary source docs:
- `FULL-BUILD-SPEC.md`
- `V3-MASTER-SPEC.md`
- `INSTALLER-FLOW-SPEC.md`
- `BUILD-RUNBOOK.md`

---

## Current Priority

**Phase UX — Paged Wizard UX Pass**

The next build work should focus on turning the current functional terminal flow into the paged wizard described in the specs.

Heartbeat mode:
- Active build mode
- 10-minute wake cadence
- heartbeat wakes and re-aligns the build; it does not imply waiting idly between beats
- blocked/test-failure recovery follows the 5x same-error review-code-test loop from `BUILD-RUNBOOK.md`

Current external baseline for dashboard/installer linking:
- `https://github.com/ResonantOS/resonantos-alpha` branch `experimental/v0.6.0-linux-safe-bringup-20260402`
- prefer the repo-local install contract at `install/INSTALL_SPEC.yaml` over older branch assumptions

---

## Ordered Next Tasks

1. `UX-1` — Clear-screen page shell
2. `UX-2` — Detection intro / waiting page
3. `UX-3` — Suppress noisy probe output
4. `UX-4` — Branch ordering fix
5. `UX-5` — Dependency issues page gating
6. `UX-5A` — Non-Docker dependency remediation actions
7. `UX-6` — Detected instance card renderer
8. `UX-7` — Simple install intent menu
9. `UX-8` — Arrow-key selector
10. `REC-1` — Zero-detection existing-user recovery entry
11. `REC-2` — Directed openclaw.json prompt
12. `REC-3` — Targeted single-location detection
13. `REC-4` — Wrong-machine / remote-topology escape page
14. `NEW-1` — Recommended vs Custom page
15. `NEW-2` — Wizard state model
16. `NEW-3` — Help / Back / Next navigation
17. `NEW-4` — Dependent-state invalidation
18. `NEW-5` — Docker later in the flow
19. `NEW-5A` — Docker install/update check
20. `NEW-5B` — Interactive Docker setup page
21. `NEW-6` — Paths / ports onboarding page
22. `NEW-7` — OpenClaw / setup-agent readiness page
23. `NEW-7A` — Agent mode choice
24. `NEW-7B` — Auto mode provisioning
25. `NEW-7C` — Manual mode provider/model onboarding
26. `REV-1` — Review page
27. `REV-2` — Install-phase prep contract
28. `REV-3` — Dashboard landing contract
29. `CLN-1` — Remove residual rough edges
30. `CLN-2` — Align docs and tests
31. `CLN-3` — Final polish pass

---

## Current Next Action

**Next task: `REV-1`**

Build the clean final review page summarizing install mode, target, Docker, paths/ports, and setup-agent readiness.

Success criteria:
- review page is clear and compact
- all major decisions are shown together
- user can verify install-ready state before the later execution phase

---

## Known Open Items

- wrong-machine tutorial URL is still a placeholder
- exact Docker management wording/details still need refinement beyond the interactive page model
- setup-agent provisioning details still need to be nailed down fully
- exact browser-launch/dashboard-handshake mechanics still need implementation detail, although the desired end-state is now locked
- curated model list for manual setup-agent mode still needs definition
- exact ResonantOS-installed detection heuristics/status display still need implementation detail
- future repair-installation path is deferred, but the detection/status groundwork should support it later
- final card/selector visual style is not final

Visual priority:
- function first
- best-effort polish second

---

## Blocker Log

- none recorded yet

---

## Update Rules

When work advances:
- mark completed tasks here
- set the next unblocked task as `Current Next Action`
- if blocked, add the blocker under `Blocker Log`
- user-facing heartbeat/build updates should cite the task id from `BUILD-RUNBOOK.md`
