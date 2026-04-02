module.exports = {
  check(tool, args, context) {
    const compState = context.getCompactionState();
    if (!compState || context.ctx?.agentId !== "main") {
      return { allow: true, tier: "allow" };
    }

    const filePath = args?.file_path || args?.path || "";
    if (tool === "read") {
      let updated = false;
      if (/WORKFLOW_AUTO\.md/i.test(filePath) && !compState.readWorkflow) {
        compState.readWorkflow = true;
        updated = true;
      }
      if (/memory\/\d{4}-\d{2}-\d{2}\.md/i.test(filePath) && !compState.readMemory) {
        compState.readMemory = true;
        updated = true;
      }
      if (updated) {
        if (compState.readWorkflow && compState.readMemory) {
          context.clearCompactionState();
          context.log("INFO", "Post-Compaction Recovery complete — all context files read");
        } else {
          context.updateCompactionState(compState);
        }
      }
      return { allow: true, tier: "allow" };
    }

    const missing = [];
    if (!compState.readWorkflow) missing.push("WORKFLOW_AUTO.md");
    if (!compState.readMemory) missing.push("memory/YYYY-MM-DD.md (today)");

    context.log("BLOCK", "Post-Compaction Recovery Gate", { tool, missing });
    const blockReason = `[Post-Compaction Recovery] AI context was reset (compaction). It must re-read its configuration files before acting. This is automatic — no action needed from you.` + context.ERROR_EXPLAIN_INSTRUCTION;
    return { allow: false, reason: blockReason, tier: "block", block: true, blockReason };
  },
};
