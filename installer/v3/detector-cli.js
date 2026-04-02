#!/usr/bin/env node
/*
  ResonantOS/OpenClaw Detector - v3
  - Read-only
  - Cross-platform lanes (Windows-first aware)
  - Config -> workspace -> IDENTITY name linking
  - Dependency minimum gates
*/

const fs = require('fs');
const os = require('os');
const path = require('path');
const { spawnSync } = require('child_process');

const PLATFORM = process.platform;
const probeDiagnostics = [];

function inferCommandName(cmd) {
  const raw = String(cmd || '').trim();
  if (!raw) return null;
  const m = raw.match(/^([A-Za-z0-9_.:\/\\-]+)/);
  return m ? path.basename(m[1]).toLowerCase() : null;
}

function isMissingCommandResult(cmd, errorText) {
  const text = String(errorText || '').toLowerCase();
  const name = inferCommandName(cmd);
  if (!text) return false;
  if (text.includes('command not found')) return true;
  if (text.includes('is not recognized as an internal or external command')) return true;
  if (text.includes('enoent')) return true;
  return Boolean(name && text.includes(`${name}: not found`));
}

function recordProbeDiagnostic(diag) {
  const normalized = {
    severity: diag?.severity || 'info',
    area: diag?.area || 'general',
    tool: diag?.tool || null,
    message: diag?.message || '',
    command: diag?.command || null,
    detail: diag?.detail || null,
  };
  const key = JSON.stringify(normalized);
  if (!probeDiagnostics.some(existing => JSON.stringify(existing) === key)) probeDiagnostics.push(normalized);
}

function formatCommandForDiagnostics(command, args = []) {
  return [command, ...args].map(part => {
    const text = String(part ?? '');
    return /[\s"'`]/.test(text) ? JSON.stringify(text) : text;
  }).join(' ');
}

function run(command, args = [], timeout = 6000, meta = {}) {
  const commandText = Array.isArray(args)
    ? formatCommandForDiagnostics(command, args)
    : String(command || '');
  const spawnArgs = Array.isArray(args) ? args : [];

  try {
    const result = spawnSync(command, spawnArgs, {
      stdio: ['ignore', 'pipe', 'pipe'],
      encoding: 'utf8',
      timeout,
      shell: false,
      windowsHide: true,
    });

    return {
      ok: result.status === 0,
      out: String(result.stdout || '').trim(),
      err: String(result.stderr || '').trim(),
    };
  } catch (e) {
    const result = {
      ok: false,
      out: String(e.stdout || '').trim(),
      err: String(e.stderr || e.message || '').trim(),
    };

    if (meta.recordMissingTool !== false && isMissingCommandResult(commandText, result.err)) {
      recordProbeDiagnostic({
        severity: 'warning',
        area: meta.area || 'command_probe',
        tool: meta.tool || inferCommandName(commandText),
        message: meta.missingToolMessage || `Required external command unavailable: ${meta.tool || inferCommandName(commandText) || 'unknown'}`,
        command: commandText,
        detail: result.err || null,
      });
    }

    return result;
  }
}

function runPwsh(ps, meta = {}) {
  const powershellExe = process.env.ComSpec && PLATFORM === 'win32' ? 'powershell.exe' : 'powershell';
  const quietPrelude = [
    "$ProgressPreference='SilentlyContinue'",
    "$InformationPreference='SilentlyContinue'",
    "$WarningPreference='SilentlyContinue'",
  ].join('; ');
  const wrapped = `${quietPrelude}; ${ps}`;

  return run(powershellExe, ['-NoLogo', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-Command', wrapped], 8000, {
    area: meta.area || 'powershell_probe',
    tool: meta.tool || 'powershell',
    missingToolMessage: meta.missingToolMessage || 'PowerShell is required for this Windows probe but was not available.',
    ...meta,
  });
}

function exists(p) { try { fs.accessSync(p); return true; } catch { return false; } }
function canRead(p) { try { fs.accessSync(p, fs.constants.R_OK); return true; } catch { return false; } }
function canWrite(p) { try { fs.accessSync(p, fs.constants.W_OK); return true; } catch { return false; } }

function stripLeadingBom(text) {
  return typeof text === 'string' && text.charCodeAt(0) === 0xFEFF ? text.slice(1) : text;
}

function decodeUtf16Be(buffer) {
  const swapped = Buffer.alloc(buffer.length - (buffer.length % 2));
  for (let i = 0; i < swapped.length; i += 2) {
    swapped[i] = buffer[i + 1];
    swapped[i + 1] = buffer[i];
  }
  return swapped.toString('utf16le');
}

function readTextAuto(p) {
  const buf = fs.readFileSync(p);
  if (!buf || !buf.length) return '';
  if (buf.length >= 2 && buf[0] === 0xFF && buf[1] === 0xFE) return stripLeadingBom(buf.slice(2).toString('utf16le'));
  if (buf.length >= 2 && buf[0] === 0xFE && buf[1] === 0xFF) return stripLeadingBom(decodeUtf16Be(buf.slice(2)));
  return stripLeadingBom(buf.toString('utf8'));
}

function safeJson(p) {
  try {
    return JSON.parse(readTextAuto(p));
  } catch {
    return null;
  }
}

function parseArgs(argv) {
  const outDirIdx = argv.indexOf('--out-dir');
  const handoffIdx = argv.indexOf('--handoff-file');
  const selectOptionIdx = argv.indexOf('--select-option-id');
  const targetConfigIdx = argv.indexOf('--target-config-path');
  const outDirValue = outDirIdx >= 0 && argv[outDirIdx + 1] ? argv[outDirIdx + 1] : path.resolve(process.cwd(), 'detector-output');
  const handoffValue = handoffIdx >= 0 && argv[handoffIdx + 1] ? argv[handoffIdx + 1] : null;
  const selectedOptionId = selectOptionIdx >= 0 && argv[selectOptionIdx + 1] ? String(argv[selectOptionIdx + 1]).trim() : null;
  const targetConfigValue = targetConfigIdx >= 0 && argv[targetConfigIdx + 1] ? String(argv[targetConfigIdx + 1]).trim() : null;
  return {
    deep: argv.includes('--deep'),
    consoleOnly: argv.includes('--console-only'),
    quiet: argv.includes('--quiet'),
    jsonOnly: argv.includes('--json-only'),
    userSummary: argv.includes('--user-summary'),
    debugReport: argv.includes('--debug-report'),
    outDir: path.resolve(outDirValue),
    handoffFile: handoffValue ? path.resolve(handoffValue) : null,
    selectedOptionId: selectedOptionId || null,
    targetConfigPath: targetConfigValue ? path.resolve(targetConfigValue) : null,
  };
}

function parseSemver(v) {
  const m = String(v || '').match(/(\d+)\.(\d+)\.(\d+)/);
  return m ? [Number(m[1]), Number(m[2]), Number(m[3])] : null;
}

function gte(a, b) {
  if (!a || !b) return false;
  for (let i = 0; i < 3; i++) {
    if (a[i] > b[i]) return true;
    if (a[i] < b[i]) return false;
  }
  return true;
}

function envContext() {
  const ctx = {
    os: PLATFORM === 'win32' ? 'windows' : PLATFORM === 'darwin' ? 'macos' : 'linux',
    arch: process.arch,
    hostname: os.hostname(),
    runtimeContext: exists('/.dockerenv') ? 'container' : 'host',
    user: os.userInfo().username,
    executionContext: 'user',
    profileScope: 'current_user',
  };

  if (PLATFORM === 'win32') {
    const user = runPwsh('[Environment]::UserName');
    if (user.ok && user.out) ctx.user = user.out;
    const up = process.env.USERPROFILE || '';
    if (/system32\\config\\systemprofile/i.test(up) || /^system$/i.test(ctx.user)) {
      ctx.executionContext = 'service_account';
      ctx.profileScope = 'systemprofile';
    }
  }

  return ctx;
}

function dependencyReport() {
  const node = run('node', ['-v']);
  const py = PLATFORM === 'win32' ? run('py', ['-V']) : run('python3', ['-V']);
  const git = run('git', ['--version']);
  const ffmpeg = run('ffmpeg', ['-version']);
  const docker = run('docker', ['--version']);
  const dockerInfo = docker.ok ? run('docker', ['info', '--format', '{{json .}}'], 5000) : { ok: false };

  const deps = {
    node: { detected: node.ok, version: node.ok ? node.out : null, minimumRequired: '22.0.0' },
    python: { detected: py.ok, version: py.ok ? py.out.replace('Python ', '') : null, minimumRequired: '3.10.0' },
    git: { detected: git.ok, version: git.ok ? git.out.replace('git version ', '') : null, minimumRequired: null },
    ffmpeg: { detected: ffmpeg.ok, version: ffmpeg.ok ? (ffmpeg.out.split('\n')[0] || '').replace('ffmpeg version ', '') : null, minimumRequired: null },
    docker: { detected: docker.ok, version: docker.ok ? docker.out : null, minimumRequired: null, running: dockerInfo.ok },
  };

  for (const [k, d] of Object.entries(deps)) {
    if (!d.detected) {
      d.status = k === 'node' ? 'fail' : 'missing';
      d.impact = k === 'node' ? 'Install blocked (required)' : 'May block some install paths';
      continue;
    }
    if (d.minimumRequired) {
      const have = parseSemver(d.version);
      const need = parseSemver(d.minimumRequired);
      const ok = gte(have, need);
      d.status = ok ? 'pass' : 'fail';
      d.impact = ok ? 'OK' : `Minimum ${d.minimumRequired} required`;
    } else {
      d.status = 'pass';
      d.impact = 'OK';
    }
  }

  return deps;
}

function windowsUserProfilesCandidates() {
  const out = [];
  const usersRoot = 'C:\\Users';
  if (!exists(usersRoot)) return out;
  const r = runPwsh("Get-ChildItem 'C:\\Users' -Directory -ErrorAction SilentlyContinue | Select-Object -Expand FullName");
  if (!r.ok || !r.out) return out;
  const exclude = new Set(['public', 'default', 'default user', 'all users']);
  for (const dir of r.out.split(/\r?\n/).filter(Boolean)) {
    const name = path.basename(dir).toLowerCase();
    if (exclude.has(name)) continue;
    out.push(path.join(dir, '.openclaw', 'openclaw.json'));
    out.push(path.join(dir, 'AppData', 'Roaming', 'openclaw', 'openclaw.json'));
    out.push(path.join(dir, 'AppData', 'Local', 'openclaw', 'openclaw.json'));
  }
  return out;
}

function probeWhereOpenclaw() {
  if (PLATFORM !== 'win32') return [];
  const r = run('where.exe', ['openclaw'], 6000, {
    area: 'path_probe',
    tool: 'where.exe',
    missingToolMessage: 'Windows PATH probe skipped because where.exe was not available.',
  });
  if (!r.ok || !r.out) return [];
  return r.out.split(/\r?\n/).map(x => x.trim()).filter(Boolean);
}

function extractWindowsSignalRoots({ whereHits = [], services = [], processes = [] }) {
  const roots = new Set();
  const addPath = (p) => {
    if (!p) return;
    const cleaned = String(p).replace(/^"|"$/g, '').trim();
    if (!cleaned) return;
    let dir = cleaned;
    if (/\.(exe|cmd|bat|ps1|js)$/i.test(cleaned)) dir = path.dirname(cleaned);
    roots.add(dir);
    // include one and two levels up for targeted config probe
    const p1 = path.dirname(dir);
    const p2 = path.dirname(p1);
    roots.add(p1);
    roots.add(p2);
  };

  for (const w of whereHits) addPath(w);
  for (const s of services) addPath(s.pathName || s.binaryPath || '');

  for (const p of processes) {
    for (const candidate of extractAbsolutePathsFromCommand(p.command || '')) addPath(candidate);
  }

  return Array.from(roots).filter(Boolean).sort();
}

// Extra targeted probe: resolve openclaw.json from a running gateway process command line.
// This is bounded and deterministic (no disk-wide crawl).
function resolveConfigCandidatesFromProcesses(processes) {
  if (PLATFORM !== 'win32') return [];

  const anchors = processes.flatMap(p => extractAbsolutePathsFromCommand(p.command || ''));
  const uniqAnchors = Array.from(new Set(anchors.filter(anchor => /^[A-Za-z]:\\/.test(anchor))));
  const hits = new Set();

  const up = (dir, n) => {
    let cur = dir;
    for (let i = 0; i < n; i++) cur = path.dirname(cur);
    return cur;
  };

  for (const a of uniqAnchors) {
    const dir = path.dirname(a);
    for (let i = 0; i <= 6; i++) {
      const root = up(dir, i);
      const cands = [
        path.join(root, '.openclaw', 'openclaw.json'),
        path.join(root, 'gateway', '.openclaw', 'openclaw.json'),
        path.join(root, 'Gateway', '.openclaw', 'openclaw.json'),
        path.join(root, 'gateway', 'config', 'openclaw.json'),
        path.join(root, 'Gateway', 'config', 'openclaw.json'),
        path.join(root, 'config', 'openclaw.json'),
        path.join(root, 'state', 'openclaw.json'),
      ];
      for (const c of cands) {
        if (exists(c)) hits.add(c);
      }
    }
  }

  return Array.from(hits);
}

function targetedWindowsConfigProbe(signalRoots) {
  const out = [];
  for (const root of signalRoots) {
    const rr = root.replace(/'/g, "''");
    const cmd = `if (Test-Path '${rr}') { Get-ChildItem -Path '${rr}' -Filter openclaw.json -Recurse -Depth 4 -ErrorAction SilentlyContinue | Select-Object -First 20 -Expand FullName }`;
    const r = runPwsh(cmd);
    if (r.ok && r.out) out.push(...r.out.split(/\r?\n/).filter(Boolean));
  }
  return Array.from(new Set(out));
}

function windowsBreadcrumbRoots() {
  // fast, deterministic roots (no guessing drive letters beyond C:)
  return [
    'C:\\Program Files\\Openclaw',
    'C:\\Program Files\\ResonantOS',
    'C:\\Program Files (x86)\\Openclaw',
    'C:\\Program Files (x86)\\ResonantOS',
    'C:\\ProgramData\\OpenClaw',
    'C:\\ProgramData\\ResonantOS',
  ];
}

function macosBreadcrumbRoots() {
  return [
    // app installs (optional)
    '/Applications/OpenClaw.app',
    '/Applications/ResonantOS.app',

    // system-level config/data
    '/Library/Application Support/openclaw',
    '/Library/Application Support/ResonantOS',
    '/etc/openclaw',
    '/etc/resonantos',

    // user-level config/data
    path.join(os.homedir(), 'Library', 'Application Support', 'openclaw'),
    path.join(os.homedir(), '.openclaw'),
  ];
}

function linuxBreadcrumbRoots() {
  return [
    // system-level
    '/etc/openclaw',
    '/etc/resonantos',
    '/opt/openclaw',
    '/opt/resonantos',
    '/var/lib/openclaw',
    '/var/lib/resonantos',

    // user-level
    path.join(os.homedir(), '.config', 'openclaw'),
    path.join(os.homedir(), '.openclaw'),

    // common container mounts
    '/workspace/.openclaw',
    '/workspace',
  ];
}

function breadcrumbConfigProbeWindows() {
  if (PLATFORM !== 'win32') return [];
  const roots = windowsBreadcrumbRoots().filter(exists);
  if (!roots.length) return [];
  const out = [];
  for (const root of roots) {
    const rr = root.replace(/'/g, "''");
    const cmd = `Get-ChildItem -Path '${rr}' -Filter openclaw.json -Recurse -Depth 6 -ErrorAction SilentlyContinue | Select-Object -First 50 -Expand FullName`;
    const r = runPwsh(cmd);
    if (r.ok && r.out) out.push(...r.out.split(/\r?\n/).filter(Boolean));
  }
  return Array.from(new Set(out));
}

function boundedFindConfigFiles(roots, { maxDepth = 6, maxResults = 50 } = {}) {
  const out = [];
  const seen = new Set();
  const queue = [];

  for (const root of (roots || []).filter(exists)) {
    queue.push({ dir: root, depth: 0 });
  }

  while (queue.length && out.length < maxResults) {
    const current = queue.shift();
    const key = normalizePathKey(current?.dir);
    if (!current?.dir || !key || seen.has(key)) continue;
    seen.add(key);

    let entries;
    try {
      entries = fs.readdirSync(current.dir, { withFileTypes: true });
    } catch {
      continue;
    }

    for (const entry of entries) {
      const fullPath = path.join(current.dir, entry.name);
      if (entry.isFile() && entry.name === 'openclaw.json') {
        out.push(fullPath);
        if (out.length >= maxResults) break;
        continue;
      }
      if (entry.isDirectory() && current.depth < maxDepth) {
        queue.push({ dir: fullPath, depth: current.depth + 1 });
      }
    }
  }

  return out;
}

function breadcrumbConfigProbePosix(roots, maxDepth = 6) {
  return Array.from(new Set(boundedFindConfigFiles(roots, { maxDepth, maxResults: 50 })));
}

function breadcrumbConfigProbeMacos() {
  if (PLATFORM !== 'darwin') return [];
  return breadcrumbConfigProbePosix(macosBreadcrumbRoots(), 6);
}

function breadcrumbConfigProbeLinux() {
  if (PLATFORM !== 'linux') return [];
  return breadcrumbConfigProbePosix(linuxBreadcrumbRoots(), 6);
}

function configCandidates(ctx, signalRoots = []) {
  if (PLATFORM === 'win32') {
    const appData = process.env.APPDATA || path.join(os.homedir(), 'AppData', 'Roaming');
    const local = process.env.LOCALAPPDATA || path.join(os.homedir(), 'AppData', 'Local');
    const user = process.env.USERPROFILE || os.homedir();
    let paths = [
      path.join(appData, 'openclaw', 'openclaw.json'),
      path.join(local, 'openclaw', 'openclaw.json'),
      path.join(user, '.openclaw', 'openclaw.json'),
      'C:\\ProgramData\\openclaw\\openclaw.json',
    ];
    if (ctx.profileScope === 'systemprofile') paths = paths.concat(windowsUserProfilesCandidates());
    // probe from strong runtime signals (where/service/process) before guessing roots
    paths = paths.concat(targetedWindowsConfigProbe(signalRoots));
    paths = paths.concat(breadcrumbConfigProbeWindows());
    return Array.from(new Set(paths)).sort();
  }

  if (PLATFORM === 'darwin') {
    return Array.from(
      new Set([
        path.join(os.homedir(), 'Library', 'Application Support', 'openclaw', 'openclaw.json'),
        path.join(os.homedir(), '.openclaw', 'openclaw.json'),
        '/etc/openclaw/openclaw.json',
        ...breadcrumbConfigProbeMacos(),
      ])
    ).sort();
  }

  // linux
  return Array.from(
    new Set([
      path.join(os.homedir(), '.config', 'openclaw', 'openclaw.json'),
      path.join(os.homedir(), '.openclaw', 'openclaw.json'),
      '/etc/openclaw/openclaw.json',
      '/workspace/.openclaw/openclaw.json',
      ...breadcrumbConfigProbeLinux(),
    ])
  ).sort();
}

function deepSearch(enabled, extraRoots = []) {
  if (!enabled) return [];
  if (PLATFORM === 'win32') {
    const roots = Array.from(new Set(['C:\\ProgramData', os.homedir(), ...(extraRoots || [])])).filter(exists);
    const out = [];
    for (const root of roots) {
      const r = runPwsh(`Get-ChildItem -Path '${root.replace(/'/g, "''")}' -Filter openclaw.json -Recurse -ErrorAction SilentlyContinue | Select-Object -First 200 -Expand FullName`, {
        area: 'deep_search',
        tool: 'powershell',
        missingToolMessage: 'Deep search on Windows requires PowerShell and was skipped because it was not available.',
      });
      if (r.ok && r.out) out.push(...r.out.split(/\r?\n/).filter(Boolean));
    }
    return Array.from(new Set(out)).sort();
  }
  const roots = Array.from(new Set([os.homedir(), '/workspace', '/etc', '/opt', ...(extraRoots || [])])).filter(exists);
  return Array.from(new Set(boundedFindConfigFiles(roots, { maxDepth: 32, maxResults: 200 }))).sort();
}

function normalizeConfig(cfg) {
  if (!cfg || typeof cfg !== 'object') return { workspacePath: null, wsUrl: null, dashboardPort: null, gatewayMode: null };
  return {
    workspacePath:
      cfg.workspacePath ||
      cfg.workspace?.path ||
      cfg.workspace ||
      cfg.paths?.workspace ||
      cfg.agents?.defaults?.workspace ||
      process.env.OPENCLAW_WORKSPACE ||
      null,
    wsUrl: cfg.gateway?.wsUrl || cfg.gateway?.url || cfg.wsUrl || cfg.gatewayWsUrl || cfg.dashboard?.wsUrl || null,
    dashboardPort: cfg.dashboard?.port || cfg.gateway?.port || cfg.port || cfg.dashboardPort || null,
    gatewayMode: cfg.gateway?.mode || cfg.mode || null,
  };
}

function deriveWorkspacePathFromConfigPath(configPath) {
  const abs = safeAbsolutePath(configPath);
  if (!abs) return null;

  const candidates = [];
  const dir = path.dirname(abs);
  const normalized = normalizePathKey(abs) || '';

  if (/[\\/]\.openclaw[\\/]openclaw\.json$/i.test(normalized)) {
    candidates.push(path.join(dir, 'workspace'));
  }
  if (/[\\/]config[\\/]openclaw\.json$/i.test(normalized)) {
    candidates.push(path.join(path.dirname(dir), 'workspace'));
  }
  if (/[\\/]state[\\/]openclaw\.json$/i.test(normalized)) {
    candidates.push(path.join(path.dirname(dir), 'workspace'));
  }
  if (/[\\/]gateway[\\/]config[\\/]openclaw\.json$/i.test(normalized)) {
    candidates.push(path.join(path.dirname(path.dirname(dir)), 'workspace'));
  }

  return candidates.find(candidate => {
    try { return fs.statSync(candidate).isDirectory(); } catch { return false; }
  }) || null;
}

function parseIdentityName(workspacePath) {
  if (!workspacePath) return { identityPath: null, identityName: null };
  const p = path.resolve(workspacePath, 'IDENTITY.md');
  if (!exists(p)) return { identityPath: p, identityName: null };
  try {
    const txt = readTextAuto(p);
    const m = txt.match(/^\s*-\s*\*\*Name:\*\*\s*(.+)$/mi) || txt.match(/^\s*Name:\s*(.+)$/mi);
    return { identityPath: p, identityName: m ? m[1].trim() : null };
  } catch {
    return { identityPath: p, identityName: null };
  }
}

function probeProcesses() {
  if (PLATFORM === 'win32') {
    const r = runPwsh("Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'openclaw|node|gateway' -and $_.CommandLine -match 'openclaw|gateway' } | Select-Object ProcessId,Name,CommandLine | ConvertTo-Json -Compress", {
      area: 'process_probe',
      tool: 'powershell',
      missingToolMessage: 'Windows process-first detection requires PowerShell and was skipped because it was not available.',
    });
    if (!r.ok || !r.out) return [];
    try {
      const p = JSON.parse(r.out); const arr = Array.isArray(p) ? p : [p];
      return arr.map(x => ({ pid: Number(x.ProcessId), name: x.Name, command: x.CommandLine || '' }));
    } catch { return []; }
  }
  const r = run('ps', ['-eo', 'pid,user,command'], 6000, {
    area: 'process_probe',
    tool: 'ps',
    missingToolMessage: 'POSIX process-first detection requires ps and was skipped because it was not available.',
  });
  if (!r.ok || !r.out) return [];
  return r.out.split('\n').filter(line => /openclaw|openclaw-gateway/i.test(line)).map(line => {
    const m = line.trim().match(/^(\d+)\s+(\S+)\s+(.+)$/);
    return m ? { pid: Number(m[1]), user: m[2], command: m[3] } : { raw: line };
  });
}

function probeServices() {
  if (PLATFORM === 'win32') {
    const r = runPwsh("Get-CimInstance Win32_Service | Where-Object { $_.Name -match 'openclaw' -or $_.DisplayName -match 'openclaw' -or $_.PathName -match 'openclaw' } | Select-Object Name,DisplayName,State,StartMode,PathName | ConvertTo-Json -Compress", {
      area: 'service_probe',
      tool: 'powershell',
      missingToolMessage: 'Windows service probe requires PowerShell and was skipped because it was not available.',
    });
    if (!r.ok || !r.out) return [];
    try {
      const p = JSON.parse(r.out);
      const arr = Array.isArray(p) ? p : [p];
      return arr.map(s => ({
        name: s.Name,
        displayName: s.DisplayName,
        status: s.State,
        startType: s.StartMode,
        pathName: s.PathName || null,
      }));
    } catch {
      return [];
    }
  }
  if (PLATFORM === 'darwin') {
    const r = run('launchctl', ['list'], 6000, {
      area: 'service_probe',
      tool: 'launchctl',
      missingToolMessage: 'macOS service probe requires launchctl and was skipped because it was not available.',
    });
    return r.ok && r.out ? r.out.split('\n').filter(line => /openclaw/i.test(line)).map(raw => ({ raw })) : [];
  }
  const r = run('systemctl', ['list-units', '--type=service', '--all'], 6000, {
    area: 'service_probe',
    tool: 'systemctl',
    missingToolMessage: 'Linux service probe requires systemctl and was skipped because it was not available.',
  });
  return r.ok && r.out ? r.out.split('\n').filter(line => /openclaw/i.test(line)).map(raw => ({ raw })) : [];
}

function dockerPortMappingsFromInspect(inspected) {
  const out = [];
  const ports = inspected?.NetworkSettings?.Ports || {};
  for (const [containerPortProto, bindings] of Object.entries(ports)) {
    const [containerPortRaw, protocol = 'tcp'] = String(containerPortProto).split('/');
    const containerPort = Number(containerPortRaw);
    if (!Array.isArray(bindings)) continue;
    for (const binding of bindings) {
      const hostPort = Number(binding?.HostPort);
      out.push({
        protocol,
        containerPort: Number.isFinite(containerPort) ? containerPort : null,
        hostIp: binding?.HostIp || null,
        hostPort: Number.isFinite(hostPort) ? hostPort : null,
      });
    }
  }
  return out;
}

function isOpenClawDockerContainer(container) {
  const hay = [
    container?.image,
    container?.name,
    container?.composeProject,
    container?.composeService,
    container?.command,
  ].filter(Boolean).join(' ').toLowerCase();
  return /openclaw|resonantos|helm/.test(hay);
}

function dockerCandidatePathsForRoot(root) {
  if (!root) return [];
  return [
    path.join(root, 'openclaw.json'),
    path.join(root, 'state', 'openclaw.json'),
    path.join(root, 'config', 'openclaw.json'),
    path.join(root, '.openclaw', 'openclaw.json'),
    path.join(root, 'gateway', 'config', 'openclaw.json'),
    path.join(root, 'gateway', '.openclaw', 'openclaw.json'),
    path.join(root, 'Gateway', 'config', 'openclaw.json'),
    path.join(root, 'Gateway', '.openclaw', 'openclaw.json'),
  ];
}

function addDockerRoot(roots, p) {
  if (!p) return;
  roots.add(p);
  try {
    const p1 = path.dirname(p);
    const p2 = path.dirname(p1);
    roots.add(p1);
    roots.add(p2);
  } catch {}
}

function dockerSignalRoots(docker) {
  const roots = new Set();
  for (const container of (docker?.containers || []).filter(isOpenClawDockerContainer)) {
    addDockerRoot(roots, container.composeWorkingDir);
    for (const mount of (container.mounts || [])) {
      addDockerRoot(roots, mount.source);
      if (mount.source && /[\\/](workspace|state|logs|secrets|config|\.openclaw)$/i.test(mount.source)) {
        addDockerRoot(roots, path.dirname(mount.source));
      }
    }
  }
  return Array.from(roots).filter(Boolean).sort();
}

function dockerConfigCandidates(docker) {
  const out = new Set();
  for (const container of (docker?.containers || []).filter(isOpenClawDockerContainer)) {
    const roots = new Set();
    if (container.composeWorkingDir) roots.add(container.composeWorkingDir);
    for (const mount of (container.mounts || [])) {
      if (mount.source) {
        roots.add(mount.source);
        if (/[\\/](workspace|state|logs|secrets|config|\.openclaw)$/i.test(mount.source)) roots.add(path.dirname(mount.source));
      }
    }
    for (const root of roots) {
      for (const candidate of dockerCandidatePathsForRoot(root)) {
        if (exists(candidate)) out.add(candidate);
      }
    }
  }
  return Array.from(out).sort();
}

function containerPathToHostPath(containerPath, container) {
  const posixPath = String(containerPath || '').replace(/\\/g, '/');
  if (!posixPath.startsWith('/')) return null;
  const mounts = [...(container?.mounts || [])].sort((a, b) => String(b.destination || '').length - String(a.destination || '').length);
  for (const mount of mounts) {
    const destination = String(mount.destination || '').replace(/\\/g, '/').replace(/\/+$/, '');
    if (!destination) continue;
    if (posixPath === destination || posixPath.startsWith(`${destination}/`)) {
      const rest = posixPath.slice(destination.length).replace(/^\/+/, '');
      return rest ? path.join(mount.source, ...rest.split('/')) : mount.source;
    }
  }
  return null;
}

function scoreDockerContainerForCandidate(container, candidatePath) {
  const target = normalizePathKey(candidatePath);
  if (!target) return 0;
  let best = 0;
  for (const mount of (container.mounts || [])) {
    best = Math.max(best, sharedPathPrefixDepth(target, mount.source));
  }
  if (container.composeWorkingDir) best = Math.max(best, sharedPathPrefixDepth(target, container.composeWorkingDir));
  return best;
}

function translateContainerPathToHost(containerPath, docker, candidatePath) {
  if (!containerPath || typeof containerPath !== 'string' || !containerPath.startsWith('/')) return containerPath;
  const containers = [...((docker?.containers || []).filter(isOpenClawDockerContainer))].sort((a, b) => scoreDockerContainerForCandidate(b, candidatePath) - scoreDockerContainerForCandidate(a, candidatePath));
  for (const container of containers) {
    const mapped = containerPathToHostPath(containerPath, container);
    if (mapped) return mapped;
  }
  return containerPath;
}

function probeDocker() {
  const ver = run('docker', ['--version']);
  if (!ver.ok) return { installed: false, running: false, containers: [] };
  const info = run('docker', ['info', '--format', '{{json .}}'], 5000);
  const ps = run('docker', ['ps', '--format', '{{.ID}}\t{{.Image}}\t{{.Names}}\t{{.Status}}'], 5000);
  const baseContainers = ps.ok && ps.out ? ps.out.split('\n').filter(Boolean).map(line => {
    const [id, image, name, status] = line.split('\t');
    return { id, image, name, status };
  }) : [];

  const inspectMap = new Map();
  if (baseContainers.length) {
    const ids = baseContainers.map(c => c.id).filter(Boolean);
    const inspected = ids.length ? run('docker', ['inspect', ...ids], 15000) : { ok: false };
    if (inspected.ok && inspected.out) {
      try {
        const parsed = JSON.parse(inspected.out);
        for (const item of (Array.isArray(parsed) ? parsed : [parsed])) {
          if (item?.Id) inspectMap.set(String(item.Id), item);
        }
      } catch {}
    }
  }

  const containers = baseContainers.map(container => {
    const inspected = inspectMap.get(container.id) || Array.from(inspectMap.entries()).find(([id]) => id.startsWith(container.id))?.[1] || null;
    const labels = inspected?.Config?.Labels || {};
    return {
      ...container,
      healthStatus: inspected?.State?.Health?.Status || inspected?.State?.Status || null,
      publishedPorts: dockerPortMappingsFromInspect(inspected),
      mounts: (inspected?.Mounts || []).map(m => ({
        type: m?.Type || null,
        source: m?.Source || null,
        destination: m?.Destination || null,
        rw: Boolean(m?.RW),
      })),
      composeProject: labels['com.docker.compose.project'] || null,
      composeService: labels['com.docker.compose.service'] || null,
      composeWorkingDir: labels['com.docker.compose.project.working_dir'] || null,
      workingDir: inspected?.Config?.WorkingDir || null,
      command: [inspected?.Path, ...(Array.isArray(inspected?.Args) ? inspected.Args : [])].filter(Boolean).join(' '),
    };
  });

  return { installed: true, running: info.ok, containers };
}

function windowsCapabilities(services, configInstances) {
  if (PLATFORM !== 'win32') {
    return {
      serviceModel: { status: 'n/a', evidence: 'not_windows' },
      dockerDesktopBridge: { checked: false, method: null, target: null, reachable: null },
      startMenuIntegration: { supported: false, status: 'not_windows' },
    };
  }

  const serviceModel = services.length
    ? { status: 'service_account', evidence: 'openclaw service detected' }
    : { status: 'user_account_or_manual', evidence: 'no service detected' };

  const port = configInstances.find(i => i.dashboardPort)?.dashboardPort || 18820;
  const bridge = runPwsh(`if (Test-NetConnection host.docker.internal -Port ${port} -InformationLevel Quiet -WarningAction SilentlyContinue) { 'true' } else { 'false' }`);

  return {
    serviceModel,
    dockerDesktopBridge: {
      checked: true,
      method: 'tcp',
      target: `host.docker.internal:${port}`,
      reachable: bridge.ok ? String(bridge.out).trim() === 'true' : false,
    },
    startMenuIntegration: { supported: true, status: 'available' },
  };
}

function normalizePathKey(p) {
  if (!p) return null;
  try {
    const resolved = path.resolve(String(p));
    return (PLATFORM === 'win32' ? resolved.replace(/\//g, '\\').toLowerCase() : resolved.replace(/\\/g, '/')).replace(/[\\/]+$/, '');
  } catch {
    const raw = String(p).trim();
    return (PLATFORM === 'win32' ? raw.replace(/\//g, '\\').toLowerCase() : raw.replace(/\\/g, '/')).replace(/[\\/]+$/, '');
  }
}

function normalizeWorkspaceKey(workspacePath) {
  return workspacePath ? normalizePathKey(workspacePath) : null;
}

function getFileMetadata(p) {
  if (!exists(p)) return { fileModifiedMs: null, fileModifiedAt: null };
  try {
    const st = fs.statSync(p);
    return {
      fileModifiedMs: Number(st.mtimeMs || 0) || 0,
      fileModifiedAt: st.mtime ? st.mtime.toISOString() : null,
    };
  } catch {
    return { fileModifiedMs: null, fileModifiedAt: null };
  }
}

function classifyConfigCandidatePath(p) {
  const sl = String(normalizePathKey(p) || '').toLowerCase();
  const tags = [];
  let authorityScore = 0;
  let backupLike = false;
  let stateLike = false;
  let canonicalLike = false;

  const add = (tag, delta = 0) => {
    if (!tags.includes(tag)) tags.push(tag);
    authorityScore += delta;
  };

  if (!sl) return { tags, authorityScore, backupLike, stateLike, canonicalLike };

  if (/[\\/]programdata[\\/]openclaw[\\/]/i.test(sl)) add('programdata_openclaw', 180);
  if (/[\\/]programdata[\\/]openclaw[\\/]gateway[\\/]/i.test(sl)) add('programdata_gateway', 160);

  if (/[\\/]gateway[\\/]config[\\/]openclaw\.json$/i.test(sl)) {
    add('gateway_config', 420);
    canonicalLike = true;
  } else if (/[\\/]config[\\/]openclaw\.json$/i.test(sl)) {
    add('config_path', 240);
    canonicalLike = true;
  }

  if (/[\\/]gateway[\\/]\.openclaw[\\/]openclaw\.json$/i.test(sl)) add('gateway_dot_openclaw', 140);
  else if (/[\\/]\.openclaw[\\/]openclaw\.json$/i.test(sl)) add('dot_openclaw', 90);

  if (/[\\/]state[\\/]openclaw\.json$/i.test(sl)) {
    add('state_path', -140);
    stateLike = true;
  }

  if (/[\\/]instances[\\/]/i.test(sl)) add('instance_scoped_path', 40);

  if (/[\\/]_backups[\\/]/i.test(sl) || /[\\/]backups[\\/]/i.test(sl) || /[\\/]archive[\\/]/i.test(sl) || /[\\/]archived[\\/]/i.test(sl) || /cutover_/i.test(sl)) {
    add('backup_like_path', -550);
    backupLike = true;
  }

  if (/openclaw\.json\.(bak|old|orig)$/i.test(sl) || /[\\/]openclaw[-_.]backup\.json$/i.test(sl)) {
    add('backup_named_file', -550);
    backupLike = true;
  }

  return { tags, authorityScore, backupLike, stateLike, canonicalLike };
}

function buildConfigCandidateFamilyKey(p) {
  const key = normalizePathKey(p);
  if (!key) return null;

  return key
    .replace(/[\\/]openclaw\.json$/i, '')
    .replace(/[\\/]config$/i, '')
    .replace(/[\\/]state$/i, '')
    .replace(/[\\/]\.openclaw$/i, '')
    .replace(/[\\/]+$/, '');
}

const gatewayHealthCache = new Map();

function probeLocalGatewayHealth(port) {
  const pn = Number(port);
  if (!Number.isFinite(pn) || pn <= 0) {
    return { port: null, checked: false, live: false, statusCode: null, statusText: 'no_port', endpoint: null };
  }

  if (gatewayHealthCache.has(pn)) return gatewayHealthCache.get(pn);

  const endpoint = `http://127.0.0.1:${pn}/health`;
  let result = { port: pn, checked: true, live: false, statusCode: null, statusText: 'unreachable', endpoint };

  if (PLATFORM === 'win32') {
    const ps = [
      "$ProgressPreference='SilentlyContinue'",
      `try {`,
      `  $r = Invoke-WebRequest -UseBasicParsing -Uri '${endpoint}' -TimeoutSec 2`,
      `  [PSCustomObject]@{ ok=([int]$r.StatusCode -eq 200); code=[int]$r.StatusCode; desc=($r.StatusDescription -as [string]); endpoint='${endpoint}' } | ConvertTo-Json -Compress`,
      `} catch {`,
      `  if ($_.Exception.Response) {`,
      `    $resp = $_.Exception.Response`,
      `    [PSCustomObject]@{ ok=([int]$resp.StatusCode -eq 200); code=[int]$resp.StatusCode; desc=($resp.StatusDescription -as [string]); endpoint='${endpoint}' } | ConvertTo-Json -Compress`,
      `  } else {`,
      `    [PSCustomObject]@{ ok=$false; code=$null; desc=($_.Exception.Message -as [string]); endpoint='${endpoint}' } | ConvertTo-Json -Compress`,
      `  }`,
      `}`,
    ].join('; ');

    const r = runPwsh(ps);
    if (r.ok && r.out) {
      try {
        const parsed = JSON.parse(r.out);
        result = {
          port: pn,
          checked: true,
          live: Boolean(parsed.ok),
          statusCode: Number.isFinite(Number(parsed.code)) ? Number(parsed.code) : null,
          statusText: parsed.desc || (parsed.ok ? 'OK' : 'unreachable'),
          endpoint: parsed.endpoint || endpoint,
        };
      } catch {
        result.statusText = r.err || 'unreachable';
      }
    } else if (r.err) {
      result.statusText = r.err;
    }
  } else {
    const r = run('curl', ['-sS', '-o', '/dev/null', '-w', '%{http_code}', '--max-time', '2', endpoint], 4000, {
      area: 'gateway_health_probe',
      tool: 'curl',
      missingToolMessage: 'Gateway health probe on POSIX requires curl and could not run because it was not available.',
    });
    const code = Number(String(r.out || '').trim());
    if (Number.isFinite(code) && code > 0) {
      result.statusCode = code;
      result.live = code === 200;
      result.statusText = code === 200 ? 'OK' : `HTTP ${code}`;
    } else if (r.err) {
      result.statusText = r.err;
    }
  }

  gatewayHealthCache.set(pn, result);
  return result;
}

function pathSegments(p) {
  const key = normalizePathKey(p);
  return key ? key.split(/[\\/]+/).filter(Boolean) : [];
}

function sharedPathPrefixDepth(a, b) {
  const aa = pathSegments(a);
  const bb = pathSegments(b);
  const len = Math.min(aa.length, bb.length);
  let depth = 0;
  for (let i = 0; i < len; i++) {
    if (aa[i] !== bb[i]) break;
    depth += 1;
  }
  return depth;
}

function extractAbsolutePathsFromCommand(cmd) {
  const raw = String(cmd || '');
  const hits = new Set();
  const patterns = [
    /"([A-Za-z]:\\[^"\r\n]+?\.(?:exe|cmd|bat|ps1|js|mjs))"/g,
    /'([A-Za-z]:\\[^'\r\n]+?\.(?:exe|cmd|bat|ps1|js|mjs))'/g,
    /([A-Za-z]:\\[^"'\r\n]+?\.(?:exe|cmd|bat|ps1|js|mjs))(?=\s+(?:--|-[A-Za-z0-9])|$)/g,
    /"(\/(?:[^"\r\n]+?)\.(?:exe|cmd|bat|ps1|js|mjs))"/g,
    /'(\/(?:[^'\r\n]+?)\.(?:exe|cmd|bat|ps1|js|mjs))'/g,
    /(\/(?:[^\s"'\r\n]+(?:\s+[^\s"'\r\n]+)*)\.(?:exe|cmd|bat|ps1|js|mjs))(?=\s+(?:--|-[A-Za-z0-9])|$)/g,
  ];

  for (const re of patterns) {
    let m;
    while ((m = re.exec(raw)) !== null) {
      const candidate = String(m[1] || '').trim();
      if (candidate) hits.add(candidate);
    }
  }

  return Array.from(hits);
}

function extractPortHintsFromCommand(cmd) {
  const raw = String(cmd || '');
  const ports = new Set();
  const patterns = [/--port(?:=|\s+)(\d{2,5})/gi, /-p(?:=|\s+)(\d{2,5})/gi, /:(\d{2,5})\b/g];
  for (const re of patterns) {
    let m;
    while ((m = re.exec(raw)) !== null) {
      const n = Number(m[1]);
      if (Number.isFinite(n) && n > 0 && n <= 65535) ports.add(n);
    }
  }
  return Array.from(ports);
}

function isLikelyUserProfilePath(p) {
  const key = normalizePathKey(p);
  if (!key) return false;
  return /[\\/]users[\\/][^\\/]+[\\/](?:\.openclaw|appdata[\\/](?:local|roaming)[\\/]openclaw)/i.test(key);
}

function extractInstanceScopedName(p) {
  const key = normalizePathKey(p);
  if (!key) return null;
  const m = key.match(/[\\/]instances[\\/]([^\\/]+)/i);
  return m ? m[1] : null;
}

function deriveCandidateConfidence({ exists, workspacePath, wsUrl, dashboardPort, identityName }) {
  if (!exists) return 'blocked';
  if (workspacePath && (wsUrl || dashboardPort) && identityName) return 'attach-ready';
  return 'partial';
}

function applyCandidateAuthorityAdjustments(candidates) {
  const adjusted = candidates.map(candidate => ({ ...candidate }));
  const byFamily = new Map();

  for (const candidate of adjusted) {
    const familyKey = candidate.candidateFamilyKey || candidate.configPathKey;
    if (!byFamily.has(familyKey)) byFamily.set(familyKey, []);
    byFamily.get(familyKey).push(candidate);
  }

  for (const group of byFamily.values()) {
    const canonical = group.filter(c => c.exists && c.candidateCanonicalLike);
    if (!canonical.length) continue;
    const newestCanonicalMs = Math.max(...canonical.map(c => Number(c.fileModifiedMs || 0)));
    for (const candidate of group) {
      const tags = new Set(candidate.candidatePathTags || []);
      if (!tags.has('gateway_dot_openclaw') && !tags.has('dot_openclaw')) continue;
      candidate.candidateAuthorityScore -= 180;
      candidate.evidence = Array.from(new Set([...(candidate.evidence || []), 'sidecar_demoted_due_to_canonical_config']));
      if (Number(candidate.fileModifiedMs || 0) <= newestCanonicalMs) {
        candidate.candidateAuthorityScore -= 20;
        candidate.evidence = Array.from(new Set([...(candidate.evidence || []), 'sidecar_older_than_canonical_config']));
      }
    }
  }

  return adjusted;
}

function buildConfigCandidates(configPaths, services, docker, processes, ctx) {
  const candidates = [];
  for (const p of configPaths) {
    const ex = exists(p);
    const cfg = ex ? safeJson(p) : null;
    const norm = normalizeConfig(cfg);
    const workspaceHint = norm.workspacePath || deriveWorkspacePathFromConfigPath(p);
    const workspacePath = translateContainerPathToHost(workspaceHint, docker, p);
    const { identityPath, identityName } = parseIdentityName(workspacePath);
    const fileMeta = getFileMetadata(p);
    const candidatePath = classifyConfigCandidatePath(p);
    const evidence = ex ? ['config_path_exists'] : ['config_path_missing'];
    if (cfg === null && ex) evidence.push('config_parse_failed');
    if (!norm.workspacePath && workspacePath) evidence.push('workspace_inferred_from_standard_layout');
    if (workspacePath && norm.workspacePath && workspacePath !== norm.workspacePath) evidence.push('workspace_translated_from_container_path');

    candidates.push({
      recordType: 'config_candidate',
      instanceName: identityName || null,
      openclawConfigPath: p,
      configPathKey: normalizePathKey(p),
      workspacePath,
      normalizedWorkspaceKey: normalizeWorkspaceKey(workspacePath),
      identityPath,
      identityNameExtracted: identityName,
      wsUrl: norm.wsUrl,
      dashboardPort: norm.dashboardPort,
      gatewayMode: norm.gatewayMode,
      exists: ex,
      readable: ex ? canRead(p) : false,
      writable: ex ? canWrite(p) : false,
      confidence: deriveCandidateConfidence({
        exists: ex,
        workspacePath,
        wsUrl: norm.wsUrl,
        dashboardPort: norm.dashboardPort,
        identityName,
      }),
      evidence,
      fileModifiedMs: fileMeta.fileModifiedMs,
      fileModifiedAt: fileMeta.fileModifiedAt,
      candidatePathTags: candidatePath.tags,
      candidateAuthorityScore: candidatePath.authorityScore,
      candidateBackupLike: candidatePath.backupLike,
      candidateStateLike: candidatePath.stateLike,
      candidateCanonicalLike: candidatePath.canonicalLike,
      candidateFamilyKey: buildConfigCandidateFamilyKey(p),
    });
  }

  return applyCandidateAuthorityAdjustments(candidates)
    .sort((a, b) => Number(b.exists) - Number(a.exists) || String(a.openclawConfigPath).localeCompare(String(b.openclawConfigPath)));
}

function compareConfigCandidates(a, b) {
  const scoreDiff = Number(b.candidateAuthorityScore || 0) - Number(a.candidateAuthorityScore || 0);
  if (scoreDiff) return scoreDiff;

  const timeDiff = Number(b.fileModifiedMs || 0) - Number(a.fileModifiedMs || 0);
  if (timeDiff) return timeDiff;

  return String(a.openclawConfigPath || '').localeCompare(String(b.openclawConfigPath || ''));
}

function collapseSameConfigPath(candidates) {
  const buckets = new Map();

  for (const candidate of candidates) {
    const key = candidate.configPathKey || normalizePathKey(candidate.openclawConfigPath) || String(candidate.openclawConfigPath || '');
    if (!buckets.has(key)) buckets.set(key, []);
    buckets.get(key).push(candidate);
  }

  const collapsed = [];
  for (const group of buckets.values()) {
    group.sort(compareConfigCandidates);
    const best = { ...group[0] };
    if (group.length > 1) {
      best.sameConfigPathAliases = group.slice(1).map(g => g.openclawConfigPath);
      best.evidence = Array.from(new Set([...(best.evidence || []), 'collapsed_same_config_path']));
    }
    collapsed.push(best);
  }

  return collapsed;
}

function deriveClusterInfoFromCandidates(candidates) {
  const sorted = [...(candidates || [])].sort(compareConfigCandidates);
  const workspaceKey = sorted.find(c => c.normalizedWorkspaceKey)?.normalizedWorkspaceKey || null;
  const port = Number(sorted.find(c => Number.isFinite(Number(c.dashboardPort)) && Number(c.dashboardPort) > 0)?.dashboardPort || 0) || null;
  const familyKey = sorted.find(c => c.candidateFamilyKey)?.candidateFamilyKey || null;
  const pathKey = sorted[0]?.configPathKey || normalizePathKey(sorted[0]?.openclawConfigPath) || String(sorted[0]?.openclawConfigPath || '');

  if (workspaceKey && port) {
    return {
      key: `workspace_port|${workspaceKey}|${port}`,
      strategy: 'workspace_port',
      workspaceKey,
      port,
      familyKey,
    };
  }

  if (workspaceKey) {
    return {
      key: `workspace_only|${workspaceKey}`,
      strategy: 'workspace_only',
      workspaceKey,
      port,
      familyKey,
    };
  }

  if (familyKey && port) {
    return {
      key: `family_port|${familyKey}|${port}`,
      strategy: 'family_port',
      workspaceKey,
      port,
      familyKey,
    };
  }

  if (familyKey) {
    return {
      key: `family_only|${familyKey}`,
      strategy: 'family_only',
      workspaceKey,
      port,
      familyKey,
    };
  }

  return {
    key: `config_path|${pathKey}`,
    strategy: 'config_path',
    workspaceKey,
    port,
    familyKey,
  };
}

function buildInstanceClusterKey(candidate) {
  return deriveClusterInfoFromCandidates([candidate]);
}

function classifyRuntimeForCluster(cluster, services, docker, processes, ctx) {
  const scores = {
    windows_service: 0,
    windows_user: 0,
    docker_container: 0,
    linux_systemd: 0,
    manual_process: 0,
    unknown: 0,
  };
  const evidence = [];
  const add = (type, points, reason) => {
    scores[type] = Number(scores[type] || 0) + Number(points || 0);
    evidence.push({ runtimeType: type, points: Number(points || 0), reason });
  };

  const candidates = Array.isArray(cluster.configCandidates) && cluster.configCandidates.length
    ? cluster.configCandidates
    : [cluster];
  const candidatePaths = candidates.map(c => c.openclawConfigPath).filter(Boolean);
  const matchablePaths = Array.from(new Set([...candidatePaths, ...(cluster.workspacePath ? [cluster.workspacePath] : [])])).filter(Boolean);
  const candidateTags = new Set(candidates.flatMap(c => c.candidatePathTags || []));
  const clusterPort = Number(cluster.dashboardPort);
  const hasPort = Number.isFinite(clusterPort) && clusterPort > 0;

  if (candidatePaths.some(p => /[\\/]programdata[\\/]openclaw[\\/]gateway[\\/]/i.test(normalizePathKey(p) || ''))) {
    add('windows_service', 6, 'candidate_under_programdata_gateway');
  }
  if (candidateTags.has('gateway_config') && candidatePaths.some(p => /[\\/]programdata[\\/]openclaw[\\/]gateway[\\/]/i.test(normalizePathKey(p) || ''))) {
    add('windows_service', 4, 'gateway_config_under_programdata_gateway');
  }
  if (candidateTags.has('gateway_dot_openclaw')) add('windows_service', 2, 'gateway_dot_openclaw_candidate');

  if (candidatePaths.some(isLikelyUserProfilePath)) add('windows_user', 5, 'candidate_under_user_profile');
  if (candidatePaths.some(p => /[\\/]program files(?: \(x86\))?[\\/]openclaw[\\/]/i.test(normalizePathKey(p) || ''))) add('windows_user', 3, 'candidate_under_program_files');

  if (candidateTags.has('instance_scoped_path')) add('docker_container', 4, 'candidate_under_instances');
  if (candidates.some(c => c.candidateStateLike)) add('docker_container', 2, 'state_path_candidate');

  if (candidatePaths.some(p => /(^|[\\/])etc[\\/]openclaw[\\/]|(^|[\\/])var[\\/]lib[\\/]openclaw[\\/]|(^|[\\/])library[\\/]application support[\\/]openclaw[\\/]/i.test(normalizePathKey(p) || ''))) {
    add('linux_systemd', 5, 'candidate_under_system_openclaw_path');
  }

  const servicePaths = services.flatMap(s => extractAbsolutePathsFromCommand(s.pathName || s.binaryPath || ''));
  let maxServicePrefix = 0;
  for (const cPath of matchablePaths) {
    for (const sPath of servicePaths) {
      maxServicePrefix = Math.max(maxServicePrefix, sharedPathPrefixDepth(cPath, sPath));
    }
  }
  if (maxServicePrefix >= 4) add('windows_service', 8, 'service_path_near_candidate');
  else if (maxServicePrefix >= 2) add('windows_service', 4, 'service_path_same_root_family');

  const openclawContainers = (docker?.containers || []).filter(isOpenClawDockerContainer);
  if (openclawContainers.length && (candidateTags.has('instance_scoped_path') || candidates.some(c => c.candidateStateLike))) {
    add('docker_container', 6, 'docker_openclaw_present_with_instance_scoped_candidate');
  }

  let bestDockerMountPrefix = 0;
  let sawDockerPortMatch = false;
  for (const container of openclawContainers) {
    if (hasPort && (container.publishedPorts || []).some(p => p.hostPort === clusterPort || p.containerPort === clusterPort)) {
      sawDockerPortMatch = true;
    }
    for (const mount of (container.mounts || [])) {
      for (const cPath of matchablePaths) {
        bestDockerMountPrefix = Math.max(bestDockerMountPrefix, sharedPathPrefixDepth(cPath, mount.source));
      }
    }
    if (container.composeWorkingDir) {
      for (const cPath of matchablePaths) {
        bestDockerMountPrefix = Math.max(bestDockerMountPrefix, sharedPathPrefixDepth(cPath, container.composeWorkingDir));
      }
    }
  }
  if (sawDockerPortMatch) add('docker_container', 8, 'docker_port_match');
  if (bestDockerMountPrefix >= 4) add('docker_container', 7, 'docker_mount_path_match');
  else if (bestDockerMountPrefix >= 2) add('docker_container', 4, 'docker_mount_same_root_family');

  const scopedNames = Array.from(new Set(candidatePaths.map(extractInstanceScopedName).filter(Boolean)));
  for (const scopedName of scopedNames) {
    if (openclawContainers.some(c => `${c.image || ''} ${c.name || ''} ${c.composeProject || ''} ${c.composeService || ''}`.toLowerCase().includes(String(scopedName).toLowerCase()))) {
      add('docker_container', 3, `docker_name_matches_${scopedName}`);
    }
  }

  let bestProcessPrefix = 0;
  let bestProcessPortPrefix = 0;
  let sawPortMatch = false;
  let sawGatewayProcess = false;

  for (const proc of (processes || [])) {
    const command = String(proc.command || '');
    const procPaths = extractAbsolutePathsFromCommand(command);
    const procPorts = extractPortHintsFromCommand(command);
    if (/gateway/i.test(command)) sawGatewayProcess = true;

    let procPrefix = 0;
    for (const cPath of matchablePaths) {
      for (const pPath of procPaths) {
        procPrefix = Math.max(procPrefix, sharedPathPrefixDepth(cPath, pPath));
      }
    }
    bestProcessPrefix = Math.max(bestProcessPrefix, procPrefix);

    const portMatch = hasPort && procPorts.includes(clusterPort);
    if (portMatch) {
      sawPortMatch = true;
      bestProcessPortPrefix = Math.max(bestProcessPortPrefix, procPrefix);
    }
  }

  if (sawPortMatch && bestProcessPortPrefix >= 2) add('manual_process', 7, 'process_port_and_path_match');
  else if (sawPortMatch) add('manual_process', 4, 'process_port_match');
  else if (bestProcessPrefix >= 3 && sawGatewayProcess) add('manual_process', 3, 'gateway_process_path_match');
  else if (bestProcessPrefix >= 2) add('manual_process', 2, 'process_same_root_family');

  const ranked = Object.entries(scores).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
  const [topType, topScore] = ranked[0] || ['unknown', 0];
  const secondScore = ranked[1] ? ranked[1][1] : 0;

  if (topScore <= 0) {
    scores.unknown = 1;
    evidence.push({ runtimeType: 'unknown', points: 1, reason: 'no_runtime_evidence' });
    return {
      runtimeType: 'unknown',
      runtimeConfidence: 'unknown',
      runtimeScores: scores,
      runtimeEvidence: evidence,
    };
  }

  const delta = topScore - secondScore;
  const runtimeConfidence = topScore >= 8 && delta >= 3 ? 'high' : topScore >= 5 ? 'medium' : 'low';

  return {
    runtimeType: topType,
    runtimeConfidence,
    runtimeScores: scores,
    runtimeEvidence: evidence,
  };
}

function buildInstanceClusterFromGroup(key, group, services, docker, processes, ctx) {
  const sorted = [...group].sort(compareConfigCandidates);
  const bestCandidate = sorted[0];
  const clusterInfo = bestCandidate._clusterInfo || deriveClusterInfoFromCandidates(sorted);
  const resolvedWorkspace = sorted.find(c => c.workspacePath)?.workspacePath || bestCandidate.workspacePath || null;
  const resolvedIdentityPath = sorted.find(c => c.identityPath)?.identityPath || bestCandidate.identityPath || null;
  const resolvedIdentityName = sorted.find(c => c.identityNameExtracted)?.identityNameExtracted || bestCandidate.identityNameExtracted || null;
  const resolvedInstanceName = sorted.find(c => c.instanceName)?.instanceName || bestCandidate.instanceName || null;
  const resolvedWsUrl = sorted.find(c => c.wsUrl)?.wsUrl || bestCandidate.wsUrl || null;
  const resolvedPort = Number(sorted.find(c => Number.isFinite(Number(c.dashboardPort)) && Number(c.dashboardPort) > 0)?.dashboardPort || bestCandidate.dashboardPort || 0) || null;
  const resolvedGatewayMode = sorted.find(c => c.gatewayMode)?.gatewayMode || bestCandidate.gatewayMode || null;
  const health = resolvedPort ? probeLocalGatewayHealth(resolvedPort) : { port: null, checked: false, live: false, statusCode: null, statusText: 'no_port', endpoint: null };
  const distinctNames = Array.from(new Set(sorted.map(g => g.instanceName).filter(Boolean)));
  const candidateFamilyKeys = Array.from(new Set(sorted.map(g => g.candidateFamilyKey).filter(Boolean)));

  const cluster = {
    ...bestCandidate,
    recordType: 'instance_cluster',
    instanceName: resolvedInstanceName,
    workspacePath: resolvedWorkspace,
    normalizedWorkspaceKey: normalizeWorkspaceKey(resolvedWorkspace),
    identityPath: resolvedIdentityPath,
    identityNameExtracted: resolvedIdentityName,
    wsUrl: resolvedWsUrl,
    dashboardPort: resolvedPort,
    gatewayMode: resolvedGatewayMode,
    confidence: deriveCandidateConfidence({
      exists: true,
      workspacePath: resolvedWorkspace,
      wsUrl: resolvedWsUrl,
      dashboardPort: resolvedPort,
      identityName: resolvedIdentityName,
    }),
    additionalConfigPaths: sorted.slice(1).map(g => g.openclawConfigPath),
    duplicateCandidates: sorted.slice(1).map(g => ({
      openclawConfigPath: g.openclawConfigPath,
      fileModifiedAt: g.fileModifiedAt || null,
      fileModifiedMs: g.fileModifiedMs || null,
      candidateAuthorityScore: g.candidateAuthorityScore || 0,
      candidatePathTags: g.candidatePathTags || [],
      candidateBackupLike: Boolean(g.candidateBackupLike),
      candidateStateLike: Boolean(g.candidateStateLike),
      candidateCanonicalLike: Boolean(g.candidateCanonicalLike),
      candidateFamilyKey: g.candidateFamilyKey || null,
    })),
    dedupeKey: key,
    dedupeStrategy: clusterInfo.strategy,
    configCandidateCount: sorted.length,
    configCandidatePaths: sorted.map(g => g.openclawConfigPath),
    candidateFamilyKey: candidateFamilyKeys[0] || null,
    candidateFamilyKeys,
    dedupeCluster: {
      strategy: clusterInfo.strategy,
      size: sorted.length,
      workspaceKey: clusterInfo.workspaceKey || null,
      port: resolvedPort || clusterInfo.port || null,
      familyKey: clusterInfo.familyKey || null,
      health: health.checked ? health : null,
      conflictingNames: distinctNames.length > 1 ? distinctNames : [],
    },
    _configCandidates: sorted,
  };

  if (health.checked) {
    cluster.gatewayHealth = health.statusCode ? `${health.statusCode}${health.statusText ? ` ${health.statusText}` : ''}`.trim() : health.statusText;
  }

  const runtime = classifyRuntimeForCluster({ ...cluster, configCandidates: sorted }, services, docker, processes, ctx);
  cluster.runtimeType = runtime.runtimeType;
  cluster.runtimeConfidence = runtime.runtimeConfidence;
  cluster.runtimeScores = runtime.runtimeScores;
  cluster.runtimeEvidence = runtime.runtimeEvidence;

  cluster.evidence = Array.from(new Set([
    ...(cluster.evidence || []),
    clusterInfo.strategy === 'workspace_port' ? 'clustered_from_config_candidates_by_workspace_port' : `clustered_from_config_candidates_by_${clusterInfo.strategy}`,
    ...(health.live ? ['cluster_port_healthy_200'] : []),
  ]));

  delete cluster._clusterInfo;
  return cluster;
}

function buildClusterPathSet(cluster) {
  const values = new Set();
  if (cluster.openclawConfigPath) values.add(normalizePathKey(cluster.openclawConfigPath));
  for (const p of cluster.configCandidatePaths || []) {
    const key = normalizePathKey(p);
    if (key) values.add(key);
  }
  return Array.from(values).filter(Boolean);
}

function maxSharedPathPrefixBetweenClusters(a, b) {
  let best = 0;
  for (const ap of buildClusterPathSet(a)) {
    for (const bp of buildClusterPathSet(b)) {
      best = Math.max(best, sharedPathPrefixDepth(ap, bp));
    }
  }
  return best;
}

function normalizeClusterNameValue(cluster) {
  const raw = cluster.instanceName || cluster.identityNameExtracted || null;
  return raw ? String(raw).trim().toLowerCase() : null;
}

function validClusterPort(cluster) {
  const port = Number(cluster.dashboardPort || cluster.dedupeCluster?.port || 0);
  return Number.isFinite(port) && port > 0 ? port : null;
}

function computeClusterActionability(cluster) {
  let score = 0;
  const reasons = [];
  const add = (points, reason) => {
    score += Number(points || 0);
    reasons.push({ points: Number(points || 0), reason });
  };

  if (cluster.exists) add(20, 'config_exists');
  if (cluster.dedupeCluster?.health?.live) add(120, 'healthy_gateway');
  else if (validClusterPort(cluster)) add(40, 'port_detected');

  if (cluster.workspacePath) add(90, 'workspace_resolved');
  if (cluster.identityPath || cluster.identityNameExtracted) add(35, 'identity_resolved');

  if (cluster.confidence === 'attach-ready') add(80, 'attach_ready');
  else if (cluster.confidence === 'partial') add(20, 'partial_record');

  const runtimeConfidenceRank = { high: 40, medium: 20, low: 8, unknown: 0 };
  add(runtimeConfidenceRank[cluster.runtimeConfidence] || 0, `runtime_${cluster.runtimeConfidence || 'unknown'}`);

  if (cluster.candidateCanonicalLike) add(20, 'canonical_primary_candidate');
  if (cluster.candidateBackupLike) add(-80, 'backup_like_primary_candidate');
  if ((cluster.configCandidateCount || 0) > 1) add(10, 'multiple_supporting_candidates');

  return { score, reasons };
}

function applyClusterActionability(cluster) {
  const actionability = computeClusterActionability(cluster);
  cluster.actionabilityScore = actionability.score;
  cluster.actionabilityEvidence = actionability.reasons;
  return cluster;
}

function shouldReconcilePartialClusters(a, b) {
  if (!a?.exists || !b?.exists) return { merge: false, score: 0, reasons: ['nonexistent_cluster'] };
  if ((a.dedupeKey || '') === (b.dedupeKey || '')) return { merge: false, score: 0, reasons: ['same_cluster'] };

  const aWorkspace = a.normalizedWorkspaceKey || normalizeWorkspaceKey(a.workspacePath);
  const bWorkspace = b.normalizedWorkspaceKey || normalizeWorkspaceKey(b.workspacePath);
  const aPort = validClusterPort(a);
  const bPort = validClusterPort(b);
  const aName = normalizeClusterNameValue(a);
  const bName = normalizeClusterNameValue(b);

  if (aWorkspace && bWorkspace && aWorkspace !== bWorkspace) return { merge: false, score: 0, reasons: ['workspace_conflict'] };
  if (aPort && bPort && aPort !== bPort) return { merge: false, score: 0, reasons: ['port_conflict'] };
  if (aName && bName && aName !== bName) return { merge: false, score: 0, reasons: ['identity_conflict'] };

  const aFamilies = new Set((a.candidateFamilyKeys || [a.candidateFamilyKey]).filter(Boolean));
  const bFamilies = new Set((b.candidateFamilyKeys || [b.candidateFamilyKey]).filter(Boolean));
  const sharedFamilies = Array.from(aFamilies).filter(x => bFamilies.has(x));
  const sameWorkspace = Boolean(aWorkspace && bWorkspace && aWorkspace === bWorkspace);
  const samePort = Boolean(aPort && bPort && aPort === bPort);
  const oneMissingWorkspace = Boolean((aWorkspace && !bWorkspace) || (!aWorkspace && bWorkspace));
  const oneMissingPort = Boolean((aPort && !bPort) || (!aPort && bPort));
  const aMissingCriticals = !aWorkspace && !aPort;
  const bMissingCriticals = !bWorkspace && !bPort;
  const sameGatewayMode = Boolean(a.gatewayMode && b.gatewayMode && a.gatewayMode === b.gatewayMode);
  const sharedPrefixDepth = maxSharedPathPrefixBetweenClusters(a, b);

  if ((aMissingCriticals || bMissingCriticals) && !samePort && !sameWorkspace) {
    return { merge: false, score: 0, reasons: ['insufficient_bridge_fields'] };
  }

  let score = 0;
  const reasons = [];
  const add = (points, reason) => {
    score += Number(points || 0);
    reasons.push(reason);
  };

  if (samePort) add(3, 'same_port');
  if (sameWorkspace) add(3, 'same_workspace');
  if (sharedFamilies.length) add(3, 'shared_candidate_family');
  if (oneMissingWorkspace) add(1, 'bridges_missing_workspace');
  if (oneMissingPort) add(1, 'bridges_missing_port');
  if (sameGatewayMode) add(1, 'same_gateway_mode');
  if (sharedPrefixDepth >= 4) add(2, 'strong_path_prefix_match');
  else if (sharedPrefixDepth >= 3) add(1, 'moderate_path_prefix_match');
  if ((a.dedupeCluster?.health?.live || b.dedupeCluster?.health?.live) && samePort) add(1, 'healthy_port_support');

  const partialBridge = oneMissingWorkspace || oneMissingPort || !aName || !bName;
  return {
    merge: partialBridge && score >= 6,
    score,
    reasons,
  };
}

function mergeClusterPair(a, b, services, docker, processes, ctx, reconcileInfo) {
  const mergedCandidates = collapseSameConfigPath([...(a._configCandidates || []), ...(b._configCandidates || [])]);
  const clusterInfo = deriveClusterInfoFromCandidates(mergedCandidates);
  const group = mergedCandidates.map(candidate => ({ ...candidate, _clusterInfo: clusterInfo }));
  const merged = buildInstanceClusterFromGroup(clusterInfo.key, group, services, docker, processes, ctx);
  merged.reconciledFromDedupeKeys = Array.from(new Set([
    ...((a.reconciledFromDedupeKeys && a.reconciledFromDedupeKeys.length) ? a.reconciledFromDedupeKeys : [a.dedupeKey]),
    ...((b.reconciledFromDedupeKeys && b.reconciledFromDedupeKeys.length) ? b.reconciledFromDedupeKeys : [b.dedupeKey]),
  ].filter(Boolean)));
  merged.reconciliation = { score: reconcileInfo.score, reasons: reconcileInfo.reasons };
  merged.evidence = Array.from(new Set([...(merged.evidence || []), 'reconciled_partial_clusters']));
  return applyClusterActionability(merged);
}

function stripInternalClusterFields(cluster) {
  const clean = { ...cluster };
  delete clean._configCandidates;
  return clean;
}

function reconcilePartialClusters(clusters, services, docker, processes, ctx) {
  let working = [...clusters];
  let changed = true;

  while (changed) {
    changed = false;

    outer: for (let i = 0; i < working.length; i++) {
      for (let j = i + 1; j < working.length; j++) {
        const decision = shouldReconcilePartialClusters(working[i], working[j]);
        if (!decision.merge) continue;

        const merged = mergeClusterPair(working[i], working[j], services, docker, processes, ctx, decision);
        working = working.filter((_, idx) => idx !== i && idx !== j);
        working.push(merged);
        changed = true;
        break outer;
      }
    }
  }

  return working;
}

function compareResolvedInstancesForPriority(a, b) {
  const actionabilityDiff = Number(b.actionabilityScore || 0) - Number(a.actionabilityScore || 0);
  if (actionabilityDiff) return actionabilityDiff;

  const liveDiff = Number(Boolean(b.dedupeCluster?.health?.live)) - Number(Boolean(a.dedupeCluster?.health?.live));
  if (liveDiff) return liveDiff;

  const attachDiff = Number(String(b.confidence || '') === 'attach-ready') - Number(String(a.confidence || '') === 'attach-ready');
  if (attachDiff) return attachDiff;

  const runtimeConfidenceRank = { high: 3, medium: 2, low: 1, unknown: 0 };
  const runtimeDiff = Number(runtimeConfidenceRank[b.runtimeConfidence] || 0) - Number(runtimeConfidenceRank[a.runtimeConfidence] || 0);
  if (runtimeDiff) return runtimeDiff;

  return compareConfigCandidates(a, b);
}

function selectPrimaryActionableCluster(instances) {
  const resolved = (instances || []).filter(i => i.exists);
  if (!resolved.length) return null;
  return [...resolved].sort(compareResolvedInstancesForPriority)[0] || null;
}

function buildInstanceClusters(candidates, services, docker, processes, ctx) {
  const existing = collapseSameConfigPath(candidates.filter(i => i.exists));
  const buckets = new Map();

  for (const candidate of existing) {
    const clusterInfo = buildInstanceClusterKey(candidate);
    const withCluster = { ...candidate, _clusterInfo: clusterInfo };
    if (!buckets.has(clusterInfo.key)) buckets.set(clusterInfo.key, []);
    buckets.get(clusterInfo.key).push(withCluster);
  }

  let clusters = [];
  for (const [key, group] of buckets.entries()) {
    clusters.push(applyClusterActionability(buildInstanceClusterFromGroup(key, group, services, docker, processes, ctx)));
  }

  clusters = reconcilePartialClusters(clusters, services, docker, processes, ctx)
    .map(applyClusterActionability)
    .sort(compareResolvedInstancesForPriority)
    .map(stripInternalClusterFields);

  return clusters;
}

function startCase(instances, services, docker) {
  const winner = selectPrimaryActionableCluster(instances);
  if (!winner) return 'new_openclaw';

  const type = String(winner.runtimeType || 'unknown');

  if (type === 'windows_service' || type === 'linux_systemd') return 'existing_openclaw_service_account';
  if (type === 'docker_container') return 'existing_openclaw_in_docker';
  if (type === 'windows_user' || type === 'manual_process') return 'existing_openclaw_user_account';

  if (winner.dedupeCluster?.health?.live && winner.workspacePath) return 'existing_openclaw_user_account';
  if (services.length) return 'existing_openclaw_service_account';
  if ((docker?.containers || []).some(c => (`${c.image} ${c.name}`).toLowerCase().includes('openclaw'))) return 'existing_openclaw_in_docker';
  return 'existing_openclaw_user_account';
}


function readiness(instances, deps, sc) {
  const blockers = [];
  if (deps.node.status !== 'pass') blockers.push('node_minimum_not_met');

  if (sc === 'new_openclaw') {
    return { level: blockers.length ? 'blocked' : 'attach-ready', blockers };
  }

  const readyInstance = instances.find(i => i.exists && i.workspacePath && (i.wsUrl || i.dashboardPort));
  if (!readyInstance) blockers.push('openclaw_attach_fields_incomplete');
  return { level: blockers.length ? 'blocked' : 'attach-ready', blockers };
}

function pathChecks(ctx) {
  if (PLATFORM === 'win32') {
    const user = process.env.USERPROFILE || os.homedir();
    return [
      user,
      path.join(user, '.openclaw'),
      path.join(user, 'AppData', 'Roaming', 'openclaw'),
      path.join(user, 'AppData', 'Local', 'openclaw'),
      'C:\\ProgramData\\openclaw',
    ].map(p => ({ path: p, exists: exists(p), readable: exists(p) ? canRead(p) : false, writable: exists(p) ? canWrite(p) : false }));
  }
  return [
    os.homedir(),
    '/workspace',
    '/workspace/projects',
    '/etc/openclaw',
  ].map(p => ({ path: p, exists: exists(p), readable: exists(p) ? canRead(p) : false, writable: exists(p) ? canWrite(p) : false }));
}

function portFree(p) {
  if (PLATFORM === 'win32') {
    const r = runPwsh(`Get-NetTCPConnection -LocalPort ${p} -ErrorAction SilentlyContinue | Select-Object -First 1`, {
      area: 'port_probe',
      tool: 'powershell',
      missingToolMessage: 'Windows port availability probe requires PowerShell and was skipped because it was not available.',
    });
    return !r.out;
  }
  if (PLATFORM === 'darwin') {
    const r = run('lsof', [`-iTCP:${p}`, '-sTCP:LISTEN', '-n', '-P'], 6000, {
      area: 'port_probe',
      tool: 'lsof',
      missingToolMessage: 'Port availability probe requires lsof and could not run because it was not available.',
    });
    const lines = String(r.out || '').split('\n').filter(Boolean);
    return lines.length <= 1;
  }
  const r = run('ss', ['-ltn', `sport = :${p}`], 6000, {
    area: 'port_probe',
    tool: 'ss',
    missingToolMessage: 'Port availability probe requires ss and could not run because it was not available.',
  });
  const lines = String(r.out || '').split('\n').filter(Boolean);
  return lines.length <= 1;
}

function ports(preferred = 18820) {
  const fallback = [18821, 18822, 18823, 18824, 18825];
  const preferredAvailable = portFree(preferred);
  let selected = preferred;
  if (!preferredAvailable) for (const p of fallback) { if (portFree(p)) { selected = p; break; } }
  return { preferred, fallback, preferredAvailable, selected };
}

function reportHealthSummary(cluster) {
  const health = cluster?.dedupeCluster?.health || null;
  if (!health) return null;
  return {
    live: Boolean(health.live),
    statusCode: Number.isFinite(Number(health.statusCode)) ? Number(health.statusCode) : null,
    statusText: health.statusText || null,
    endpoint: health.endpoint || null,
  };
}

function reportInstance(cluster) {
  if (!cluster) return null;
  return {
    id: cluster.dedupeKey || null,
    name: cluster.instanceName || cluster.identityNameExtracted || null,
    runtimeType: cluster.runtimeType || 'unknown',
    runtimeConfidence: cluster.runtimeConfidence || 'unknown',
    confidence: cluster.confidence || 'partial',
    actionabilityScore: Number(cluster.actionabilityScore || 0),
    exists: Boolean(cluster.exists),
    openclawConfigPath: cluster.openclawConfigPath || null,
    workspacePath: cluster.workspacePath || null,
    identityPath: cluster.identityPath || null,
    dashboardPort: validClusterPort(cluster),
    gatewayMode: cluster.gatewayMode || null,
    gatewayHealth: reportHealthSummary(cluster),
    canonicalConfig: Boolean(cluster.candidateCanonicalLike),
    backupLike: Boolean(cluster.candidateBackupLike),
    configCandidateCount: Number(cluster.configCandidateCount || 0),
    relatedConfigPaths: Array.from(new Set(cluster.additionalConfigPaths || [])),
    reconciliation: cluster.reconciliation ? {
      merged: true,
      score: Number(cluster.reconciliation.score || 0),
      reasons: cluster.reconciliation.reasons || [],
      sourceClusterKeys: cluster.reconciledFromDedupeKeys || [],
    } : null,
  };
}

function buildProbeStrategySummary({ processes, processResolved, targeted, dockerResolved, deepEnabled, deepFound, directedConfigPath = null }) {
  const directed = safeAbsolutePath(directedConfigPath);
  return {
    preferredOrder: directed
      ? ['directed_config_path', 'process_runtime_signals_for_context']
      : ['process_runtime_signals', 'targeted_known_locations', 'docker_host_mounts', 'deep_search_opt_in'],
    processFirstPreferred: !directed,
    directedConfigPath: directed,
    runningProcessCount: Array.isArray(processes) ? processes.length : 0,
    processResolvedConfigCount: Array.isArray(processResolved) ? processResolved.length : 0,
    targetedConfigCount: Array.isArray(targeted) ? targeted.length : 0,
    dockerResolvedConfigCount: Array.isArray(dockerResolved) ? dockerResolved.length : 0,
    deepSearchEnabled: Boolean(deepEnabled),
    deepSearchConfigCount: Array.isArray(deepFound) ? deepFound.length : 0,
    processFirstExplanation: directed
      ? 'A user-supplied config path was inspected directly for this recovery run. Broader filesystem discovery was skipped so the check stays focused on the chosen target.'
      : 'Live process/service/container signals are probed first and used to resolve config/workspace targets before broader filesystem fallback runs. Deep search stays opt-in and bounded.',
  };
}

function safeAbsolutePath(p) {
  if (!p) return null;
  try {
    const resolved = path.resolve(String(p));
    return path.isAbsolute(resolved) ? resolved : null;
  } catch {
    return null;
  }
}

function deriveInstallRoot(cluster) {
  const configPath = safeAbsolutePath(cluster?.openclawConfigPath);
  const workspacePath = safeAbsolutePath(cluster?.workspacePath);
  const familyKey = safeAbsolutePath(cluster?.candidateFamilyKey);

  if (familyKey) return familyKey;
  if (configPath) {
    const normalized = normalizePathKey(configPath) || '';
    if (/[\\/]gateway[\\/]config[\\/]openclaw\.json$/i.test(normalized)) return path.dirname(path.dirname(configPath));
    if (/[\\/]config[\\/]openclaw\.json$/i.test(normalized)) return path.dirname(path.dirname(configPath));
    if (/[\\/]state[\\/]openclaw\.json$/i.test(normalized)) return path.dirname(path.dirname(configPath));
    if (/[\\/]\.openclaw[\\/]openclaw\.json$/i.test(normalized)) return path.dirname(path.dirname(configPath));
    return path.dirname(configPath);
  }
  if (workspacePath) return path.dirname(workspacePath);
  return null;
}

function runtimeKindForOption(cluster) {
  const runtimeType = String(cluster?.runtimeType || 'unknown');
  const map = {
    windows_service: 'windows-service',
    windows_user: 'user-process',
    docker_container: 'docker',
    linux_systemd: 'linux-systemd',
    manual_process: 'manual-process',
    unknown: 'unknown',
  };
  return map[runtimeType] || runtimeType;
}

function selectionConfidenceForOption(cluster, optionType) {
  if (optionType === 'new') return 'new';
  if (optionType === 'manual') return 'manual';
  const raw = String(cluster?.confidence || 'partial');
  if (raw === 'attach-ready') return 'high';
  if (raw === 'partial') return optionType === 'possibleMatch' ? 'low' : 'medium';
  if (raw === 'blocked') return 'low';
  return raw;
}

function buildExistingDisplayLabel(cluster) {
  const configPath = safeAbsolutePath(cluster?.openclawConfigPath);
  const workspacePath = safeAbsolutePath(cluster?.workspacePath);
  const name = cluster?.instanceName || cluster?.identityNameExtracted || null;
  if (name && workspacePath) return `${name} at ${workspacePath}`;
  if (name && configPath) return `${name} at ${configPath}`;
  if (workspacePath) return `OpenClaw at ${workspacePath}`;
  if (configPath) return `OpenClaw at ${configPath}`;
  return name || 'Detected OpenClaw instance';
}

function summarizeEvidence(cluster) {
  const bits = [];
  if (cluster?.dedupeCluster?.health?.live) bits.push('healthy local gateway responded');
  else if (validClusterPort(cluster)) bits.push(`dashboard port ${validClusterPort(cluster)} detected`);
  if (cluster?.workspacePath) bits.push('workspace resolved');
  if (cluster?.identityNameExtracted) bits.push('identity name resolved');
  if (cluster?.runtimeConfidence && cluster.runtimeConfidence !== 'unknown') bits.push(`runtime confidence ${cluster.runtimeConfidence}`);
  if (cluster?.configCandidateCount > 1) bits.push(`${cluster.configCandidateCount} related config candidates`);
  return bits.length ? bits.join('; ') : 'detected from config/runtime evidence';
}

function isStrongExistingOption(cluster) {
  if (!cluster?.exists) return false;
  if (cluster.candidateBackupLike) return false;
  if (cluster.dedupeCluster?.health?.live) return true;
  if (String(cluster.confidence) === 'attach-ready') return true;
  if (String(cluster.runtimeConfidence) === 'high' || String(cluster.runtimeConfidence) === 'medium') return true;
  return Number(cluster.actionabilityScore || 0) >= 120;
}

function buildOptionFromCluster(cluster, { recommended = false, optionType = 'existing' } = {}) {
  const isPossibleMatch = optionType === 'possibleMatch';
  const configPath = safeAbsolutePath(cluster?.openclawConfigPath);
  const workspacePath = safeAbsolutePath(cluster?.workspacePath);
  const installRoot = deriveInstallRoot(cluster);
  const running = Boolean(cluster?.dedupeCluster?.health?.live || String(cluster?.runtimeType || '') === 'windows_service' || String(cluster?.runtimeType || '') === 'linux_systemd' || String(cluster?.runtimeType || '') === 'docker_container' || String(cluster?.runtimeType || '') === 'manual_process');
  const warnings = [];

  if (isPossibleMatch) warnings.push('Detection confidence is lower. Review paths before selecting this target.');
  if (cluster?.candidateBackupLike) warnings.push('Primary config path looks backup/archive-like.');
  if (!configPath) warnings.push('No absolute config path was resolved yet.');

  return {
    optionId: `detected:${cluster?.dedupeKey || normalizePathKey(cluster?.openclawConfigPath) || Math.random().toString(36).slice(2)}`,
    optionType,
    sourceInstanceId: cluster?.dedupeKey || null,
    sortGroup: recommended ? 'recommendedExisting' : (isPossibleMatch ? 'possibleMatches' : 'otherExisting'),
    title: isPossibleMatch ? 'Possible existing install match' : 'Install over existing OpenClaw instance',
    displayLabel: buildExistingDisplayLabel(cluster),
    summary: isPossibleMatch
      ? 'This looks like an existing install, but the evidence is incomplete or weaker than the stronger matches above.'
      : (running
        ? 'Reuse this detected OpenClaw install target. It appears to be active or strongly linked to a live runtime.'
        : 'Reuse this detected OpenClaw install target. It appears real, but is not currently confirmed as running.'),
    recommended: Boolean(recommended),
    isRunning: running,
    runtimeKind: runtimeKindForOption(cluster),
    confidence: selectionConfidenceForOption(cluster, optionType),
    warningLevel: isPossibleMatch || warnings.length ? 'warning' : 'none',
    configPath,
    workspacePath,
    installRoot,
    evidenceSummary: summarizeEvidence(cluster),
    gatewayPort: validClusterPort(cluster),
    gatewayUrl: cluster?.wsUrl || null,
    processInfo: null,
    serviceInfo: null,
    dockerInfo: cluster?.runtimeType === 'docker_container' ? { runtimeType: cluster.runtimeType } : null,
    notes: cluster?.reconciliation?.merged ? ['Merged from multiple partial detector clusters.'] : [],
    warnings,
    badges: [
      ...(recommended ? ['Recommended'] : []),
      ...(isPossibleMatch ? ['Possible match'] : []),
      ...(running ? ['Running'] : ['Not running']),
    ],
    details: {
      instanceName: cluster?.instanceName || cluster?.identityNameExtracted || null,
      configCandidateCount: Number(cluster?.configCandidateCount || 0),
      actionabilityScore: Number(cluster?.actionabilityScore || 0),
      runtimeConfidence: cluster?.runtimeConfidence || 'unknown',
      candidateFamilyKey: safeAbsolutePath(cluster?.candidateFamilyKey),
    },
  };
}

function buildInstallerOptions(instanceClusters) {
  const clusters = Array.isArray(instanceClusters) ? [...instanceClusters] : [];
  const primary = selectPrimaryActionableCluster(clusters);
  const primaryKey = primary?.dedupeKey || null;
  const strong = clusters.filter(isStrongExistingOption);
  const weak = clusters.filter(cluster => !isStrongExistingOption(cluster));
  const options = [];

  if (primary && isStrongExistingOption(primary)) {
    options.push(buildOptionFromCluster(primary, { recommended: true, optionType: 'existing' }));
  }

  for (const cluster of strong) {
    if ((cluster?.dedupeKey || null) === primaryKey) continue;
    options.push(buildOptionFromCluster(cluster, { recommended: false, optionType: 'existing' }));
  }

  for (const cluster of weak) {
    options.push(buildOptionFromCluster(cluster, { recommended: false, optionType: 'possibleMatch' }));
  }

  options.push({
    optionId: 'new-install',
    optionType: 'new',
    sortGroup: 'newInstall',
    title: 'Start a new install',
    displayLabel: 'Create a fresh ResonantOS / OpenClaw install',
    summary: 'Set up a new install target instead of reusing a detected existing instance.',
    recommended: false,
    isRunning: false,
    runtimeKind: 'new-install',
    confidence: 'new',
    warningLevel: 'info',
    configPath: null,
    workspacePath: null,
    installRoot: null,
    evidenceSummary: 'Always available option for a clean install path.',
    gatewayPort: null,
    gatewayUrl: null,
    processInfo: null,
    serviceInfo: null,
    dockerInfo: null,
    notes: [],
    warnings: [],
    badges: ['New install'],
    details: {},
  });

  options.push({
    optionId: 'manual-existing-target',
    optionType: 'manual',
    sortGroup: 'manualExisting',
    title: 'Choose an existing install path manually',
    displayLabel: 'Manually point the installer at an existing OpenClaw target',
    summary: 'Use this if detection missed your install or if you want to verify the target paths yourself.',
    recommended: false,
    isRunning: false,
    runtimeKind: 'manual-existing-target',
    confidence: 'manual',
    warningLevel: 'info',
    configPath: null,
    workspacePath: null,
    installRoot: null,
    evidenceSummary: 'Always available manual existing-target selection option.',
    gatewayPort: null,
    gatewayUrl: null,
    processInfo: null,
    serviceInfo: null,
    dockerInfo: null,
    notes: [],
    warnings: ['User-supplied paths still need normalization and validation before install actions.'],
    badges: ['Manual'],
    details: {},
  });

  return options;
}

function buildInstallerOptionSummary(options) {
  const list = Array.isArray(options) ? options : [];
  return {
    total: list.length,
    recommendedOptionId: list.find(option => option.recommended)?.optionId || null,
    recommendedCount: list.filter(option => option.recommended).length,
    existingCount: list.filter(option => option.optionType === 'existing').length,
    possibleMatchCount: list.filter(option => option.optionType === 'possibleMatch').length,
    newCount: list.filter(option => option.optionType === 'new').length,
    manualCount: list.filter(option => option.optionType === 'manual').length,
  };
}

function buildConfirmedSelection(option, { confirmedByUser = false } = {}) {
  if (!option) return null;
  return {
    selectionType: option.optionType === 'possibleMatch' ? 'existing' : option.optionType,
    selectedOptionId: option.optionId,
    displayLabel: option.displayLabel,
    configPath: safeAbsolutePath(option.configPath),
    workspacePath: safeAbsolutePath(option.workspacePath),
    installRoot: safeAbsolutePath(option.installRoot),
    runtimeKind: option.runtimeKind || 'unknown',
    isRunning: Boolean(option.isRunning),
    confidence: option.confidence || 'unknown',
    confirmedByUser: Boolean(confirmedByUser),
  };
}

function resolveConfirmedSelection(options, selectedOptionId) {
  if (!selectedOptionId) return null;
  const selected = (options || []).find(option => option.optionId === selectedOptionId);
  return selected ? buildConfirmedSelection(selected, { confirmedByUser: true }) : null;
}

function reportSummary({ instances, configCandidatesRaw, recommendations, startCase, readiness, probeStrategy, probeDiagnostics, installerOptions }) {
  const existingCandidates = (configCandidatesRaw || []).filter(c => c.exists);
  const primary = selectPrimaryActionableCluster(instances || []);
  const optionSummary = buildInstallerOptionSummary(installerOptions);
  return {
    startCase,
    readinessLevel: readiness.level,
    blockers: readiness.blockers,
    primaryInstanceId: primary?.dedupeKey || null,
    existingConfigCandidateCount: existingCandidates.length,
    resolvedInstanceCount: (instances || []).length,
    healthyInstanceCount: (instances || []).filter(i => Boolean(i.dedupeCluster?.health?.live)).length,
    recommendationCount: (recommendations || []).length,
    installerOptionCount: optionSummary.total,
    installerRecommendedOptionId: optionSummary.recommendedOptionId,
    installerPossibleMatchCount: optionSummary.possibleMatchCount,
    processFirstPreferred: Boolean(probeStrategy?.processFirstPreferred),
    runningProcessCount: Number(probeStrategy?.runningProcessCount || 0),
    processResolvedConfigCount: Number(probeStrategy?.processResolvedConfigCount || 0),
    missingToolWarningCount: (probeDiagnostics || []).filter(d => d.severity === 'warning' && d.tool).length,
  };
}

function buildDebugReport({ probePaths, services, processes, docker, configCandidatesRaw, instanceClusters, windowsCapabilities, pathChecks, ports, probeStrategy, probeDiagnostics }) {
  return {
    probeStrategy,
    probeDiagnostics,
    probePaths,
    services,
    processes,
    docker,
    configCandidatesRaw,
    instanceClusters,
    windowsCapabilities,
    pathChecks,
    ports,
  };
}

function markdown(rep) {
  const l = [];
  l.push('# OpenClaw / ResonantOS Detection Report (v3)');
  l.push('');
  l.push(`Generated: ${rep.generatedAt}`);
  l.push(`Host: ${rep.environment.hostname}`);
  l.push(`OS: ${rep.environment.os} (${rep.environment.arch})`);
  l.push(`Execution context: ${rep.environment.executionContext}`);
  l.push('');

  l.push('## Overview');
  l.push(`- status: ${rep.status}`);
  l.push(`- start-case: ${rep.startCase}`);
  l.push(`- readiness: ${rep.readiness.level}`);
  l.push(`- blockers: ${rep.readiness.blockers.length ? rep.readiness.blockers.join(', ') : 'none'}`);
  l.push(`- detection strategy: process-first preferred, deep search ${rep.probeStrategy?.deepSearchEnabled ? 'enabled' : 'disabled'}`);
  l.push(`- running processes seen: ${rep.probeStrategy?.runningProcessCount || 0}`);
  l.push(`- configs resolved directly from processes: ${rep.probeStrategy?.processResolvedConfigCount || 0}`);
  l.push(`- resolved instances: ${rep.summary.resolvedInstanceCount}`);
  l.push(`- healthy instances: ${rep.summary.healthyInstanceCount}`);
  l.push(`- config candidates seen: ${rep.summary.existingConfigCandidateCount}`);
  l.push(`- missing-tool warnings: ${rep.summary.missingToolWarningCount || 0}`);
  l.push('');

  if (rep.primaryInstance) {
    const p = rep.primaryInstance;
    l.push('## Primary Instance');
    l.push(`- name: ${p.name || 'unknown'}`);
    l.push(`- runtime: ${p.runtimeType} (${p.runtimeConfidence})`);
    l.push(`- actionability: ${p.actionabilityScore}`);
    l.push(`- config: ${p.openclawConfigPath || 'n/a'}`);
    l.push(`- workspace: ${p.workspacePath || 'n/a'}`);
    l.push(`- gateway: port=${p.dashboardPort || 'n/a'} mode=${p.gatewayMode || 'n/a'} health=${p.gatewayHealth ? `${p.gatewayHealth.statusCode || 'n/a'} ${p.gatewayHealth.statusText || ''}`.trim() : 'n/a'}`);
    if (p.reconciliation?.merged) {
      l.push(`- reconciliation: merged (${p.reconciliation.reasons.join(', ') || 'unspecified'})`);
    }
    l.push('');
  }

  l.push('## Dependencies');
  for (const [k, d] of Object.entries(rep.dependencies)) {
    l.push(`- ${k}: ${d.status} (${d.version || 'n/a'})`);
  }
  l.push('');

  l.push('## Probe Notes');
  l.push(`- strategy: ${rep.probeStrategy?.processFirstExplanation || 'n/a'}`);
  if (!rep.probeDiagnostics?.length) {
    l.push('- missing tooling observed: none');
  } else {
    rep.probeDiagnostics.forEach(diag => {
      l.push(`- [${diag.severity}] ${diag.message}${diag.tool ? ` (tool=${diag.tool})` : ''}`);
    });
  }
  l.push('');

  l.push('## Resolved Instances');
  if (!rep.instances.length) l.push('- none');
  rep.instances.forEach((i, idx) => {
    l.push(`- [${idx + 1}] ${i.name || 'unknown'} -> runtime=${i.runtimeType} (${i.runtimeConfidence}), actionability=${i.actionabilityScore}`);
    l.push(`  - config: ${i.openclawConfigPath || 'n/a'}`);
    l.push(`  - workspace: ${i.workspacePath || 'n/a'}`);
    l.push(`  - gateway: port=${i.dashboardPort || 'n/a'} mode=${i.gatewayMode || 'n/a'} health=${i.gatewayHealth ? `${i.gatewayHealth.statusCode || 'n/a'} ${i.gatewayHealth.statusText || ''}`.trim() : 'n/a'}`);
    l.push(`  - related configs: ${i.relatedConfigPaths.length}`);
    if (i.reconciliation?.merged) l.push(`  - reconciled: yes (${i.reconciliation.reasons.join(', ') || 'unspecified'})`);
  });
  l.push('');

  l.push('## Installer Options');
  if (!rep.installerOptions?.length) l.push('- none');
  rep.installerOptions?.forEach(option => {
    const badgeText = Array.isArray(option.badges) && option.badges.length ? ` [${option.badges.join(', ')}]` : '';
    l.push(`- ${option.title}${badgeText}`);
    l.push(`  - Label: ${option.displayLabel}`);
    l.push(`  - Summary: ${option.summary}`);
    if (option.configPath) l.push(`  - Config: ${option.configPath}`);
    if (option.workspacePath) l.push(`  - Workspace: ${option.workspacePath}`);
    if (option.installRoot) l.push(`  - Install root: ${option.installRoot}`);
  });
  l.push('');

  l.push('## Recommendations');
  if (!rep.recommendations.length) l.push('- none');
  rep.recommendations.forEach(r => {
    l.push(`- [${r.severity}] ${r.title}`);
    l.push(`  - Action: ${r.action}`);
  });
  l.push('');
  l.push('---');
  l.push('Detection-only run: no install writes, no service changes.');
  if (rep.debugIncluded) l.push('Debug payload included in JSON output.');
  return l.join('\n');
}

function buildInstallerHandoff(report, { reportPath, selectedOptionId = null } = {}) {
  const installerOptions = Array.isArray(report?.installerOptions) ? report.installerOptions : [];
  const confirmedSelection = resolveConfirmedSelection(installerOptions, selectedOptionId);
  return {
    schemaVersion: '1.1',
    generatedAt: report?.generatedAt || new Date().toISOString(),
    detectorVersion: report?.detectorVersion || 'v3-identity-runtime-dependency-gates',
    reportPath: reportPath || null,
    installerDecision: {
      availableOptions: installerOptions,
      optionSummary: buildInstallerOptionSummary(installerOptions),
      selectedOptionId: selectedOptionId || null,
      confirmedSelection: confirmedSelection || null,
    },
    report,
  };
}

function main() {
  const args = parseArgs(process.argv);
  const directedConfigPath = safeAbsolutePath(args.targetConfigPath);

  if (args.consoleOnly && args.handoffFile) {
    console.error('Cannot use --handoff-file with --console-only because no report file would be written.');
    process.exit(2);
  }

  const environment = envContext();
  const dependencies = dependencyReport();
  const services = probeServices();
  const docker = probeDocker();
  const processes = probeProcesses();
  const whereHits = directedConfigPath ? [] : probeWhereOpenclaw();
  const dockerRoots = directedConfigPath ? [] : dockerSignalRoots(docker);
  const signalRoots = directedConfigPath
    ? []
    : Array.from(new Set([...extractWindowsSignalRoots({ whereHits, services, processes }), ...dockerRoots])).sort();

  const procResolved = directedConfigPath
    ? []
    : resolveConfigCandidatesFromProcesses(processes);

  const targeted = directedConfigPath
    ? [directedConfigPath]
    : configCandidates(environment, signalRoots);
  const dockerResolved = directedConfigPath ? [] : dockerConfigCandidates(docker);
  const deep = directedConfigPath ? [] : deepSearch(args.deep, dockerRoots);
  const allConfig = Array.from(new Set([...procResolved, ...targeted, ...dockerResolved, ...deep])).sort();
  const probeStrategy = buildProbeStrategySummary({
    processes,
    processResolved: procResolved,
    targeted,
    dockerResolved,
    deepEnabled: args.deep && !directedConfigPath,
    deepFound: deep,
    directedConfigPath,
  });

  const configCandidatesRaw = buildConfigCandidates(allConfig, services, docker, processes, environment);
  const instanceClusters = buildInstanceClusters(configCandidatesRaw, services, docker, processes, environment);
  const sc = startCase(instanceClusters, services, docker);
  const ready = readiness(instanceClusters, dependencies, sc);
  const winCaps = windowsCapabilities(services, instanceClusters);
  const portPlan = ports(18820);
  const checks = pathChecks(environment);

  const recs = [];
  if (dependencies.node.status !== 'pass') recs.push({ severity: 'error', title: 'Node minimum not met', action: 'Install/upgrade Node.js to >=22.0.0' });
  if (!dependencies.docker.detected) recs.push({ severity: 'info', title: 'Docker unavailable', action: 'Use host mode or install Docker Desktop/Engine.' });
  for (const diag of probeDiagnostics.filter(d => d.severity === 'warning' && d.tool)) {
    recs.push({ severity: 'warning', title: `Probe tooling missing: ${diag.tool}`, action: diag.message });
  }
  ready.blockers.forEach(b => recs.push({ severity: 'warning', title: `Readiness blocker: ${b}`, action: 'Resolve before attach/install execution.' }));

  const installerOptions = buildInstallerOptions(instanceClusters);
  const confirmedSelection = resolveConfirmedSelection(installerOptions, args.selectedOptionId);
  const instances = instanceClusters.map(reportInstance);
  const primaryInstance = reportInstance(selectPrimaryActionableCluster(instanceClusters));
  const summary = reportSummary({
    instances: instanceClusters,
    configCandidatesRaw,
    recommendations: recs,
    startCase: sc,
    readiness: ready,
    probeStrategy,
    probeDiagnostics,
    installerOptions,
  });
  const debugPayload = buildDebugReport({
    probePaths: { processResolved: procResolved, targeted, dockerResolved, deepEnabled: args.deep, deepFound: deep, whereHits, signalRoots, dockerRoots },
    services,
    processes,
    docker,
    configCandidatesRaw,
    instanceClusters,
    windowsCapabilities: winCaps,
    pathChecks: checks,
    ports: portPlan,
    probeStrategy,
    probeDiagnostics,
  });

  const report = {
    schemaVersion: '1.3',
    detectorVersion: 'v3-identity-runtime-dependency-gates',
    generatedAt: new Date().toISOString(),
    status: recs.some(r => r.severity === 'error') ? 'error' : (recs.length ? 'ok_with_gaps' : 'ok'),
    summary,
    environment,
    dependencies,
    probeStrategy,
    probeDiagnostics,
    primaryInstance,
    instances,
    installerOptions,
    installerOptionSummary: buildInstallerOptionSummary(installerOptions),
    confirmedSelection: confirmedSelection || null,
    startCase: sc,
    readiness: ready,
    windowsCapabilities: winCaps,
    ports: portPlan,
    recommendations: recs,
    debugIncluded: Boolean(args.debugReport),
  };

  if (args.debugReport) report.debug = debugPayload;

  const md = markdown(report);

  if (!args.consoleOnly) {
    try {
      fs.mkdirSync(args.outDir, { recursive: true });
      const stamp = new Date().toISOString().replace(/[:.]/g, '-');
      const jsonPath = path.resolve(path.join(args.outDir, `install-detect-${stamp}.json`));
      fs.writeFileSync(jsonPath, JSON.stringify(report, null, 2), 'utf8');

      if (!args.jsonOnly) {
        const mdPath = path.resolve(path.join(args.outDir, `install-detect-${stamp}.md`));
        fs.writeFileSync(mdPath, md, 'utf8');
        if (!args.quiet) console.log(`Wrote Markdown: ${mdPath}`);
      }

      if (args.handoffFile) {
        fs.mkdirSync(path.dirname(args.handoffFile), { recursive: true });
        const handoff = buildInstallerHandoff(report, {
          reportPath: jsonPath,
          selectedOptionId: args.selectedOptionId || null,
        });
        fs.writeFileSync(args.handoffFile, JSON.stringify(handoff, null, 2), 'utf8');
        if (!args.quiet) console.log(`Wrote handoff: ${args.handoffFile}`);
      }

      if (!args.quiet) console.log(`Wrote JSON: ${jsonPath}`);
    } catch (error) {
      console.error('Failed to write detector output.', error.message || String(error));
      process.exit(1);
    }
  }

  if (args.userSummary) {
    const dep = report.dependencies;
    const line = (name, d) => `${name}=${d.version || 'missing'} Status ${String(d.status || '').toUpperCase()}`;
    console.log('Dependencies:');
    console.log(line('Node', dep.node));
    console.log(line('Python', dep.python));
    console.log(line('Git', dep.git));
    console.log(line('Docker', dep.docker));
    return;
  }

  if (!args.quiet) {
    console.log('\n===== HUMAN SUMMARY =====\n');
    console.log(md);
  }
}

module.exports = {
  classifyConfigCandidatePath,
  collapseSameConfigPath,
  deriveClusterInfoFromCandidates,
  deriveWorkspacePathFromConfigPath,
  buildInstanceClusters,
  compareResolvedInstancesForPriority,
  selectPrimaryActionableCluster,
  buildInstallerOptions,
  buildInstallerOptionSummary,
  buildConfirmedSelection,
  resolveConfirmedSelection,
  buildInstallerHandoff,
  reportInstance,
  reportSummary,
};

if (require.main === module) {
  main();
}

