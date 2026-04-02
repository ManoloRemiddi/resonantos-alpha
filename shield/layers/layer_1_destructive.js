const fs = require("fs");
const path = require("path");

const HOME = process.env.HOME || "";

module.exports = {
  check(tool, args, context) {
    if (tool !== "exec") return { allow: true, tier: "allow" };

    const command = args?.command;
    if (!command) return { allow: true, tier: "allow" };

    const {
      execSync,
      log,
      checkExecCommand,
      GATEWAY_STOP_PATTERNS,
      ERROR_EXPLAIN_INSTRUCTION,
    } = context;

    const trimmed = command.trim();
    const cmdOnly = trimmed.split(/\n/)[0].split(/<<[\s'"]*\w+/)[0].trim();
    let gatewayLifecyclePattern = null;

    for (const pattern of GATEWAY_STOP_PATTERNS) {
      if (pattern.test(cmdOnly)) {
        gatewayLifecyclePattern = pattern;
        break;
      }
    }

    if (gatewayLifecyclePattern) {
      const configPath = path.join(HOME, ".openclaw/openclaw.json");
      try {
        JSON.parse(fs.readFileSync(configPath, "utf8"));
      } catch (err) {
        log("BLOCK", "Gateway Lifecycle Gate", {
          command: trimmed.slice(0, 100),
          pattern: gatewayLifecyclePattern.source,
          configPath,
          error: String(err),
        });
        const blockReason = "[Gateway Lifecycle Gate] Config file is invalid JSON — fix before restarting." + ERROR_EXPLAIN_INSTRUCTION;
        return { allow: false, reason: blockReason, tier: "block", block: true, blockReason };
      }

      try {
        execSync("launchctl print gui/501/ai.openclaw.gateway 2>/dev/null");
      } catch (err) {
        log("WARN", "Gateway Lifecycle Gate: launchd service not found", {
          command: trimmed.slice(0, 100),
          pattern: gatewayLifecyclePattern.source,
          error: String(err),
        });
      }

      log("ALLOW", "Gateway Lifecycle Gate", {
        command: trimmed.slice(0, 100),
        pattern: gatewayLifecyclePattern.source,
        configPath,
      });
    }

    const result = checkExecCommand(command);
    if (result.block) {
      log("BLOCK", `Blocked ${tool}`, {
        command: command.slice(0, 100),
        reason: result.blockReason,
      });
      return {
        allow: false,
        reason: result.blockReason,
        tier: "block",
        ...result,
      };
    }

    return { allow: true, tier: "allow" };
  },
};
