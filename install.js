#!/usr/bin/env node
// ResonantOS Alpha Installer — Cross-platform (macOS, Linux, Windows)
//
// Usage:
//   1. Clone the repo: git clone https://github.com/ResonantOS/resonantos-alpha.git
//   2. cd resonantos-alpha
//   3. git checkout dev  (if you want the dev branch)
//   4. node install.js
//
// This script copies files from the LOCAL directory to ~/.openclaw/
// It does NOT clone or pull from git - that's your job before running this.

const { execSync } = require("child_process");
const https = require("https");
const fs = require("fs");
const path = require("path");
const os = require("os");

const HOME = os.homedir();
const SCRIPT_DIR = __dirname;
const OPENCLAW_AGENT_DIR = path.join(HOME, ".openclaw", "agents", "main", "agent");
const OPENCLAW_WORKSPACE = path.join(HOME, ".openclaw", "workspace");

const isWin = process.platform === "win32";

// ── Step tracking ────────────────────────────────────────────

const steps = [];
let coreFailed = false;

function log(msg) { console.log(msg); }

function step(name, fn) {
  steps.push({ name, status: "ok", detail: "" });
  const idx = steps.length - 1;
  try {
    fn();
  } catch (err) {
    steps[idx].status = "error";
    steps[idx].detail = err.message || String(err);
    if (err.core) { coreFailed = true; }
    else { log(`  Warning: ${err.message}`); }
  }
}

function warn(msg) { log(`  ⚠ ${msg}`); }

function fail(msg) { throw Object.assign(new Error(msg), { core: true }); }

function hasCmd(cmd) {
  try {
    execSync(isWin ? `where ${cmd}` : `command -v ${cmd}`, { stdio: "ignore" });
    return true;
  } catch { return false; }
}

function checkNet(url, timeoutMs = 5000) {
  return new Promise(resolve => {
    const req = https.get(url, { timeout: timeoutMs }, () => resolve(true));
    req.on("error", () => resolve(false));
    req.on("timeout", () => { req.destroy(); resolve(false); });
  });
}

function run(cmd, opts = {}) {
  return execSync(cmd, { stdio: "inherit", ...opts });
}

function mkdirp(dir) { fs.mkdirSync(dir, { recursive: true }); }

function copyFile(src, dest) {
  mkdirp(path.dirname(dest));
  fs.copyFileSync(src, dest);
}

function copyDirContents(src, dest) {
  mkdirp(dest);
  for (const entry of fs.readdirSync(src, { withFileTypes: true })) {
    const s = path.join(src, entry.name);
    const d = path.join(dest, entry.name);
    if (entry.isDirectory()) copyDirContents(s, d);
    else fs.copyFileSync(s, d);
  }
}

function writeJsonIfMissing(filePath, data, label) {
  if (!fs.existsSync(filePath)) {
    mkdirp(path.dirname(filePath));
    fs.writeFileSync(filePath, JSON.stringify(data, null, 2) + "\n");
    log(`  ✓ ${label} installed`);
  } else {
    log(`  ✓ ${label} already present — skipping`);
  }
}

// ── Preflight checks ─────────────────────────────────────────

log("=== ResonantOS Alpha Installer ===\n");

step("Node.js v18+", () => {
  const nodeVer = parseInt(process.versions.node.split(".")[0], 10);
  if (nodeVer < 18) fail(`Node.js 18+ required (found v${process.versions.node})`);
});

step("git", () => { if (!hasCmd("git")) fail("git is required. Install: https://git-scm.com"); });

const python = hasCmd("python3") ? "python3" : hasCmd("python") ? "python" : null;
step("python3 or python", () => { if (!python) fail("Python 3 is required. Install: https://www.python.org"); });

const pip = hasCmd("pip3") ? "pip3" : hasCmd("pip") ? "pip" : null;
step("pip3 or pip", () => { if (!pip) warn("pip not found — dashboard dependencies skipped. Install Python pip to enable."); });

const dockerAvailable = (() => {
  if (!hasCmd("docker")) return false;
  try { execSync("docker compose version", { stdio: "ignore" }); return true; } catch { return false; }
})();
if (dockerAvailable) {
  log("  ✓ Docker + Docker Compose detected — Docker setup available");
} else if (hasCmd("docker")) {
  log("  ⚠ Docker found but Docker Compose not available");
} else {
  log("  ⚠ Docker not found — see DOCKER.md for install instructions");
}

// Check we're in a valid repo
step("Valid ResonantOS repo", () => {
  const sourceRoot = SCRIPT_DIR;
  const requiredDirs = ["extensions", "dashboard", "workspace-templates"];
  const missing = requiredDirs.filter(d => !fs.existsSync(path.join(sourceRoot, d)));
  if (missing.length > 0) {
    fail(`Not a valid ResonantOS repo. Missing directories: ${missing.join(", ")}\n` +
         `Did you clone the repo first? Usage:\n` +
         `  git clone https://github.com/ResonantOS/resonantos-alpha.git\n` +
         `  cd resonantos-alpha\n` +
         `  node install.js`);
  }
});

step("Network (npm registry)", async () => {
  const online = await checkNet("https://registry.npmjs.org/", 5000);
  if (!online) warn("Cannot reach npm registry — openclaw install may fail");
});

// ── Installation steps ────────────────────────────────────────

step("openclaw CLI", () => {
  if (!hasCmd("openclaw")) {
    log("  openclaw not found — installing...");
    try {
      run("npm install -g openclaw");
    } catch {
      warn("Could not install openclaw globally. Run: npm install -g openclaw");
    }
  } else {
    log("  ✓ openclaw already installed");
  }
});

step("Extensions (r-memory, r-awareness, gateway-lifecycle)", () => {
  const extDir = path.join(OPENCLAW_AGENT_DIR, "extensions");
  mkdirp(extDir);
  const exts = [
    ["extensions/r-memory.js", "r-memory.js"],
    ["extensions/r-awareness.js", "r-awareness.js"],
    ["extensions/gateway-lifecycle.js", "gateway-lifecycle.js"],
  ];
  for (const [src, name] of exts) {
    const srcPath = path.join(SCRIPT_DIR, src);
    const destPath = path.join(extDir, name);
    if (fs.existsSync(srcPath)) {
      copyFile(srcPath, destPath);
      log(`  ✓ ${name}`);
    } else {
      warn(`${name} not found in extensions/`);
    }
  }
});

step("SSoT template documents", () => {
  const ssotDir = path.join(OPENCLAW_WORKSPACE, "resonantos-alpha", "ssot");
  const ssotEmpty = !fs.existsSync(ssotDir) || fs.readdirSync(ssotDir).length === 0;
  if (ssotEmpty) {
    const src = path.join(SCRIPT_DIR, "ssot", "templates");
    if (fs.existsSync(src)) {
      copyDirContents(src, ssotDir);
      log("  ✓ SSoT template installed");
    } else {
      warn("ssot/templates/ not found — skipping");
    }
  } else {
    log("  ✓ SSoT directory not empty — skipping (won't overwrite docs)");
  }
});

step("Workspace templates (AGENTS, SOUL, USER, etc.)", () => {
  const wsDir = path.join(SCRIPT_DIR, "workspace-templates");
  const templates = ["AGENTS.md", "SOUL.md", "USER.md", "MEMORY.md", "TOOLS.md", "IDENTITY.md", "HEARTBEAT.md"];
  let installed = 0;
  mkdirp(path.join(OPENCLAW_WORKSPACE, "agents"));
  for (const tpl of templates) {
    const dest = path.join(OPENCLAW_WORKSPACE, tpl);
    const src = path.join(wsDir, tpl);
    if (!fs.existsSync(dest) && fs.existsSync(src)) {
      fs.copyFileSync(src, dest);
      installed++;
    }
  }
  if (installed > 0) {
    log(`  ✓ ${installed} template(s) installed (won't overwrite existing)`);
  } else {
    log("  ✓ Templates already present — skipping");
  }
});

step("R-Awareness config", () => {
  mkdirp(path.join(OPENCLAW_WORKSPACE, "r-awareness"));
  writeJsonIfMissing(
    path.join(OPENCLAW_WORKSPACE, "r-awareness", "keywords.json"),
    {
      system: ["L1/SSOT-L1-IDENTITY-STUB.ai.md"],
      openclaw: ["L1/SSOT-L1-IDENTITY-STUB.ai.md"],
      philosophy: ["L0/PHILOSOPHY.md"],
      augmentatism: ["L0/PHILOSOPHY.md"],
      constitution: ["L0/CONSTITUTION.md"],
      architecture: ["L1/SYSTEM-ARCHITECTURE.md"],
      memory: ["L1/R-MEMORY.md"],
      awareness: ["L1/R-AWARENESS.md"],
    },
    "Default keywords"
  );
  writeJsonIfMissing(
    path.join(OPENCLAW_WORKSPACE, "r-awareness", "config.json"),
    { ssotRoot: "resonantos-alpha/ssot", coldStartOnly: true, coldStartDocs: ["L1/SSOT-L1-IDENTITY-STUB.ai.md"], tokenBudget: 15000, maxDocs: 10, ttlTurns: 15 },
    "R-Awareness config"
  );
});

step("R-Memory config", () => {
  mkdirp(path.join(OPENCLAW_WORKSPACE, "r-memory"));
  writeJsonIfMissing(
    path.join(OPENCLAW_WORKSPACE, "r-memory", "config.json"),
    { compressTrigger: 36000, evictTrigger: 50000, blockSize: 4000, minCompressChars: 200, compressionModel: "anthropic/claude-haiku-4-5", maxParallelCompressions: 4 },
    "R-Memory config"
  );
});

step("Setup Agent (onboarding)", () => {
  const setupSrc = path.join(SCRIPT_DIR, "agents", "setup");
  const setupDest = path.join(HOME, ".openclaw", "agents", "setup", "agent");
  if (fs.existsSync(setupSrc)) {
    mkdirp(setupDest);
    for (const f of fs.readdirSync(setupSrc)) {
      copyFile(path.join(setupSrc, f), path.join(setupDest, f));
    }
    log("  ✓ Setup Agent installed");
  } else {
    warn("agents/setup/ not found — skipping");
  }

  // Register setup agent in openclaw.json
  const openclawCfgPath = path.join(HOME, ".openclaw", "openclaw.json");
  if (fs.existsSync(openclawCfgPath)) {
    try {
      const cfg = JSON.parse(fs.readFileSync(openclawCfgPath, "utf-8"));
      const agentsList = cfg.agents && cfg.agents.list ? cfg.agents.list : [];
      const hasSetup = agentsList.some(a => a.id === "setup");
      if (!hasSetup) {
        const primaryModel = (cfg.agents && cfg.agents.defaults && cfg.agents.defaults.model && cfg.agents.defaults.model.primary) || "anthropic/claude-haiku-4-5";
        agentsList.push({ id: "setup", model: primaryModel });
        if (!cfg.agents) cfg.agents = {};
        cfg.agents.list = agentsList;
        fs.writeFileSync(openclawCfgPath, JSON.stringify(cfg, null, 2) + "\n");
        log("  ✓ Setup Agent registered in openclaw.json");
      } else {
        log("  ✓ Setup Agent already in openclaw.json");
      }
    } catch (e) {
      warn("Could not update openclaw.json: " + e.message);
    }
  }
});

step("Skills", () => {
  const skillsSrc = path.join(SCRIPT_DIR, "skills");
  const skillsDest = path.join(OPENCLAW_WORKSPACE, "skills");
  if (fs.existsSync(skillsSrc)) {
    for (const entry of fs.readdirSync(skillsSrc, { withFileTypes: true })) {
      if (entry.isDirectory()) {
        const src = path.join(skillsSrc, entry.name);
        const dest = path.join(skillsDest, entry.name);
        copyDirContents(src, dest);
      }
    }
    log("  ✓ Skills installed");
  } else {
    warn("skills/ not found — skipping");
  }
});

step("Dashboard Python venv and dependencies", () => {
  const dashDir = path.join(SCRIPT_DIR, "dashboard");
  const venvDir = path.join(dashDir, "venv");
  const reqFile = path.join(SCRIPT_DIR, "requirements.txt");

  if (!pip) { warn("pip not available — dashboard dependencies skipped"); return; }

  if (!fs.existsSync(venvDir)) {
    log("  Creating Python virtual environment...");
    try {
      run(`${python} -m venv "${venvDir}"`, { cwd: dashDir });
    } catch {
      warn("Could not create venv — skipping dashboard deps");
      return;
    }
  } else {
    log("  ✓ Venv already exists");
  }

  const venvPip = isWin ? path.join(venvDir, "Scripts", "pip") : path.join(venvDir, "bin", "pip");
  try {
    if (fs.existsSync(reqFile)) {
      run(`"${venvPip}" install -q -r "${reqFile}"`, { cwd: dashDir });
      log("  ✓ Dashboard dependencies installed");
    } else {
      const dashDeps = "flask flask-cors psutil websocket-client solana solders";
      run(`"${venvPip}" install -q ${dashDeps}`, { cwd: dashDir });
      log("  ✓ Dashboard dependencies installed");
    }
  } catch {
    warn("Dashboard dependencies install failed. Run manually:\n  cd dashboard && source venv/bin/activate && pip install -r ../requirements.txt");
  }
});

step("Dashboard config.json", () => {
  const cfgPath = path.join(SCRIPT_DIR, "dashboard", "config.json");
  const cfgExample = path.join(SCRIPT_DIR, "dashboard", "config.example.json");
  if (!fs.existsSync(cfgPath) && fs.existsSync(cfgExample)) {
    fs.copyFileSync(cfgExample, cfgPath);
    log("  ✓ Dashboard config created from template");
  } else if (fs.existsSync(cfgPath)) {
    log("  ✓ Dashboard config already present");
  } else {
    warn("config.example.json not found — skipping");
  }
});

// ── Docker convenience setup ─────────────────────────────────

step("Docker .env (OPENCLAW_HOME)", () => {
  const envPath = path.join(SCRIPT_DIR, ".env");
  const desired = `OPENCLAW_HOME=${HOME}`;
  try {
    if (dockerAvailable) {
      let lines = [];
      if (fs.existsSync(envPath)) {
        lines = fs.readFileSync(envPath, "utf-8").split(/\r?\n/).filter(Boolean);
        // Remove existing OPENCLAW_HOME entries
        lines = lines.filter(l => !/^OPENCLAW_HOME=/.test(l));
      }
      lines.push(desired);
      fs.writeFileSync(envPath, lines.join("\n") + "\n");
      log(`  ✓ .env updated: ${desired}`);
    } else {
      log("  ✓ Docker not detected — skipping .env creation");
    }
  } catch (e) {
    warn("Could not write .env: " + e.message);
  }
});

step("Gateway wsUrl for Docker Desktop", () => {
  const isMac = process.platform === "darwin";
  if (!(dockerAvailable && (isWin || isMac))) {
    log("  ✓ Non-Docker-Desktop platform — no wsUrl changes");
    return;
  }
  const ocPath = path.join(HOME, ".openclaw", "openclaw.json");
  if (!fs.existsSync(ocPath)) {
    log("  ✓ openclaw.json not found — skipping wsUrl update");
    return;
  }
  try {
    const cfg = JSON.parse(fs.readFileSync(ocPath, "utf-8"));
    const gw = cfg.gateway || {};
    const current = gw.wsUrl || "";
    const desired = "ws://host.docker.internal:18789";
    if (!current || /127\.0\.0\.1|localhost/.test(current)) {
      gw.wsUrl = desired;
      cfg.gateway = gw;
      fs.writeFileSync(ocPath, JSON.stringify(cfg, null, 2) + "\n");
      log(`  ✓ Updated gateway wsUrl for Docker Desktop: ${desired}`);
    } else {
      log("  ✓ gateway.wsUrl already set — skipping");
    }
  } catch (e) {
    warn("Could not update openclaw.json: " + e.message);
  }
});

// ── Post-install summary ─────────────────────────────────────

const okSteps = steps.filter(s => s.status === "ok");
const errSteps = steps.filter(s => s.status === "error");
const warnCount = steps.filter(s => s.status !== "error").length < steps.length ? (steps.filter(s => s.status === "error").length) : 0;

log(`\n${"=".repeat(50)}`);
log("Installation Summary");
log(`${"=".repeat(50)}`);

for (const s of steps) {
  if (s.status === "error") {
    log(`  ✗ ${s.name}: ${s.detail}`);
  }
}

const coreErrors = errSteps.filter(s => s.detail && !s.detail.includes("Warning"));
const optErrors = errSteps.filter(s => !coreErrors.includes(s));

if (coreFailed || coreErrors.length > 0) {
  log(`\n  ✗ Core installation FAILED`);
  if (coreErrors.length > 0) {
    for (const e of coreErrors) log(`    ${e.name}: ${e.detail}`);
  }
  log(`\n  Fix the errors above and re-run install.js`);
  process.exit(1);
} else {
  const optionalWarnings = optErrors.length;
  log(`\n  ✓ Core installation complete (${okSteps.length}/${steps.length} steps OK)`);
  if (optionalWarnings > 0) {
    log(`  ⚠ ${optionalWarnings} optional step(s) skipped (see warnings above)`);
  }
}

const nextStepsLines = [];
if (dockerAvailable) {
  nextStepsLines.push("  1. [Docker] Run: docker compose up -d");
  nextStepsLines.push("     Or native: cd dashboard && source venv/bin/activate && python server_v2.py");
} else {
  nextStepsLines.push("  1. cd dashboard && source venv/bin/activate");
  nextStepsLines.push("     python server_v2.py");
}
nextStepsLines.push("  2. Start OpenClaw:  openclaw gateway start");
nextStepsLines.push("  3. Open http://localhost:19100");
if (dockerAvailable) {
  nextStepsLines.push("");
  nextStepsLines.push("  Docker not working? See DOCKER.md for troubleshooting.");
}
log("\n" + nextStepsLines.join("\n"));
