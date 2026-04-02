module.exports = {
  check(tool, args, context) {
    if (context.stage !== "message") return { allow: true, tier: "allow" };

    const content = args?.content || "";
    const DESIGN_TRIGGERS = [
      /\bnew\s+(?:system|architecture|protocol|framework|engine)\b/i,
      /\bstrategic\s+decision\b/i,
      /\bdesign-level\b/i,
      /\bredesign(?:ing)?\b/i,
    ];
    const IMPLEMENTATION_INTENT = [
      /\b(?:i(?:'ll|'m going to|'m)\s+(?:build|create|implement|design|architect))\b/i,
      /\bbuilding\s+(?:a\s+)?new\b/i,
      /\bcreating\s+(?:a\s+)?new\b/i,
      /\bimplementing\s+(?:a\s+)?new\b/i,
      /\blet me (?:build|create|implement)\b/i,
    ];

    const hasDesignTrigger = DESIGN_TRIGGERS.some((pattern) => pattern.test(content));
    const hasImplementationIntent = IMPLEMENTATION_INTENT.some((pattern) => pattern.test(content));
    if (!(hasDesignTrigger && hasImplementationIntent && content.length > 100)) {
      return { allow: true, tier: "allow" };
    }

    const sessionKey = context.ctx?.sessionKey || "";
    const ev = context.turnEvidence.get(sessionKey);
    const recentCalls = ev?.toolCalls || [];
    const DEBATE_EVIDENCE = [/self-debate/i, /debate/i, /adversarial/i];
    const hasDebate = recentCalls.slice(-20).some((call) => {
      const cmd = String(call.command || call.toolName || "");
      return DEBATE_EVIDENCE.some((pattern) => pattern.test(cmd));
    });

    if (hasDebate) {
      context.log("INFO", "Autonomous Development Gate — debate evidence found ✅", {
        sessionKey: sessionKey.slice(0, 30),
      });
      return { allow: true, tier: "allow" };
    }

    context.log("BLOCK", "Autonomous Development Gate — design-level work without self-debate", {
      contentPreview: content.slice(0, 120),
      sessionKey: sessionKey.slice(0, 30),
    });

    const blockReason = "🛡️ Autonomous Development Gate: Design-level implementation detected without self-debate evidence. Run self-debate (≥5 rounds) before building new systems/architectures. See SOUL.md." + context.ERROR_EXPLAIN_INSTRUCTION;
    return { allow: false, reason: blockReason, tier: "block", block: true, blocked: true, blockReason };
  },
};
