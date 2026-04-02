module.exports = {
  check(tool, args, context) {
    const { isCgExempt, extractToolPath, isCgExcludedPath, checkCoherenceGate } = context;

    if (isCgExempt(tool, args)) return { allow: true, tier: "allow" };

    const actionPath = extractToolPath(tool, args);
    if (isCgExcludedPath(actionPath)) return { allow: true, tier: "allow" };

    const cgResult = checkCoherenceGate(tool, args);
    if (cgResult.block) {
      return {
        allow: false,
        reason: cgResult.reason,
        tier: "block",
        block: true,
        blockReason: cgResult.reason,
      };
    }

    return { allow: true, tier: "allow" };
  },
};
