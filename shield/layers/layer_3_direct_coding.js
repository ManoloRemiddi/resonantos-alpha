module.exports = {
  check(tool, args, context) {
    const { stage, log, checkDirectCoding, checkExecCodeWrite } = context;

    if (stage === "exec") {
      if (tool !== "exec") return { allow: true, tier: "allow" };
      const command = args?.command;
      if (!command) return { allow: true, tier: "allow" };

      const execCodeWriteResult = checkExecCodeWrite(command);
      if (!execCodeWriteResult.block) return { allow: true, tier: "allow" };

      log("BLOCK", "Direct Coding Gate (exec)", { command: command.slice(0, 100) });
      return {
        allow: false,
        reason: execCodeWriteResult.blockReason,
        tier: "block",
        ...execCodeWriteResult,
      };
    }

    if (stage === "tool") {
      const codingResult = checkDirectCoding(tool, args);
      if (!codingResult.block) return { allow: true, tier: "allow" };

      log("BLOCK", "Direct Coding Gate", {
        tool,
        file: (args?.file_path || args?.path || "").slice(-60),
      });
      return {
        allow: false,
        reason: codingResult.blockReason,
        tier: "block",
        ...codingResult,
      };
    }

    return { allow: true, tier: "allow" };
  },
};
