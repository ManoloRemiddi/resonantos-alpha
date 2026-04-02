module.exports = {
  check(tool, args, context) {
    if (tool !== "exec") return { allow: true, tier: "allow" };

    const command = String(args?.command || "");
    const strippedCommand = context.stripFalsePositiveContent(command);
    const ATOMIC_REBUILD_PATTERNS = [
      /\bdelete_nodes\b/,
      /\brm\s/,
      /\btrash\s/,
      /DROP\s+TABLE/i,
      /\btruncate\b/i,
    ];
    const ATOMIC_REBUILD_EXEMPT_PATTERNS = [
      /\/tmp\//i,
      /\.cache\//i,
      /\.log\b/i,
      /\bnode_modules\b/i,
      /\b__pycache__\b/i,
    ];

    const destructivePattern = ATOMIC_REBUILD_PATTERNS.find((pattern) => pattern.test(strippedCommand));
    const isExempt = ATOMIC_REBUILD_EXEMPT_PATTERNS.some((pattern) => pattern.test(strippedCommand));
    if (!destructivePattern || isExempt) return { allow: true, tier: "allow" };

    context.log("BLOCK", "Atomic Rebuild Gate — destructive operation detected", {
      pattern: destructivePattern.toString(),
      commandPreview: command.slice(0, 120),
    });

    const blockReason = "Atomic Rebuild Gate: Destructive operation detected. Ensure replacement content exists BEFORE deleting. Create → Verify → Delete.";
    return { allow: false, reason: blockReason, tier: "block", block: true, blocked: true, blockReason };
  },
};
