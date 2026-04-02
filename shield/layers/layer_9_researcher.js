const fs = require("fs");

module.exports = {
  check(tool, args, context) {
    if (!fs.existsSync(context.LOGICIAN_SOCK)) return { allow: true, tier: "allow" };

    if (tool === "exec" || tool === "sessions_spawn") {
      const textToCheck = tool === "exec"
        ? (args?.command || "")
        : (args?.task || args?.message || "");

      if (textToCheck.length > 10) {
        const lowerText = textToCheck.toLowerCase();
        const INJECTION_HINTS = ["ignore previous", "disregard", "jailbreak", "dan mode", "pretend you are", "system prompt", "reveal your"];
        const maybeInjection = INJECTION_HINTS.some((hint) => lowerText.includes(hint));

        if (maybeInjection) {
          const answers = context.queryLogician("injection_pattern(X)");
          const patterns = answers.map((answer) => {
            const match = answer.match(/injection_pattern\("(.+)"\)/);
            return match ? match[1].toLowerCase() : null;
          }).filter(Boolean);
          const matched = patterns.find((pattern) => lowerText.includes(pattern));

          if (matched) {
            context.log("BLOCK", "Logician Injection Detection", {
              tool,
              pattern: matched,
              textPreview: textToCheck.slice(0, 60),
            });
            const blockReason = `[Logician] Injection pattern detected: "${matched}". Blocked for safety.` + context.ERROR_EXPLAIN_INSTRUCTION;
            return { allow: false, reason: blockReason, tier: "block", block: true, blockReason };
          }
        }
      }
    }

    const agentId = context.ctx?.agentId || "main";
    const TOOL_MAP = {
      exec: "exec",
      write: "file_write",
      edit: "file_write",
      web_search: "brave_api",
      web_fetch: "web_fetch",
      browser: "browser",
      message: "message_send",
      tts: "tts",
      sessions_spawn: "sessions_spawn",
    };
    const logicianTool = TOOL_MAP[tool];
    if (logicianTool && agentId !== "main") {
      const proves = context.logicianProves(`can_use_tool(/${agentId}, /${logicianTool})`);
      if (!proves) {
        context.log("BLOCK", "Logician: tool not in permission set", {
          agentId,
          tool: logicianTool,
          allowed: false,
        });
        const blockReason = "Trust Level Gate: tool '" + logicianTool + "' not in permission set for agent '" + agentId + "'";
        return { allow: false, reason: blockReason, tier: "block", block: true, blocked: true, blockReason };
      }
    }

    if (tool === "sessions_spawn") {
      const targetAgent = args?.agentId || args?.runtime || "unknown";
      if (targetAgent !== "unknown") {
        const spawnAllowed = context.logicianProves(`spawn_allowed(/main, /${targetAgent})`);
        if (!spawnAllowed) {
          context.log("BLOCK", "Logician: spawn not in allowed set", { from: "main", to: targetAgent });
          const blockReason = "Spawn Permission Gate: agent 'main' cannot spawn '" + targetAgent + "'";
          return { allow: false, reason: blockReason, tier: "block", block: true, blockReason };
        }
      }
    }

    return { allow: true, tier: "allow" };
  },
};
