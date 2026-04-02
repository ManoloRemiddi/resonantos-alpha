"use strict";

const fs = require("fs");
const path = require("path");

const DEFAULT_CONFIG = { enabled: true, model: "minimax/MiniMax-M2.5", minResponseTokens: 100 };
const PI_AI_REQUIRE_PATHS = [
  "@mariozechner/pi-ai",
  "/opt/homebrew/lib/node_modules/openclaw/node_modules/@mariozechner/pi-ai",
  "/usr/local/lib/node_modules/openclaw/node_modules/@mariozechner/pi-ai",
];
const PROMPT_HEADER = "You are a philosophical heuristic auditor. Analyze the AI response against these 7 heuristics and report ONLY violations.";
const HEURISTICS = require("./heuristics.json");
let cachedPiAi = null;
let attemptedPiAiLoad = false;

function log(level, message, data) {
  const fn = level === "error" ? console.error : level === "warn" ? console.warn : console.log;
  fn(`[heuristic-auditor] ${message}${data ? ` ${JSON.stringify(data)}` : ""}`);
}

function getPiAiModule() {
  if (attemptedPiAiLoad) return cachedPiAi;
  attemptedPiAiLoad = true;
  for (const modPath of PI_AI_REQUIRE_PATHS) {
    try {
      const mod = require(modPath);
      if (mod && typeof mod.completeSimple === "function") return (cachedPiAi = mod);
    } catch (_err) {}
  }
  return null;
}

function splitProviderModel(rawModel) {
  const raw = String(rawModel || DEFAULT_CONFIG.model).trim();
  if (!raw.includes("/")) return { provider: "minimax", modelId: raw || "MiniMax-M2.5" };
  const parts = raw.split("/");
  return { provider: parts.shift() || "minimax", modelId: parts.join("/") || "MiniMax-M2.5" };
}

function getModel(piAi, provider, modelId) {
  if (piAi && typeof piAi.getModel === "function") {
    try {
      const model = piAi.getModel(provider, modelId);
      if (model) return model;
    } catch (_err) {}
  }
  return { provider, id: modelId, contextWindow: 200000, inputModalities: ["text"] };
}

function providerEnvKeys(provider) {
  const upper = String(provider || "").replace(/[^A-Za-z0-9]/g, "_").toUpperCase();
  return Array.from(new Set([`${upper}_API_KEY`, `${upper}API_KEY`, upper === "MINIMAX" ? "MINIMAX_API_KEY" : ""])).filter(Boolean);
}

function readJson(filePath) {
  try {
    return JSON.parse(fs.readFileSync(filePath, "utf8"));
  } catch (_err) {
    return null;
  }
}

function extractApiKeyFromProfile(profile) {
  if (!profile || typeof profile !== "object") return null;
  return [profile.apiKey, profile.key, profile.token, profile.credentials && profile.credentials.apiKey].find((v) => typeof v === "string" && v.trim()) || null;
}

function resolveApiKey(provider) {
  for (const envKey of providerEnvKeys(provider)) {
    if (process.env[envKey] && process.env[envKey].trim()) return process.env[envKey].trim();
  }
  const home = process.env.HOME || process.env.USERPROFILE || "";
  const authProfiles = readJson(path.join(home, ".openclaw", "agents", "main", "agent", "auth-profiles.json"));
  const profileSets = [];
  if (authProfiles && typeof authProfiles === "object") profileSets.push(authProfiles.profiles, authProfiles);
  for (const set of profileSets.filter(Boolean)) {
    for (const [name, profile] of Object.entries(set)) {
      if (!String(name).toLowerCase().includes(String(provider).toLowerCase())) continue;
      const key = extractApiKeyFromProfile(profile);
      if (key) return key.trim();
    }
  }
  const credentialsDir = path.join(home, ".openclaw", "credentials");
  try {
    for (const fileName of fs.readdirSync(credentialsDir)) {
      if (!fileName.endsWith(".json")) continue;
      const parsed = readJson(path.join(credentialsDir, fileName));
      const providerName = String(parsed && (parsed.provider || parsed.name) || "").toLowerCase();
      if (!fileName.toLowerCase().includes(String(provider).toLowerCase()) && !providerName.includes(String(provider).toLowerCase())) continue;
      const key = extractApiKeyFromProfile(parsed);
      if (key) return key.trim();
    }
  } catch (_err) {}
  return null;
}

function textFromContent(content, role) {
  if (typeof content === "string") return content.trim();
  if (!Array.isArray(content)) return "";
  return content.map((part) => {
    if (!part || typeof part !== "object") return "";
    if (part.type === "text" && typeof part.text === "string") return part.text;
    if (role === "user" && part.type === "image") return "[Image]";
    if (role === "assistant" && part.type === "toolCall") return `[Tool: ${part.name || "unknown"}]`;
    return "";
  }).filter(Boolean).join("\n").trim();
}

function findLastMessage(messages, role) {
  return Array.isArray(messages) ? messages.slice().reverse().find((msg) => msg && msg.role === role) : null;
}

function shouldSkipAudit(message, text, minResponseTokens) {
  const trimmed = String(text || "").trim();
  if (!trimmed) return true;
  if (trimmed === "HEARTBEAT_OK" || trimmed === "NO_REPLY") return true;
  if (trimmed.length < Math.max(0, Number(minResponseTokens) || DEFAULT_CONFIG.minResponseTokens) * 4) return true;
  if (/^\[(tool result|tool):/i.test(trimmed)) return true;
  const firstPart = Array.isArray(message && message.content) ? message.content.find(Boolean) : null;
  return Boolean(firstPart && firstPart.type === "toolCall");
}

function writeAuditFile(ctx, body) {
  const workspaceDir = ctx && typeof ctx.workspaceDir === "string" && ctx.workspaceDir.trim()
    ? ctx.workspaceDir
    : path.join(process.env.HOME || process.env.USERPROFILE || "", ".openclaw", "workspace");
  const filePath = path.join(workspaceDir, "HEURISTIC-AUDIT.md");
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, `# Heuristic Audit — Last Response\nAudited: ${new Date().toISOString()}\n\n${String(body || "").trim() || "NO_VIOLATIONS"}\n`, "utf8");
  // Augmentor drift flag
  const AUGMENTOR_HEURISTICS = ["surrender-without-investigation", "comfort-over-quality", "lazy-escalation", "convenience-optimization"];
  const bodyLower = String(body || "").toLowerCase();
  const driftViolations = AUGMENTOR_HEURISTICS.filter(id => bodyLower.includes(id));
  const driftFlagPath = path.join(workspaceDir, ".augmentor-drift-flag");
  if (driftViolations.length > 0) {
    try {
      fs.writeFileSync(driftFlagPath, JSON.stringify({
        timestamp: new Date().toISOString(),
        violations: driftViolations,
        detail: String(body || "").slice(0, 200)
      }), "utf8");
      log("warn", "Augmentor drift detected", { violations: driftViolations });
    } catch (e) {
      log("error", "Failed to write drift flag", { error: e.message });
    }
  } else {
    try { fs.unlinkSync(driftFlagPath); } catch (_) {}
  }
}

async function callAuditModel(modelSpec, promptText) {
  const piAi = getPiAiModule();
  if (!piAi) throw new Error("pi-ai module unavailable");
  const { provider, modelId } = splitProviderModel(modelSpec);
  const apiKey = resolveApiKey(provider);
  if (!apiKey) throw new Error(`No API key resolved for provider ${provider}`);
  const response = await piAi.completeSimple(
    getModel(piAi, provider, modelId),
    {
      systemPrompt: PROMPT_HEADER,
      messages: [{ role: "user", content: [{ type: "text", text: promptText }], timestamp: Date.now() }],
    },
    { maxTokens: 600, apiKey }
  );
  if (!response || response.stopReason === "error") throw new Error(response && response.errorMessage ? response.errorMessage : "unknown model error");
  return (Array.isArray(response.content) ? response.content : []).filter((part) => part && part.type === "text" && typeof part.text === "string").map((part) => part.text).join("\n").trim();
}

async function runAudit(api, event, ctx) {
  const config = { ...DEFAULT_CONFIG, ...(api && api.pluginConfig && typeof api.pluginConfig === "object" ? api.pluginConfig : {}) };
  if (config.enabled === false) return;
  const messages = Array.isArray(event && event.messages) ? event.messages : [];
  const human = findLastMessage(messages, "user");
  const assistant = findLastMessage(messages, "assistant");
  if (!human || !assistant) return;
  const humanText = textFromContent(human.content, "user");
  const aiText = textFromContent(assistant.content, "assistant");
  if (shouldSkipAudit(assistant, aiText, config.minResponseTokens)) return;
  const promptText = [
    "HUMAN MESSAGE:",
    humanText,
    "",
    "AI RESPONSE:",
    aiText,
    "",
    "HEURISTICS:",
    JSON.stringify(HEURISTICS, null, 2),
    "",
    "RULES:",
    "- Only report ACTUAL violations — where a heuristic clearly applied and was NOT followed",
    '- If no heuristics were relevant to this exchange, respond: "NO_VIOLATIONS"',
    "- If violations found, respond in this exact format:",
    "VIOLATION: {heuristic_id} — {one-line explanation}",
    "VIOLATION: {heuristic_id} — {one-line explanation}",
    "- Maximum 3 violations per audit",
    "- Be strict: routine operational responses (file reads, status checks, configs) rarely violate these heuristics",
    "- Only flag when the heuristic WAS relevant and WAS missed",
  ].join("\n");
  try {
    writeAuditFile(ctx, await callAuditModel(config.model, promptText));
  } catch (err) {
    const error = err && err.message ? err.message : String(err);
    log("error", "audit failed", { error, agentId: ctx && ctx.agentId });
    writeAuditFile(ctx, `AUDIT_FAILED: ${error}`);
  }
}

module.exports = function heuristicAuditorPlugin(api) {
  if (!api || typeof api.on !== "function") return;
  log("info", "loaded");
  api.on("agent_end", (event, ctx) => {
    Promise.resolve().then(() => runAudit(api, event, ctx)).catch((err) => {
      log("error", "unexpected async failure", { error: err && err.message ? err.message : String(err) });
    });
  });
};
