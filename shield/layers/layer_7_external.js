const SAFE_DESTINATIONS = (process.env.RESONANTOS_SAFE_DESTINATIONS || "")
  .split(",")
  .map((value) => value.trim())
  .filter(Boolean);

module.exports = {
  check(tool, args, context) {
    if (tool === "exec") {
      let cmd = (args?.command || "").trim();
      cmd = cmd.replace(/<<\s*'?(\w+)'?[\s\S]*?\n\1\b/g, "<<HEREDOC_STRIPPED");

      const EXTERNAL_ACTION_PATTERNS = [
        /\bgog\s+mail\s+send\b/i,
        /\bgog\s+calendar\s+create\b/i,
        /\btweet\b/i,
        /\bsendmail\b/i,
        /\bmail\s+-s\b/i,
        /\bcurl\s.*api\.twitter/i,
        /\bcurl\s.*api\.x\.com/i,
      ];

      for (const pattern of EXTERNAL_ACTION_PATTERNS) {
        if (!pattern.test(cmd)) continue;

        context.log("BLOCK", "External Action Gate — exec", {
          command: cmd.slice(0, 80),
          pattern: pattern.toString(),
        });

        const blockReason = `[External Action Gate] Blocked external action (${cmd.slice(0, 40)}...). This gate prevents the AI from sending emails, tweets, or public posts without your explicit approval. Tell the AI to proceed if you want this action taken.` + context.ERROR_EXPLAIN_INSTRUCTION;
        return { allow: false, reason: blockReason, tier: "block", block: true, blockReason };
      }
    }

    if (tool === "message" && args?.action === "send") {
      const target = args?.target || args?.to || "";
      if (target && SAFE_DESTINATIONS.length > 0 && !SAFE_DESTINATIONS.some((destination) => target.includes(destination))) {
        context.log("BLOCK", "External Action Gate — message", {
          target: target.slice(0, 30),
          action: args?.action,
        });

        const blockReason = `[External Action Gate] Blocked message to "${target}". Only configured safe destinations are auto-allowed. Tell the AI to proceed if you approve sending to this target.` + context.ERROR_EXPLAIN_INSTRUCTION;
        return { allow: false, reason: blockReason, tier: "block", block: true, blockReason };
      }
    }

    return { allow: true, tier: "allow" };
  },
};
