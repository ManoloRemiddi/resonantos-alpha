# V3 Pseudocode Diff Plan (for review)

Date: 2026-04-01
Scope: Consolidate all V3 report findings into a single implementation plan
Sources reviewed:
- `TEST-RESULTS-REVIEW-V3-20260401-204602.md`
- `V3-DETECTOR-LOCAL-INSTANCES-REPORT-2026-04-01T18-46-43.md`
- `OPENCLAW-INSTANCE-OUTPUT-FORMAT.md`
- `targeted-commands-local-instances.md`

Status target after patch: **GREEN candidate**

---

## 0) High-Level Objectives

1. Keep installer entry output concise and human-safe.
2. Improve instance detection fidelity in mixed topologies (service + user + docker).
3. Remove sensitive data exposure from persisted artifacts.
4. Make detection behavior bounded and low-risk by default.
5. Align display/output with desired `Openclaw Instance` block format.

---

## 1) Proposed Module-Level Diffs

## A. `installer-entry.js` (user UX + default safety)

### Current issues
- Historically noisy output and repeated headings.
- Deep mode used by default in some flows (EDR risk, unnecessary scan cost).

### Pseudocode diff
```pseudo
function runInstallerEntry():
  clearScreen()
  print "ResonantOS Installer — System Assessment"

  mode = "targeted"   // default
  args = ["--quiet", "--json-only", "--mode", mode, "--out-dir", reportsDir]

  run detector-cli.js with args
  if failed -> show concise error + exit

  latestJson = loadNewestJson(reportsDir)
  summary = buildHumanSummary(latestJson)
  print summary only
```

### Acceptance
- No raw probe chatter shown to user.
- No deep scan by default.
- Single concise assessment view.

---

## B. `detector-cli.js` (core detection hardening)

### B1) Process/service data redaction (HIGH)

#### Current issue
- Full process command lines can be persisted in JSON.

#### Pseudocode diff
```pseudo
function sanitizeProcess(process):
  exe = extractExecutableName(process.commandLine)
  pid = process.pid
  roleHint = inferRoleHintFromCommand(process.commandLine)  // gateway/main/unknown
  return { pid, exe, roleHint }

function collectProcesses(debug=false):
  raw = probeProcesses()
  if debug:
    return raw
  else:
    return map sanitizeProcess(raw)
```

#### Acceptance
- Default JSON contains no raw command args/tokens.
- Optional debug mode can preserve full detail explicitly.

---

### B2) Detection mode control + bounded scans (HIGH)

#### Current issue
- Deep scan can be overused; potential endpoint tooling concern.

#### Pseudocode diff
```pseudo
args:
  --mode targeted|deep   // default targeted
  --debug                // opt-in extra telemetry

function collectConfigCandidates(mode, runtimeSignals):
  base = knownStandardPathsByOS()
  targeted = deriveFromSignals(runtimeSignals)

  if mode == "targeted":
    return dedupe(base + targeted)

  if mode == "deep":
    deepHits = boundedDeepSearch(limitPaths=200, maxDepth=..., timeout=...)
    return dedupe(base + targeted + deepHits)
```

#### Acceptance
- Targeted mode default.
- Deep only when requested.
- Bounded recursion and timeouts.

---

### B3) Runtime classification scoring by instance (MEDIUM)

#### Current issue
- Global service presence can over-label all instances as service.

#### Pseudocode diff
```pseudo
function classifyInstanceRuntime(instance, evidence):
  score = {
    windows_service: 0,
    windows_user: 0,
    docker_container: 0,
    linux_systemd: 0,
    manual_process: 0
  }

  if servicePathNear(instance.configPath): score.windows_service += 5
  if processPathNear(instance.configPath): score.windows_user += 3
  if dockerMountContains(instance.configPath): score.docker_container += 6
  if systemdUnitReferences(instance.configPath): score.linux_systemd += 5
  if processOnlySignal(instance): score.manual_process += 2

  runtimeType = maxScore(score)
  confidence = scoreToConfidence(score)
  return { runtimeType, confidence, evidenceUsed }
```

#### Acceptance
- Mixed environments classify per-instance, not globally.

---

### B4) Start-case precedence refinement (MEDIUM)

#### Current issue
- Docker presence may dominate even when host service is primary.

#### Pseudocode diff
```pseudo
function classifyStartCase(instances):
  attachable = filter instances where confidence != blocked and hasConfig

  if attachable.empty:
    return new_openclaw

  // precedence by attachability confidence, not presence only
  if any attachable runtimeType == windows_service or linux_systemd:
    return existing_openclaw_service_account

  if any attachable runtimeType == windows_user or manual_process:
    return existing_openclaw_user_account

  if any attachable runtimeType == docker_container:
    return existing_openclaw_in_docker

  return existing_openclaw_user_account
```

#### Acceptance
- Branch recommendation matches primary actionable instance.

---

### B5) De-dupe strategy hardening (MEDIUM)

#### Current issue
- Null-heavy keys can collapse unrelated instances.

#### Pseudocode diff
```pseudo
function canonicalConfigKey(path):
  if windows:
    return normalizeCase(path)
      |> removeKnownSuffixVariants([
         "\\config\\openclaw.json",
         "\\.openclaw\\openclaw.json",
         "\\openclaw.json"
      ])
  else:
    return normalizePosix(path)

function dedupeInstances(instances):
  key =
    if hasConfigPath -> canonicalConfigKey(configPath)
    else if hasWorkspace -> normalize(workspacePath)
    else -> runtimeType + ":" + gatewayPort + ":" + instanceName + ":" + sourceEvidenceHash

  merge duplicates by confidence/evidence priority
```

#### Acceptance
- ProgramData variants collapse correctly.
- Distinct instances remain distinct.

---

### B6) Integrate targeted process→config resolver (HIGH)

#### Current issue
- Process-detected instances (e.g., backup gateway) may miss config path linkage.

#### Pseudocode diff
```pseudo
function resolveConfigFromProcess(process):
  roots = extractCandidateRoots(process)
  candidates = boundedSearchFor("openclaw.json", roots, depth<=4, perRootLimit<=20)
  ranked = rankCandidatesByProximityAndName(candidates, process)
  return ranked.firstOrNull

function enrichInstancesFromProcesses(processes, existingInstances):
  for process in processes:
    cfg = resolveConfigFromProcess(process)
    if cfg exists and not represented(existingInstances, cfg):
      add synthetic instance record from cfg + process evidence
```

#### Acceptance
- Backup/user gateway discovered with config linkage when running.

---

### B7) Windows capability label handling (LOW)

#### Current issue
- `Test-NetConnection` concept can feel alarming if visible.

#### Pseudocode diff
```pseudo
function computeWindowsCapabilities():
  dockerBridgeCheck = runInternalTCPProbe("host.docker.internal", port)
  persist in JSON as internal capability

function humanSummary(report):
  do not print dockerBridgeCheck in default mode
  if --verbose-user:
    print "Docker Container Bridge Check (internal): reachable|not reachable"
```

#### Acceptance
- No unsettling network probe text in default user console.

---

### B8) Output formatting alignment (HIGH)

#### Required format
```
Openclaw Instance:
InstanceName: <name>
RuntimeType: <runtime>
Config: <path>
Workspace: <path|n/a>
Gateway:<port> (<health>)
ResonantOS: <Installed|Not Installed|Unknown>
```

#### Pseudocode diff
```pseudo
function renderUserInstanceBlock(instance):
  print "Openclaw Instance:"
  print "InstanceName: " + (instance.name or "Unknown")
  print "RuntimeType: " + instance.runtimeTypeHuman
  print "Config: " + instance.configPath
  print "Workspace: " + (instance.workspacePath or "n/a")
  print "Gateway:" + (instance.gatewayPort or "n/a") + " (" + instance.gatewayHealth + ")"
  print "ResonantOS: " + instance.resonantOsState
```

#### Acceptance
- User console follows specified format exactly.

---

### B9) Gateway health check addition (SHOULD)

#### Current gap
- Port shown, but health status not consistently shown as `200 OK`/error.

#### Pseudocode diff
```pseudo
function probeGatewayHealth(instance):
  port = instance.dashboardPort or inferredGatewayPort
  endpoints = ["/health", "/status", "/"]
  for ep in endpoints:
    res = httpGet("http://127.0.0.1:" + port + ep, timeout=1200ms)
    if res.success:
      return res.statusCode + " " + res.statusText
  return "unreachable/timeout"
```

#### Acceptance
- Every printed instance has gateway health string.

---

### B10) ResonantOS presence signal (SHOULD)

#### Current gap
- ResonantOS field sometimes unknown without explicit logic.

#### Pseudocode diff
```pseudo
function detectResonantOs(instance):
  workspace = instance.workspacePath
  if workspace and exists(workspace + "/projects/ResonantOS Installer"):
    return "Installed"
  if dockerMountHasResonantMarker(instance):
    return "Installed"
  if confidentNoSignal:
    return "Not Installed"
  return "Unknown"
```

#### Acceptance
- Field present for each instance.

---

## C. `tester/run-detector-tests.js` (semantic quality gates)

### Current issue
- Structural pass can hide semantic failures.

### Pseudocode diff
```pseudo
test "windows semantic gates":
  assert environment.executionContext exists
  assert environment.profileScope exists
  assert no linux path leakage in windows targeted candidates
  assert windowsCapabilities block exists
  assert no raw process command lines in non-debug output
  assert dedupe does not collapse distinct known instances

if critical semantic gate fails:
  status = FAIL
```

### Acceptance
- `ok_with_gaps` cannot pass if critical semantics fail.

---

## 2) Data Model Diff (JSON)

## Add / refine fields
```pseudo
report = {
  mode: "targeted|deep",
  debug: boolean,
  instances: [{
    instanceName,
    runtimeType,
    confidence,
    configPath,
    workspacePath,
    gatewayPort,
    gatewayHealth,
    resonantOsState,
    evidence: [...],
  }],
  capabilities: {
    windows: {
      serviceModel,
      dockerBridgeInternal,
      startMenuIntegration
    }
  }
}
```

## Remove / gate
```pseudo
report.processes.rawCommandLine   // remove by default
```

---

## 3) Patch Sequence (recommended order)

1. Add mode defaults (`targeted`), quiet UX, and process redaction.
2. Integrate process→config resolver.
3. Improve dedupe and runtime scoring.
4. Add gateway health and ResonantOS state.
5. Align user output block format.
6. Upgrade tester semantic assertions.
7. Re-run Linux + Windows tests and publish updated reports.

---

## 4) Review Checklist for this Diff Plan

- [ ] No sensitive command args persisted by default.
- [ ] Targeted mode is default; deep is explicit.
- [ ] Three local instance topology can be represented without collapse.
- [ ] Runtime and start-case decisions are evidence-based.
- [ ] User output format matches requested block style.
- [ ] Tester can fail critical semantic regressions.

---

## 5) Expected Outcome

After applying this plan, V3 should move from **YELLOW+** to **GREEN-candidate** for detector phase handoff, with safer defaults, clearer operator UX, and stronger instance fidelity in real Windows mixed deployments.
