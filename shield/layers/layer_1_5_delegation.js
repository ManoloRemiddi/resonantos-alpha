module.exports = {
  check(tool, args, context) {
    if (tool !== "exec") return { allow: true, tier: "allow" };

    const command = args?.command;
    if (!command) return { allow: true, tier: "allow" };

    const { log, checkDelegation } = context;
    const delegationResult = checkDelegation(command, args?.workdir);
    if (!delegationResult.block) return { allow: true, tier: "allow" };

    log("BLOCK", `Delegation Gate blocked ${tool}`, {
      command: command.slice(0, 100),
    });

    return {
      allow: false,
      reason: delegationResult.blockReason,
      tier: "block",
      ...delegationResult,
    };
  },
};
