const path = require("path");

const CODE_EXTENSIONS = new Set([
  ".py",
  ".js",
  ".ts",
  ".jsx",
  ".tsx",
  ".html",
  ".css",
  ".sh",
  ".bash",
  ".zsh",
]);

const EXCLUDED_FILENAMES = new Set([
  "TASK.md",
  "HEARTBEAT.md",
  "OPEN-ITEMS.md",
  "MEMORY.md",
]);

const DELEGATION_SKILL_PATH_HINTS = [
  "skills/delegation/SKILL.md",
  ".openclaw/workspace/skills/delegation/SKILL.md",
];

function extractFilePath(params) {
  return String(
    params?.file_path ||
    params?.path ||
    params?.file ||
    params?.filePath ||
    ""
  ).trim();
}

function normalizePath(filePath) {
  return String(filePath || "").replace(/\\/g, "/");
}

function isExcludedPath(filePath) {
  const normalized = normalizePath(filePath);
  const basename = path.basename(normalized);

  if (EXCLUDED_FILENAMES.has(basename)) return true;
  if (/(^|\/)memory(\/|$)/i.test(normalized)) return true;

  return false;
}

function isCodeFile(filePath) {
  return CODE_EXTENSIONS.has(path.extname(String(filePath || "")).toLowerCase());
}

function flattenSkillEntries(value) {
  if (!value) return [];
  if (Array.isArray(value)) return value.flatMap(flattenSkillEntries);
  if (typeof value === "string") return [value];
  if (typeof value === "object") {
    return [
      value.name,
      value.id,
      value.path,
      value.description,
      value.command,
      value.title,
    ].filter(Boolean);
  }
  return [];
}

function delegationSkillAvailable(context = {}) {
  const skillSignals = [
    context.availableSkills,
    context.availableCommands,
    context.ctx?.availableSkills,
    context.ctx?.availableCommands,
    context.event?.availableSkills,
    context.event?.availableCommands,
  ].flatMap(flattenSkillEntries);

  if (skillSignals.length === 0) return false;

  return skillSignals.some((entry) => {
    const normalized = String(entry).toLowerCase();
    return (
      normalized === "delegation" ||
      normalized.includes("skill:delegation") ||
      normalized.includes("/delegation/skill.md") ||
      normalized.includes("skills/delegation/skill.md")
    );
  });
}

function delegationSkillLoaded(context = {}) {
  if (typeof context.hasReadFile === "function") {
    return DELEGATION_SKILL_PATH_HINTS.some((hint) => context.hasReadFile(hint));
  }

  const readFiles = context.readFiles;
  if (readFiles && typeof readFiles[Symbol.iterator] === "function") {
    for (const filePath of readFiles) {
      const normalized = normalizePath(filePath).toLowerCase();
      if (DELEGATION_SKILL_PATH_HINTS.some((hint) => normalized.includes(hint.toLowerCase()))) {
        return true;
      }
    }
  }

  const history = Array.isArray(context.messageHistory) ? context.messageHistory : [];
  return history.some((message) => {
    const toolCalls = Array.isArray(message?.tool_calls) ? message.tool_calls : [];
    return toolCalls.some((toolCall) => {
      const toolName = String(toolCall?.function?.name || toolCall?.name || "").toLowerCase();
      const args = toolCall?.function?.arguments || toolCall?.arguments || {};
      const rawPath = typeof args === "string" ? args : args?.path || args?.file_path || "";
      const normalized = normalizePath(rawPath).toLowerCase();
      return toolName === "read" && DELEGATION_SKILL_PATH_HINTS.some((hint) => normalized.includes(hint.toLowerCase()));
    });
  });
}

function check(toolName, params, context = {}) {
  const normalizedTool = String(toolName || "").toLowerCase();
  if (normalizedTool !== "write" && normalizedTool !== "edit") {
    return { block: false };
  }

  const filePath = extractFilePath(params);
  if (!filePath || isExcludedPath(filePath) || !isCodeFile(filePath)) {
    return { block: false };
  }

  if (!delegationSkillAvailable(context)) {
    return { block: false };
  }

  if (delegationSkillLoaded(context)) {
    return { block: false };
  }

  const fileExtension = path.extname(filePath) || "code";
  const explainInstruction = String(context.ERROR_EXPLAIN_INSTRUCTION || "");

  return {
    block: true,
    blockReason:
      `🛡️ Skill Enforcement Gate: Delegation skill must be loaded before editing code.\n` +
      `📖 Action required: Read skills/delegation/SKILL.md before editing ${fileExtension} files\n` +
      `ℹ️ Reason: You are an orchestrator, not a coder. Delegation to Codex is mandatory for code changes.\n\n` +
      `Current file: ${filePath}\n` +
      `Load skill: Read ~/.openclaw/workspace/skills/delegation/SKILL.md` +
      explainInstruction,
  };
}

module.exports = {
  check,
  extractFilePath,
  isCodeFile,
  isExcludedPath,
  delegationSkillAvailable,
  delegationSkillLoaded,
};
