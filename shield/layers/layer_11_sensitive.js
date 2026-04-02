module.exports = {
  check(tool, args, context) {
    if (String(context.ctx?.sessionKey || "").startsWith("agent:main:main")) {
      return { allow: true, tier: "allow" };
    }

    if (tool === "read" || tool === "write" || tool === "edit") {
      const rawPath = String(args?.file_path || args?.path || "");
      const normalizedPath = rawPath.replace(/^~(?=\/|$)/, context.HOME);

      for (const pattern of context.SENSITIVE_PATH_PATTERNS) {
        if (!pattern.test(normalizedPath)) continue;

        context.log("BLOCK", "Sensitive Path Gate", {
          tool,
          path: normalizedPath,
          sessionKey: String(context.ctx?.sessionKey || "").slice(0, 30),
          pattern: pattern.source,
        });

        const blockReason = `🔐 [Sensitive Path Gate] Blocked access to "${normalizedPath}" — credential/secret paths are restricted for sub-agents. Only the main agent can access sensitive paths.` + context.ERROR_EXPLAIN_INSTRUCTION;
        return { allow: false, reason: blockReason, tier: "block", block: true, blockReason };
      }
    }

    if (tool === "exec") {
      const rawCommand = String(args?.command || "");
      const expandedCommand = rawCommand.replace(/~/g, context.HOME);

      for (const pattern of context.SENSITIVE_PATH_PATTERNS) {
        const match = expandedCommand.match(pattern);
        if (!match) continue;

        context.log("BLOCK", "Sensitive Path Gate", {
          tool,
          path: match[0],
          sessionKey: String(context.ctx?.sessionKey || "").slice(0, 30),
          pattern: pattern.source,
        });

        const blockReason = `🔐 [Sensitive Path Gate] Blocked access to "${match[0]}" — credential/secret paths are restricted for sub-agents. Only the main agent can access sensitive paths.` + context.ERROR_EXPLAIN_INSTRUCTION;
        return { allow: false, reason: blockReason, tier: "block", block: true, blockReason };
      }
    }

    return { allow: true, tier: "allow" };
  },
};
