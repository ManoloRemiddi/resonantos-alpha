# V3 Changeset Summary (built from V2 learnings)

Date: 2026-04-01
Base: `versions/v2/detector-cli.js`
Output: `versions/v3/detector-cli.js`

## Inputs reviewed
- `v2/reports/REVIEW-V2-LOGIC-SECURITY-20260401-154900.md`
- `v2/reports/REVIEW-PLAN-V2-LOGIC-SECURITY-20260401-154900.md`
- `v2/reports/TEST-REPORT-V2-LINUX-20260401-162758.md`
- `v2/reports/V2-WINDOWS-DETECTOR-RUN-2026-04-01T16-18-36.md`
- Prior reviewer/test summaries in `v2/`

## Implemented in v3
1. **Instance formatting upgraded**
   - Adds per-instance fields:
     - `instanceName` (from `workspace/IDENTITY.md` when discoverable)
     - `runtimeType`
     - `openclawConfigPath`
     - `workspacePath`
     - `identityPath`
     - `identityNameExtracted`
     - gateway details (`wsUrl`, `dashboardPort`, `gatewayMode`)
     - `confidence`

2. **Config → workspace → identity linking**
   - Normalizes config values
   - Resolves `workspacePath`
   - Reads `IDENTITY.md` and extracts `Name:` where present

3. **Dependency minimum gates added**
   - Node minimum gate: `>=22.0.0`
   - Python minimum gate: `>=3.10.0`
   - Includes `git`, `ffmpeg`, `docker` presence/status
   - Reports `status`, `minimumRequired`, and `impact`

4. **Readiness mismatch bug fixed**
   - Readiness checks now use normalized top-level fields (`wsUrl`, `dashboardPort`)
   - No mixed nested-shape dependency

5. **Windows capability improvements**
   - Service model signal retained
   - Docker Desktop bridge uses TCP probe (`Test-NetConnection`) instead of ICMP ping
   - Start Menu capability remains explicit

6. **Service-account user-profile probing hardening**
   - Windows systemprofile lane includes `C:\Users\*` candidate probing
   - Excludes `Public`, `Default*`, `All Users`

7. **Operational safety**
   - Script remains read-only
   - Docker checks have short timeouts to reduce hangs

## Artifacts generated
- `v3/reports/install-detect-2026-04-01T03-36-08-599Z.json`
- `v3/reports/install-detect-2026-04-01T03-36-08-599Z.md`

## Next validation
- Run Linux tester + Windows host run against `versions/v3`
- Compare:
  - start-case correctness
  - attach-readiness correctness
  - identity name resolution quality
  - dependency gate behavior (Node/Python minimums)
