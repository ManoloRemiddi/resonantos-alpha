module.exports = {
  check(tool, args, context) {
    if (context.stage === "web_search") {
      if (tool !== "web_search") return { allow: true, tier: "allow" };

      const query = args?.query || "";
      const words = query.trim().split(/\s+/).length;
      const RESEARCH_KEYWORDS = /\b(compare|analyze|research|investigate|state of the art|technical details|best approach|how does .+ work|architecture of|deep dive|comprehensive|evaluate|assessment)\b/i;
      if (!(words > 15 && RESEARCH_KEYWORDS.test(query))) return { allow: true, tier: "allow" };

      context.log("BLOCK", "Research Discipline Gate", {
        query: query.slice(0, 80),
        words,
      });

      const blockReason = `[Research Discipline Gate] Query too complex for basic web_search (${words} words). The AI will delegate this to the researcher agent instead for higher-quality results. No action needed.` + context.ERROR_EXPLAIN_INSTRUCTION;
      return { allow: false, reason: blockReason, tier: "block", block: true, blockReason };
    }

    if (context.stage === "message") {
      const content = args?.content || "";
      const RESEARCH_PATTERNS = [
        /\bresearch\b/i,
        /\binvestigate\b/i,
        /\bdeep\s+dive\b/i,
        /\banalyze\b.*\blandscape\b/i,
        /\btrends?\b/i,
      ];
      const researchMatch = RESEARCH_PATTERNS.some((pattern) => pattern.test(content));
      const lower = content.toLowerCase();
      const hasPerplexity = lower.includes("perplexity") || (lower.includes("browser") && lower.includes("search"));

      if (!researchMatch || hasPerplexity) return { allow: true, tier: "allow" };

      context.log("BLOCK", "Research Gate: Research requested without Perplexity", {
        content: content.slice(0, 80),
      });

      const blockReason = "🛡️ Research Gate: All research must use Perplexity via browser. Use browser tool to navigate to perplexity.ai and run deep research there." + context.ERROR_EXPLAIN_INSTRUCTION;
      return { allow: false, reason: blockReason, tier: "block", block: true, blockReason };
    }

    return { allow: true, tier: "allow" };
  },
};
