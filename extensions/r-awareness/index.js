"use strict";
/**
 * R-Awareness V3.0 — Curated SSoT Context Injector
 *
 * Modern OpenClaw plugin. Injects always-on SSoT documents + keyword-triggered
 * docs into the system prompt via `before_prompt_build` → `appendSystemContext`.
 * Compound keyword scanning: multi-word phrases only, no single common words.
 * Supports /R commands for manual doc management.
 *
 * Hook: before_prompt_build
 */

const fs = require("fs");
const path = require("path");

const DEFAULTS = {
  enabled: true,
  ssotRoot: "",
  alwaysOnDocs: [],
  tokenBudget: 25000,
  refreshEveryNTurns: 10,
  commandPrefix: "/R",
};

function log(level, msg, data) {
  const fn = level === "error" ? console.error : level === "warn" ? console.warn : console.log;
  fn(`[r-awareness] ${msg}${data ? " " + JSON.stringify(data) : ""}`);
}

function estimateTokens(text) {
  return Math.ceil((text || "").length / 4);
}

function detectLevel(relPath) {
  const m = relPath.match(/L(\d)/i);
  return m ? parseInt(m[1], 10) : 2;
}

// ---- Keyword system ----
function loadKeywordMap(extensionDir) {
  try {
    const kwPath = path.join(extensionDir, "keywords.json");
    if (!fs.existsSync(kwPath)) return [];
    const data = JSON.parse(fs.readFileSync(kwPath, "utf-8"));
    return data.keywords || [];
  } catch (e) {
    log("error", "Failed to load keywords.json", { error: e.message });
    return [];
  }
}

function scanForKeywords(text, keywordEntries) {
  if (!text || !keywordEntries.length) return [];
  const textLower = text.toLowerCase();
  const matched = new Set();
  for (const entry of keywordEntries) {
    for (const phrase of entry.phrases) {
      if (textLower.includes(phrase.toLowerCase())) {
        matched.add(entry.doc);
        break; // one phrase match is enough per entry
      }
    }
  }
  return [...matched];
}

module.exports = function rAwarenessPlugin(api) {
  if (!api || typeof api.on !== "function") return;

  const pluginCfg =
    api.pluginConfig && typeof api.pluginConfig === "object" && !Array.isArray(api.pluginConfig)
      ? api.pluginConfig
      : {};
  const cfg = { ...DEFAULTS, ...pluginCfg };

  if (!cfg.enabled) {
    log("info", "Disabled via config");
    return;
  }
  if (!cfg.ssotRoot) {
    log("error", "ssotRoot not configured — R-Awareness disabled");
    return;
  }
  if (!fs.existsSync(cfg.ssotRoot)) {
    log("error", "ssotRoot not found", { path: cfg.ssotRoot });
    return;
  }

  // ---- State ----
  let turnCount = 0;
  let lastRefreshTurn = 0;
  const extensionDir = __dirname;
  const keywordEntries = loadKeywordMap(extensionDir);

  // docPath → { content, tokens, level, source: "always-on"|"keyword"|"manual" }
  const loadedDocs = new Map();

  // ---- Doc loading ----
  function readDoc(relPath) {
    try {
      const full = path.join(cfg.ssotRoot, relPath);
      if (!fs.existsSync(full)) {
        log("warn", "Doc not found", { path: relPath });
        return null;
      }
      return fs.readFileSync(full, "utf-8");
    } catch (e) {
      log("error", "Read failed", { path: relPath, error: e.message });
      return null;
    }
  }

  function currentTokenUsage() {
    let total = 0;
    for (const [, doc] of loadedDocs) total += doc.tokens;
    return total;
  }

  function loadAlwaysOnDocs() {
    // Remove always-on and keyword docs (manual stay)
    for (const [p, doc] of loadedDocs) {
      if (doc.source !== "manual") loadedDocs.delete(p);
    }
    for (const relPath of cfg.alwaysOnDocs) {
      if (loadedDocs.has(relPath)) continue;
      const content = readDoc(relPath);
      if (!content) continue;
      const tokens = estimateTokens(content);
      if (currentTokenUsage() + tokens > cfg.tokenBudget) {
        log("warn", "Budget exceeded, skipping", { path: relPath, tokens, used: currentTokenUsage(), budget: cfg.tokenBudget });
        continue;
      }
      loadedDocs.set(relPath, { content, tokens, level: detectLevel(relPath), source: "always-on" });
    }
    lastRefreshTurn = turnCount;
    log("info", "Docs loaded", { count: loadedDocs.size, tokens: currentTokenUsage() });
  }

  function injectKeywordDocs(matchedPaths) {
    // Remove previous keyword docs (they're per-turn)
    for (const [p, doc] of loadedDocs) {
      if (doc.source === "keyword") loadedDocs.delete(p);
    }
    if (!matchedPaths.length) return;
    let injected = 0;
    for (const relPath of matchedPaths) {
      if (loadedDocs.has(relPath)) continue; // already loaded as always-on or manual
      const content = readDoc(relPath);
      if (!content) continue;
      const tokens = estimateTokens(content);
      if (currentTokenUsage() + tokens > cfg.tokenBudget) {
        log("warn", "Keyword doc skipped (budget)", { path: relPath, tokens, budget: cfg.tokenBudget });
        continue;
      }
      loadedDocs.set(relPath, { content, tokens, level: detectLevel(relPath), source: "keyword" });
      injected++;
    }
    if (injected > 0) log("info", "Keyword docs injected", { count: injected, paths: matchedPaths, totalTokens: currentTokenUsage() });
  }

  // ---- Injection builder ----
  function buildInjection() {
    if (loadedDocs.size === 0) return "";
    const docs = [...loadedDocs.entries()].sort((a, b) => a[1].level - b[1].level);
    const parts = [
      "\n<!-- R-Awareness: SSoT Context -->",
      "<r-awareness-context>",
    ];
    for (const [docPath, doc] of docs) {
      parts.push(`\n--- ${docPath} (L${doc.level}) ---`);
      parts.push(doc.content);
    }
    parts.push("\n</r-awareness-context>");
    parts.push("<!-- End R-Awareness -->\n");
    return parts.join("\n");
  }

  // ---- /R commands ----
  function processCommand(text) {
    if (!text || typeof text !== "string") return null;
    const trimmed = text.trim();
    const pfx = cfg.commandPrefix;
    if (!trimmed.startsWith(pfx + " ") && trimmed !== pfx) return null;

    const remainder = trimmed.slice(pfx.length).trim();
    if (!remainder) return processCommand(pfx + " help");
    const args = remainder.split(/\s+/);
    const cmd = args[0].toLowerCase();
    const arg = args.slice(1).join(" ");

    switch (cmd) {
      case "load": {
        if (!arg) return `Usage: ${pfx} load <path>`;
        const content = readDoc(arg);
        if (!content) return `Not found: ${arg}`;
        const tokens = estimateTokens(content);
        loadedDocs.set(arg, { content, tokens, level: detectLevel(arg), source: "manual" });
        return `Loaded: ${arg} (~${tokens} tokens)`;
      }
      case "remove": {
        if (!arg) return `Usage: ${pfx} remove <path>`;
        if (loadedDocs.has(arg)) { loadedDocs.delete(arg); return `Removed: ${arg}`; }
        return `Not loaded: ${arg}`;
      }
      case "clear": {
        for (const [p, d] of loadedDocs) { if (d.source === "manual") loadedDocs.delete(p); }
        return `Cleared manual docs. Always-on + keyword docs remain.`;
      }
      case "list": {
        if (loadedDocs.size === 0) return "No documents loaded.";
        const lines = ["Loaded documents:"];
        let total = 0;
        for (const [p, d] of loadedDocs) {
          lines.push(`  L${d.level} ${p} (~${d.tokens}t) [${d.source}]`);
          total += d.tokens;
        }
        lines.push(`Total: ${loadedDocs.size} docs, ~${total}/${cfg.tokenBudget} tokens`);
        return lines.join("\n");
      }
      case "refresh": {
        loadAlwaysOnDocs();
        return `Refreshed. ${loadedDocs.size} docs loaded.`;
      }
      case "help":
        return [
          `R-Awareness V3 commands:`,
          `  ${pfx} load <path>  — Add a doc manually`,
          `  ${pfx} remove <path> — Remove a doc`,
          `  ${pfx} clear — Clear manual docs`,
          `  ${pfx} list — Show loaded docs`,
          `  ${pfx} refresh — Force re-read from disk`,
          `  ${pfx} help — This message`,
          `Keyword scanning: ${keywordEntries.length} entries (compound phrases)`,
        ].join("\n");
      default:
        return `Unknown command: ${cmd}. Use ${pfx} help`;
    }
  }

  // ---- Initial load ----
  loadAlwaysOnDocs();
  log("info", "R-Awareness V3.0 initialized", {
    ssotRoot: cfg.ssotRoot,
    alwaysOnDocs: cfg.alwaysOnDocs.length,
    keywords: keywordEntries.length,
    tokenBudget: cfg.tokenBudget,
    refresh: cfg.refreshEveryNTurns,
  });

  // ---- Hook ----
  api.on("before_prompt_build", (event) => {
    try {
      turnCount++;
      const prompt = event.prompt || "";

      // Process /R command
      processCommand(prompt);

      // Periodic refresh of always-on docs
      if (turnCount - lastRefreshTurn >= cfg.refreshEveryNTurns) {
        loadAlwaysOnDocs();
      }

      // Keyword scanning on user message
      const matchedPaths = scanForKeywords(prompt, keywordEntries);
      injectKeywordDocs(matchedPaths);

      // Layer 2: Augmentor drift reinforcement
      const homeDir = process.env.HOME || process.env.USERPROFILE || "";
      const driftFlagPath = path.join(homeDir, ".openclaw", "workspace", ".augmentor-drift-flag");
      try {
        if (fs.existsSync(driftFlagPath)) {
          const reinforcementDocPath = "L1/SSOT-L1-AUGMENTOR-REINFORCEMENT.md";
          if (!loadedDocs.has(reinforcementDocPath)) {
            const content = readDoc(reinforcementDocPath);
            if (content) {
              const tokens = estimateTokens(content);
              loadedDocs.set(reinforcementDocPath, { content, tokens, level: 1, source: "keyword" });
              log("warn", "Augmentor drift flag found — reinforcement doc injected", { tokens });
            }
          }
          // Clear the flag after injection (one-shot)
          try { fs.unlinkSync(driftFlagPath); } catch (_) {}
        }
      } catch (e) {
        log("error", "Drift flag check failed", { error: e.message });
      }

      const injection = buildInjection();
      if (!injection) return undefined;

      return { appendSystemContext: injection };
    } catch (e) {
      log("error", "before_prompt_build error", { error: e.message });
      return undefined;
    }
  });
};
