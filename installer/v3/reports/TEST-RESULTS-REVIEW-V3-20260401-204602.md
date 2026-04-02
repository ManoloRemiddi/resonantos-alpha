# Test Results Review — V3 Detector (Comprehensive)

Status: **YELLOW+** (strong progress, not final-green)
Reviewer: Helm
Date: 2026-04-01
Scope: Logic correctness, cross-platform command hygiene, and security/endpoint-risk posture

## Executive Summary
V3 is a substantial upgrade over V2. The architecture is cleaner, readiness logic is improved, Windows service-account detection is better, and capability probing is more practical. However, several issues remain that should be resolved before release-grade confidence: report data exposure risk, overly noisy default deep scanning, and a few classification/deduping edge-case misclassifications.

## What’s Working Well
1. **Code quality baseline is healthy**
   - `detector-cli.js`, `installer-entry.js`, and helper scripts parse cleanly.
2. **Readiness path improved**
   - V2 readiness field-shape mismatch has been corrected.
3. **Windows lane maturity increased**
   - Better handling of service-account/systemprofile context.
   - Docker Desktop bridge check moved to TCP-style probing.
4. **Dependency gates are clearer**
   - Node/Python minimum gate reporting is explicit and actionable.
5. **Instance enrichment is useful**
   - Config → workspace → IDENTITY linking materially improves operator visibility.

## Findings (Must/Should Fix)

### A) Security / data-handling concern (HIGH)
**Issue:** Full process command lines are persisted in output JSON (`processes` array).  
**Risk:** Sensitive args/tokens/paths may be captured and retained in artifacts.  
**Action:** Redact command arguments before persistence (store executable + selected normalized flags only), or gate raw process capture behind explicit debug mode.

### B) Operational/EDR risk posture (HIGH)
**Issue:** `installer-entry.js` defaults to `--deep` scanning on every human run.  
**Risk:** On enterprise endpoints this can look like aggressive recon and trigger endpoint tooling alerts.  
**Action:** Make targeted mode default; require explicit opt-in for deep mode.

### C) Runtime classification accuracy (MEDIUM)
**Issue:** `inferRuntimeType()` can over-label as `windows_service` based on global service presence and path pattern assumptions.  
**Risk:** Misclassification of mixed environments (service + manual + container side by side).  
**Action:** Make runtime-type scoring instance-local with evidence weighting.

### D) Dedupe key fragility (MEDIUM)
**Issue:** Dedupe key uses `workspace|port|name`; null-heavy records can collapse unrelated instances.  
**Risk:** Distinct installs merged into one, losing fidelity.  
**Action:** Add stable fallback dimensions (e.g., normalized config-root family or canonical config path score bucket).

### E) Start-case precedence in mixed topologies (MEDIUM)
**Issue:** Docker presence can dominate classification even when host service is primary.  
**Risk:** Wrong installer branch suggestion.  
**Action:** Use confidence-based precedence (attachability evidence > mere presence).

### F) Start Menu capability optimism (LOW)
**Issue:** Windows start-menu support reported as universally available.  
**Risk:** False positives in constrained/service contexts.  
**Action:** Verify writable/accessible Start Menu target path before reporting “available”.

## Firewall / Security Tooling Assessment
- **Not inherently a firewall/TOS violation** on Windows/Linux.
- Main concern is **behavioral detection** by Defender/EDR (especially broad scans and verbose process harvesting).
- V3 remains defensible as installer preflight if scans remain bounded, explainable, and minimally invasive.

## Recommended Release Gate (for GREEN)
1. Redact process command lines in persisted reports.
2. Change default run mode to targeted (non-deep).
3. Tighten runtime classification and mixed-topology start-case precedence.
4. Harden dedupe key for null/unknown identity cases.
5. Add semantic tests for the above (not just structural JSON checks).

## Verdict
Do not mark V3 final-green yet. Approve for another patch cycle with focused hardening.
