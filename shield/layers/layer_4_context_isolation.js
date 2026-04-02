module.exports = {
  check(tool, args, context) {
    if (tool !== "read" && tool !== "write" && tool !== "edit") {
      return { allow: true, tier: "allow" };
    }

    const filePath = args?.file_path || args?.path || "";
    const isMemoryFile = /MEMORY\.md$/i.test(filePath) || /memory\/\d{4}-\d{2}-\d{2}\.md$/i.test(filePath);
    if (!isMemoryFile) return { allow: true, tier: "allow" };

    const MEMORY_TRUSTED_AGENTS = ["main", "resonant-voice", "content-voice", "researcher", "voice"];
    const agentId = context.ctx?.agentId || "";
    if (MEMORY_TRUSTED_AGENTS.includes(agentId)) return { allow: true, tier: "allow" };

    context.log("BLOCK", "Context Isolation Gate", {
      tool,
      file: filePath.slice(-40),
      agentId,
    });

    const blockReason = `[Context Isolation Gate] Blocked ${tool} on "${filePath.split("/").pop()}" — memory files are restricted to trusted agents. Agent "${agentId}" is not in the allowlist. This is a security feature preventing unauthorized memory access.` + context.ERROR_EXPLAIN_INSTRUCTION;
    return { allow: false, reason: blockReason, tier: "block", block: true, blockReason };
  },
};
