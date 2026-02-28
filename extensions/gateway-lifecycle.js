/**
 * Gateway Lifecycle Guard — v2
 *
 * Protects gateway start/stop lifecycle operations.
 * Enforces: no stop without a timed auto-resume or maintenance mode.
 * Enforces: no start while maintenance mode is active.
 *
 * TASK-STATE.json format:
 * {
 *   "resumeMethod": "auto",        // "auto" | "manual" | "cron"
 *   "resumeAfterSeconds": 120,     // seconds until auto-restart (default 120)
 *   "reason": "overnight test"     // human-readable reason for the stop
 * }
 *
 * When resumeMethod is "auto", the extension spawns a detached background
 * process that will re-bootstrap the gateway LaunchAgent after the specified
 * delay. This process survives the gateway shutdown.
 *
 * Hook: before_tool_call
 * v2.0.0 — 2026-02-26
 */

const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");

const HOME = process.env.HOME || "";
const WORKSPACE_DIR = path.join(HOME, ".openclaw/workspace");
const MAINTENANCE_FILE = path.join(WORKSPACE_DIR, ".gateway-maintenance");
const TASK_STATE_FILE = path.join(WORKSPACE_DIR, "TASK-STATE.json");
const RESUME_SCRIPT = path.join(HOME, "resonantos-alpha/shield/scripts/gateway-resume.sh");
const LOG_FILE = path.join(HOME, "resonantos-alpha/shield/logs/gateway-lifecycle.log");

const DEFAULT_RESUME_SECONDS = 120;
const MAX_RESUME_SECONDS = 3600;
const MIN_RESUME_SECONDS = 30;

const STOP_PATTERNS = [
  /openclaw\s+gateway\s+stop/,
  /openclaw\s+gateway\s+restart/,
  /pkill.*openclaw/,
  /launchctl\s+unload.*openclaw/
];

const START_PATTERNS = [
  /openclaw\s+gateway\s+start/,
  /launchctl\s+(load|bootstrap).*openclaw/
];

function log(level, message, data) {
  const ts = new Date().toISOString();
  const entry = `[${ts}] [${level}] ${message}${data ? " " + JSON.stringify(data) : ""}`;
  try {
    const dir = path.dirname(LOG_FILE);
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
    fs.appendFileSync(LOG_FILE, entry + "\n");
  } catch (_) {}
}

function readTaskState() {
  if (!fs.existsSync(TASK_STATE_FILE)) return { valid: false };
  try {
    const raw = fs.readFileSync(TASK_STATE_FILE, "utf8");
    const parsed = JSON.parse(raw);
    if (!parsed || !parsed.resumeMethod) return { valid: false };
    let seconds = parseInt(parsed.resumeAfterSeconds, 10);
    if (isNaN(seconds) || seconds < MIN_RESUME_SECONDS) seconds = DEFAULT_RESUME_SECONDS;
    if (seconds > MAX_RESUME_SECONDS) seconds = MAX_RESUME_SECONDS;
    return {
      valid: true,
      resumeMethod: parsed.resumeMethod,
      resumeAfterSeconds: seconds,
      reason: parsed.reason || "no reason provided"
    };
  } catch (err) {
    log("WARN", "Failed to parse TASK-STATE.json", { error: err.message });
    return { valid: false };
  }
}

function scheduleAutoResume(seconds) {
  try {
    ensureResumeScript();
    const cmd = `nohup bash "${RESUME_SCRIPT}" ${seconds} >> /tmp/gateway-resume.log 2>&1 &`;
    execSync(cmd, { stdio: "ignore", timeout: 5000 });
    log("INFO", "Auto-resume scheduled: " + seconds + "s");
    return true;
  } catch (err) {
    log("ERROR", "Failed to schedule auto-resume", { error: err.message });
    return false;
  }
}

function ensureResumeScript() {
  const dir = path.dirname(RESUME_SCRIPT);
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
  const script = '#!/bin/bash\n'
    + '# Gateway Auto-Resume — spawned by gateway-lifecycle.js\n'
    + 'DELAY=${1:-' + DEFAULT_RESUME_SECONDS + '}\n'
    + 'PLIST="$HOME/Library/LaunchAgents/ai.openclaw.gateway.plist"\n'
    + 'UID_NUM=$(id -u)\n'
    + 'echo "[$(date -Iseconds)] Resume timer: ${DELAY}s" >> /tmp/gateway-resume.log\n'
    + 'sleep "$DELAY"\n'
    + 'echo "[$(date -Iseconds)] Bootstrapping gateway..." >> /tmp/gateway-resume.log\n'
    + 'launchctl bootstrap "gui/${UID_NUM}" "$PLIST" 2>> /tmp/gateway-resume.log\n'
    + 'if [ $? -ne 0 ]; then\n'
    + '  /opt/homebrew/bin/openclaw gateway start >> /tmp/gateway-resume.log 2>&1\n'
    + 'fi\n'
    + 'rm -f "' + TASK_STATE_FILE + '" 2>/dev/null\n'
    + 'echo "[$(date -Iseconds)] Resumed, TASK-STATE cleaned" >> /tmp/gateway-resume.log\n';
  fs.writeFileSync(RESUME_SCRIPT, script, { mode: 0o755 });
}

function matchesAny(command, patterns) {
  // Only test the first line of multi-line commands (heredocs, Python strings, etc.)
  const firstLine = command.split("\n")[0];
  for (const p of patterns) { if (p.test(firstLine)) return true; }
  return false;
}

module.exports = function gatewayLifecycleExtension(api) {
  log("INFO", "Gateway Lifecycle Guard v2 loaded");

  api.on("before_tool_call", (event) => {
    try {
      const { toolName, params } = event || {};
      if (toolName !== "exec") return {};
      const command = (params && typeof params.command === "string") ? params.command.trim() : "";
      if (!command) return {};

      const isStop = matchesAny(command, STOP_PATTERNS);
      const isStart = matchesAny(command, START_PATTERNS);
      if (!isStop && !isStart) return {};

      const maintenance = fs.existsSync(MAINTENANCE_FILE);

      if (isStop) {
        if (maintenance) {
          log("ALLOW", "Stop allowed (maintenance mode)");
          return {};
        }
        const state = readTaskState();
        if (!state.valid) {
          log("BLOCK", "Stop blocked: no plan");
          return {
            block: true,
            blockReason: 'Gateway stop blocked. Create TASK-STATE.json first:\n'
              + '{"resumeMethod":"auto","resumeAfterSeconds":120,"reason":"why"}\n'
              + 'Or maintenance mode: touch ~/.openclaw/workspace/.gateway-maintenance'
          };
        }
        if (state.resumeMethod === "auto") {
          if (!scheduleAutoResume(state.resumeAfterSeconds)) {
            return { block: true, blockReason: "Auto-resume scheduling failed. Cannot stop safely." };
          }
          log("ALLOW", "Stop allowed (auto-resume " + state.resumeAfterSeconds + "s)");
        } else {
          log("ALLOW", "Stop allowed (" + state.resumeMethod + ")");
        }
        return {};
      }

      if (isStart && maintenance) {
        log("BLOCK", "Start blocked: maintenance mode active");
        return {
          block: true,
          blockReason: "Gateway in maintenance mode. Remove first: rm ~/.openclaw/workspace/.gateway-maintenance"
        };
      }

      log("ALLOW", "Gateway command allowed");
      return {};
    } catch (err) {
      log("ERROR", "Guard failed open: " + err.message);
      return {};
    }
  });
};
