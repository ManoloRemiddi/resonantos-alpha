module.exports = {
  check(tool, args, context) {
    if (tool !== "web_fetch") return { allow: true, tier: "allow" };

    const rawUrl = String(args?.url || "").trim();
    let domain = rawUrl;
    try {
      domain = new URL(rawUrl).hostname.toLowerCase();
    } catch (_) {
      // Fall back to raw value so invalid URLs fail closed below.
    }

    for (const pattern of context.NETWORK_BLOCKED_DOMAINS) {
      if (!pattern.test(domain)) continue;

      context.log("BLOCK", "Network Allowlist Gate", {
        url: rawUrl,
        domain,
        reason: "blocklist",
        pattern: pattern.source,
      });

      const blockReason = `🌐 [Network Allowlist Gate] Blocked web_fetch to "${domain}" — domain is on the blocklist (data exfiltration risk).` + context.ERROR_EXPLAIN_INSTRUCTION;
      return { allow: false, reason: blockReason, tier: "block", block: true, blockReason };
    }

    let allowed = false;
    for (const pattern of context.NETWORK_ALLOWED_DOMAINS) {
      if (!pattern.test(domain)) continue;
      allowed = true;
      context.log("ALLOW", "Network Allowlist Gate", {
        url: rawUrl,
        domain,
        pattern: pattern.source,
      });
      break;
    }

    if (allowed) return { allow: true, tier: "allow" };

    context.log("BLOCK", "Network Allowlist Gate", {
      url: rawUrl,
      domain,
      reason: "not_in_allowlist",
    });

    const blockReason = `🌐 [Network Allowlist Gate] Blocked web_fetch to "${domain}" — domain not in allowlist. If this domain is legitimate, update the allowlist before retrying.` + context.ERROR_EXPLAIN_INSTRUCTION;
    return { allow: false, reason: blockReason, tier: "block", block: true, blockReason };
  },
};
