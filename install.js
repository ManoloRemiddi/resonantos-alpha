#!/usr/bin/env node
// ResonantOS Alpha Installer — Cross-platform (macOS, Linux, Windows)
// Usage: npx https://github.com/ManoloRemiddi/resonantos-alpha install
//   or:  node install.js

const { execSync } = require("child_process");
const fs = require("fs");
const path = require("path");
const os = require("os");

const REPO = "https://github.com/ManoloRemiddi/resonantos-alpha.git";
const HOME = os.homedir();
const INSTALL_DIR = path.join(HOME, "resonantos-alpha");
const OPENCLAW_AGENT_DIR = path.join(HOME, ".openclaw", "agents", "main", "agent");
const OPENCLAW_WORKSPACE = path.join(HOME, ".openclaw", "workspace");

const isWin = process.platform === "win32";

function log(msg) { console.log(msg); }
function ok(msg) { log(`✓ ${msg}`); }
function fail(msg) { console.error(`ERROR: ${msg}`); process.exit(1); }

function hasCmd(cmd) {
  try {
    execSync(isWin ? `where ${cmd}` : `command -v ${cmd}`, { stdio: "ignore" });
    return true;
  } catch { return false; }
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
    ok(`${label} installed`);
  }
}

// ── Main ──

log("=== ResonantOS Alpha Installer ===\n");

// 1. Check dependencies
if (!hasCmd("git")) fail("git is required. Install: https://git-scm.com/");
if (!hasCmd("node")) fail("node is required. Install: https://nodejs.org/");
if (!hasCmd("python3") && !hasCmd("python"))
  fail("Python 3 is required. Install: https://www.python.org/");

const nodeVer = parseInt(process.versions.node.split(".")[0], 10);
if (nodeVer < 18) fail(`Node.js 18+ required (found v${process.versions.node})`);

const pip = hasCmd("pip3") ? "pip3" : hasCmd("pip") ? "pip" : null;
if (!pip) fail("pip3/pip is required (should come with Python 3).");

const python = hasCmd("python3") ? "python3" : "python";

// 2. Check/install OpenClaw
if (!hasCmd("openclaw")) {
  log("OpenClaw not found. Installing...");
  run("npm install -g openclaw");
}

ok("Dependencies OK");

// 3. Clone or pull repo
if (fs.existsSync(path.join(INSTALL_DIR, ".git"))) {
  log(`Directory ${INSTALL_DIR} exists. Pulling latest...`);
  run("git pull", { cwd: INSTALL_DIR });
} else {
  log("Cloning ResonantOS Alpha...");
  run(`git clone ${REPO} "${INSTALL_DIR}"`);
}

// 4. Copy extensions
log("Installing extensions...");
const extDir = path.join(OPENCLAW_AGENT_DIR, "extensions");
mkdirp(extDir);
copyFile(path.join(INSTALL_DIR, "extensions", "r-memory.js"), path.join(extDir, "r-memory.js"));
copyFile(path.join(INSTALL_DIR, "extensions", "r-awareness.js"), path.join(extDir, "r-awareness.js"));
copyFile(path.join(INSTALL_DIR, "extensions", "gateway-lifecycle.js"), path.join(extDir, "gateway-lifecycle.js"));
ok("Extensions installed");

// 5. SSoT template
log("Setting up SSoT documents...");
const ssotDir = path.join(OPENCLAW_WORKSPACE, "resonantos-augmentor", "ssot");
mkdirp(ssotDir);
const ssotEmpty = fs.readdirSync(ssotDir).length === 0;
if (ssotEmpty) {
  copyDirContents(path.join(INSTALL_DIR, "ssot-template"), ssotDir);
  ok("SSoT template installed");
} else {
  log("  SSoT directory not empty — skipping (won't overwrite your docs)");
}

// 6. R-Memory & R-Awareness configs
mkdirp(path.join(OPENCLAW_WORKSPACE, "r-memory"));
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
  {
    ssotRoot: "resonantos-augmentor/ssot",
    coldStartOnly: true,
    coldStartDocs: ["L1/SSOT-L1-IDENTITY-STUB.ai.md"],
    tokenBudget: 15000,
    maxDocs: 10,
    ttlTurns: 15,
  },
  "R-Awareness config"
);

writeJsonIfMissing(
  path.join(OPENCLAW_WORKSPACE, "r-memory", "config.json"),
  {
    compressTrigger: 36000,
    evictTrigger: 50000,
    blockSize: 4000,
    minCompressChars: 200,
    compressionModel: "anthropic/claude-haiku-4-5",
    maxParallelCompressions: 4,
  },
  "R-Memory config"
);

// 7. Dashboard dependencies
log("Installing dashboard dependencies...");
try {
  run(`${pip} install -q flask flask-cors psutil websocket-client`, { cwd: path.join(INSTALL_DIR, "dashboard") });
} catch {
  run(`${pip} install flask flask-cors psutil websocket-client`, { cwd: path.join(INSTALL_DIR, "dashboard") });
}
ok("Dashboard ready");

// 8. Config from example
const cfgPath = path.join(INSTALL_DIR, "dashboard", "config.json");
const cfgExample = path.join(INSTALL_DIR, "dashboard", "config.example.json");
if (!fs.existsSync(cfgPath) && fs.existsSync(cfgExample)) {
  fs.copyFileSync(cfgExample, cfgPath);
  ok("Dashboard config created from template (edit config.json with your addresses)");
}

log(`
=== Installation Complete ===

Next steps:
  1. Edit ~/resonantos-alpha/dashboard/config.json with your Solana addresses
  2. Start OpenClaw:  openclaw gateway start
  3. Start Dashboard: cd ~/resonantos-alpha/dashboard && ${python} server_v2.py
  4. Open http://localhost:19100

Docs: https://github.com/ManoloRemiddi/resonantos-alpha
`);
