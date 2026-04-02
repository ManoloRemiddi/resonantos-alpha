/**
 * Usage Tracker — v1.0.0
 * Logs each LLM output event to append-only monthly JSONL.
 */
const fs = require("fs");
const path = require("path");

module.exports = function usageTrackerExtension(api) {
  let trackerDir = null;
  let announced = false;

  function resolveWorkspaceDir(ctx) {
    if (ctx && ctx.workspaceDir) return ctx.workspaceDir;
    const home = process.env.HOME || "";
    return path.join(home, ".openclaw", "workspace");
  }

  function ensureTrackerDir(ctx) {
    if (!trackerDir) {
      trackerDir = path.join(resolveWorkspaceDir(ctx), "usage-tracker");
    }
    if (!fs.existsSync(trackerDir)) {
      fs.mkdirSync(trackerDir, { recursive: true });
    }
    return trackerDir;
  }

  function monthFileFor(dir, now) {
    const d = now || new Date();
    const month = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
    return path.join(dir, `${month}.jsonl`);
  }

  function tokenCount(value) {
    const n = Number(value);
    return Number.isFinite(n) && n > 0 ? n : 0;
  }

  function deriveSessionType(sessionKey) {
    const key = String(sessionKey || "");
    if (!key) return "other";
    if (/^agent:[^:]+:main$/.test(key)) return "main";
    if (/^cron:/.test(key)) return "cron";
    if (key.includes(":group:")) return "group";

    const lower = key.toLowerCase();
    if (
      lower.includes("sub-agent") ||
      lower.includes("subagent") ||
      lower.includes(":spawn:") ||
      lower.includes("spawned") ||
      lower.includes(":child:")
    ) {
      return "subagent";
    }
    return "other";
  }

  api.on("agent_start", (_event, ctx) => {
    try {
      ensureTrackerDir(ctx);
      if (!announced) {
        announced = true;
        console.info(`[usage-tracker] INFO tracker active at ${trackerDir}`);
      }
    } catch (err) {
      try {
        console.warn(`[usage-tracker] warning init failed: ${err && err.message ? err.message : err}`);
      } catch (_) {}
    }
  });

  api.on("llm_output", (event, ctx) => {
    try {
      const dir = ensureTrackerDir(ctx);
      const usage = (event && event.usage) || {};
      const line = JSON.stringify({
        ts: new Date().toISOString(),
        runId: (event && event.runId) || null,
        sessionKey: (ctx && ctx.sessionKey) || null,
        sessionType: deriveSessionType(ctx && ctx.sessionKey),
        agentId: (ctx && ctx.agentId) || null,
        provider: (event && event.provider) || null,
        model: (event && event.model) || null,
        input: tokenCount(usage.input),
        output: tokenCount(usage.output),
        cacheRead: tokenCount(usage.cacheRead),
        cacheWrite: tokenCount(usage.cacheWrite),
        total: tokenCount(usage.total),
      });

      fs.appendFileSync(monthFileFor(dir), `${line}\n`, "utf8");
    } catch (err) {
      try {
        console.warn(`[usage-tracker] warning write failed: ${err && err.message ? err.message : err}`);
      } catch (_) {}
    }
  });
};
