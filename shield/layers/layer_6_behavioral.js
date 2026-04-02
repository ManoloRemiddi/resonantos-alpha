const PRIVATE_PATTERNS = [
  /resonantos-(augmentor|alpha)/i,
  /ssot\/private/i,
  /MEMORY\.md/i,
  /memory\/\d{4}-\d{2}-\d{2}\.md/i,
  /\/Users\/[^/]+\//i,
];

const SAFE_DESTINATIONS = (process.env.RESONANTOS_SAFE_DESTINATIONS || "")
  .split(",")
  .map((value) => value.trim())
  .filter(Boolean);

module.exports = {
  check(tool, args, context) {
    const stage = context.stage;

    if (stage === "message_tool_state_claim") {
      if (tool !== "message" || args?.action !== "send") return { allow: true, tier: "allow" };

      const content = args?.message || args?.text || "";
      const stateClaimPattern = context.containsStateClaim(content);
      if (!stateClaimPattern) return { allow: true, tier: "allow" };

      const sessionKey = context.ctx?.sessionKey || "";
      const hasRecentVerification = context.hasRecentVerificationCommand(sessionKey);
      if (hasRecentVerification) {
        context.log("INFO", "State Claim Gate (message tool) — state claim has verification evidence ✅", {
          pattern: stateClaimPattern,
          sessionKey: sessionKey.slice(0, 30),
        });
        return { allow: true, tier: "allow" };
      }

      context.log("BLOCK", "State Claim Gate (message tool) — state claim without verification command", {
        pattern: stateClaimPattern,
        sessionKey: sessionKey.slice(0, 30),
        contentPreview: String(content).slice(0, 80),
      });

      const blockReason = "🛡️ State Claim Gate: System state claim detected in message tool content without a verification command in the last 20 tool calls. Run a verification command first (for example `openclaw status`, `openclaw skills`, `openclaw agents`, `openclaw plugins`) and then report the claim." + context.ERROR_EXPLAIN_INSTRUCTION;
      return { allow: false, reason: blockReason, tier: "block", block: true, blockReason };
    }

    if (stage === "message_tool_behavioral") {
      if (tool !== "message" || args?.action !== "send") return { allow: true, tier: "allow" };

      const content = args?.message || args?.text || "";
      const overclaim = context.containsBehavioralOverclaim(content);
      if (!overclaim) return { allow: true, tier: "allow" };

      context.log("BLOCK", "Behavioral Integrity Gate — potential overclaim", {
        pattern: overclaim.pattern,
        preview: overclaim.preview,
      });

      const blockReason = "Behavioral Integrity Gate: Overclaim detected. Rephrase with evidence or qualifier.";
      return { allow: false, reason: blockReason, tier: "block", block: true, blockReason };
    }

    if (stage === "config_change") {
      if (tool !== "write" && tool !== "edit" && tool !== "exec") return { allow: true, tier: "allow" };

      const CONFIG_FILE_PATTERNS = [
        /openclaw\.json/,
        /keywords\.json/,
        /config\.json/,
        /\.plist\b/,
        /launch.*\.json/i,
      ];
      const EXEMPT_CONFIG_PATHS = [
        /\.md$/i, /\.jsonl$/i, /\/memory\//i, /\/tmp\//i, /TASK\.md/i,
      ];

      let targetPath = "";
      if (tool === "exec") {
        targetPath = String(args?.command || "");
      } else {
        targetPath = String(args?.file_path || args?.path || "");
      }

      const isConfigFile = CONFIG_FILE_PATTERNS.some((pattern) => pattern.test(targetPath));
      const isExempt = EXEMPT_CONFIG_PATHS.some((pattern) => pattern.test(targetPath));
      const isExecReadOnly = tool === "exec" && isConfigFile && (() => {
        const EXEC_WRITE_PATTERNS = [
          /\s>\s/, /\s>>\s/, /\btee\b/, /\bsed\s+-i/, /\bperl\s+-[ip]/,
          /\becho\b.*>/, /\bprintf\b.*>/, /\bmv\b/, /\brm\b/, /\btrash\b/,
        ];
        return !EXEC_WRITE_PATTERNS.some((pattern) => pattern.test(targetPath));
      })();

      if (!isConfigFile || isExempt || isExecReadOnly) return { allow: true, tier: "allow" };

      const sessionKey = context.ctx?.sessionKey || "";
      const ev = context.turnEvidence.get(sessionKey);
      const recentCalls = ev?.toolCalls || [];
      const BACKUP_PATTERNS = [/\bcp\b/, /\brsync\b/, /\.bak\b/, /backup/i, /\bcopy\b/i];
      const hasBackup = recentCalls.slice(-10).some((call) => {
        const cmd = String(call.command || call.toolName || "");
        return BACKUP_PATTERNS.some((pattern) => pattern.test(cmd));
      });

      if (hasBackup) {
        context.log("INFO", "Config Change Gate — backup evidence found ✅", {
          targetPath: targetPath.slice(0, 80),
        });
        return { allow: true, tier: "allow" };
      }

      context.log("BLOCK", "Config Change Gate — no backup evidence", {
        targetPath: targetPath.slice(0, 80),
        sessionKey: sessionKey.slice(0, 30),
      });

      const blockReason = "🛡️ Config Change Gate: Back up config before modifying. Run: cp <file> <file>.bak" + context.ERROR_EXPLAIN_INSTRUCTION;
      return { allow: false, reason: blockReason, tier: "block", block: true, blocked: true, blockReason };
    }

    if (stage === "model_selection") {
      if (tool !== "sessions_spawn" || !args?.model) return { allow: true, tier: "allow" };

      const model = String(args.model).toLowerCase();
      const EXPENSIVE_MODELS = [/opus/, /sonnet/, /gpt-4o/, /gpt-5(?!\.3-codex)/];
      const isExpensive = EXPENSIVE_MODELS.some((pattern) => pattern.test(model));
      if (!isExpensive) return { allow: true, tier: "allow" };

      const task = String(args?.task || args?.message || "").toLowerCase();
      const COMPLEXITY_KEYWORDS = ["architecture", "reasoning", "complex", "design-level", "strategic", "debate", "audit", "security", "protocol"];
      const hasJustification = COMPLEXITY_KEYWORDS.some((keyword) => task.includes(keyword));
      if (hasJustification) {
        context.log("INFO", "Model Selection Gate — expensive model justified ✅", {
          model: model.slice(0, 40),
        });
        return { allow: true, tier: "allow" };
      }

      context.log("BLOCK", "Model Selection Hierarchy Gate — expensive model for routine task", {
        model: model.slice(0, 40),
        taskPreview: task.slice(0, 80),
      });

      const blockReason = "🛡️ Model Selection Gate: Expensive model (" + model + ") used for routine task. Use MiniMax or Haiku for non-complex work. Add complexity justification to task description if needed." + context.ERROR_EXPLAIN_INSTRUCTION;
      return { allow: false, reason: blockReason, tier: "block", block: true, blocked: true, blockReason };
    }

    if (stage === "repo_contamination") {
      const content = args?.content || "";
      const to = String(args?.to || "");
      const isSafeDest = SAFE_DESTINATIONS.some((destination) => to.includes(destination));
      if (isSafeDest) return { allow: true, tier: "allow" };

      for (const pattern of PRIVATE_PATTERNS) {
        if (!pattern.test(content)) continue;

        context.log("BLOCK", "Repo Contamination Gate — cancelled outbound message", {
          to: to.slice(0, 30),
          pattern: pattern.toString(),
          contentPreview: content.slice(0, 80),
        });

        return {
          allow: false,
          reason: "Repo contamination",
          tier: "cancel",
          cancel: true,
        };
      }

      return { allow: true, tier: "allow" };
    }

    if (stage === "verification_claim") {
      const content = args?.content || "";
      const claimPattern = context.containsVerificationClaim(content);
      if (!claimPattern) return { allow: true, tier: "allow" };

      const sessionKey = context.ctx?.sessionKey || "";
      const hasEvidence = context.hasTestEvidence(sessionKey);
      if (hasEvidence) {
        context.log("INFO", "Verification Claim Gate — claim has exec evidence ✅", {
          pattern: claimPattern,
          sessionKey: sessionKey.slice(0, 30),
        });
        return { allow: true, tier: "allow" };
      }

      context.log("BLOCK", "Verification Claim Gate — 'fixed' claim without exec evidence", {
        pattern: claimPattern,
        sessionKey: sessionKey.slice(0, 30),
        contentPreview: content.slice(0, 80),
      });

      const blockReason = "🛡️ Verification Gate: You claimed 'fixed' without running a test. Run a test first, then report results. Do not claim something is fixed without evidence." + context.ERROR_EXPLAIN_INSTRUCTION;
      return { allow: false, reason: blockReason, tier: "block", block: true, blockReason };
    }

    if (stage === "message_state_claim") {
      const content = args?.content || "";
      const stateClaimPattern = context.containsStateClaim(content);
      if (!stateClaimPattern) return { allow: true, tier: "allow" };

      const sessionKey = context.ctx?.sessionKey || "";
      const hasRecentVerification = context.hasRecentVerificationCommand(sessionKey);
      if (hasRecentVerification) {
        context.log("INFO", "State Claim Gate — state claim has verification evidence ✅", {
          pattern: stateClaimPattern,
          sessionKey: sessionKey.slice(0, 30),
        });
        return { allow: true, tier: "allow" };
      }

      context.log("BLOCK", "State Claim Gate — state claim without verification command", {
        pattern: stateClaimPattern,
        sessionKey: sessionKey.slice(0, 30),
        contentPreview: content.slice(0, 80),
      });

      const blockReason = "🛡️ State Claim Gate: System state claim detected without a verification command in the last 20 tool calls. Run a verification command first (for example `openclaw status`, `openclaw skills`, `openclaw agents`, `openclaw plugins`) and then report the claim." + context.ERROR_EXPLAIN_INSTRUCTION;
      return { allow: false, reason: blockReason, tier: "block", block: true, blockReason };
    }

    if (stage === "behavioral_integrity") {
      const content = args?.content || "";
      const overclaim = context.containsBehavioralOverclaim(content);
      if (!overclaim) return { allow: true, tier: "allow" };

      context.log("BLOCK", "Behavioral Integrity Gate — potential overclaim", {
        pattern: overclaim.pattern,
        preview: overclaim.preview,
      });

      const blockReason = "Behavioral Integrity Gate: Overclaim detected. Rephrase with evidence or qualifier.";
      return { allow: false, reason: blockReason, tier: "block", block: true, blocked: true, blockReason };
    }

    if (stage === "decision_bias") {
      const content = args?.content || "";
      const OPTION_PATTERNS = [
        /\bOption\s+[A-C]\b/g,
        /\b(?:option|choice)\s*(?:#?\s*)?[1-3]\b/ig,
        /\*\*(?:Option|Choice)\s+[A-C1-3]\b/g,
        /^\s*[-•]\s*\*?\*?(?:Option|Choice)\s+/im,
      ];
      const ASKING_PATTERNS = [
        /\bwant me to\b/i,
        /\bwhich (?:would you|do you|option)\b/i,
        /\bwhat do you (?:think|prefer|want)\b/i,
        /\byour (?:call|choice|preference)\b/i,
        /\bshould I\b/i,
        /\blet me know\b/i,
      ];

      let optionCount = 0;
      for (const pattern of OPTION_PATTERNS) {
        const matches = content.match(pattern);
        if (matches) optionCount = Math.max(optionCount, matches.length);
      }

      const isAskingUser = ASKING_PATTERNS.some((pattern) => pattern.test(content));
      if (!(optionCount >= 2 && isAskingUser)) return { allow: true, tier: "allow" };

      context.log("BLOCK", "Decision Bias Gate — presenting options instead of acting", {
        optionCount,
        contentPreview: content.slice(0, 120),
      });

      const blockReason = "Decision Bias Gate: You presented " + optionCount + " options. Apply SOUL.md decision bias filters. If one option clearly wins, act — don't ask.";
      return { allow: false, reason: blockReason, tier: "block", block: true, blockReason };
    }

    if (stage === "memory_log") {
      const content = args?.content || "";
      const memoryLogGateResult = context.checkMemoryLogGate(content);
      if (!memoryLogGateResult.block) return { allow: true, tier: "allow" };

      context.log("BLOCK", "Memory Log Gate — blocked HEARTBEAT_OK", {
        breadcrumbsFile: context.MEMORY_BREADCRUMBS_FILE,
        heartbeatFile: context.MEMORY_HEARTBEAT_STATE_FILE,
        contentPreview: content.slice(0, 40),
      });

      return {
        allow: false,
        reason: memoryLogGateResult.blockReason,
        tier: "block",
        ...memoryLogGateResult,
      };
    }

    return { allow: true, tier: "allow" };
  },
};
