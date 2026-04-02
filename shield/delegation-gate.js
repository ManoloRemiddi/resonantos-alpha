/**
 * Delegation Gate — Codex Task Quality Validator
 * 
 * Deterministic validator that blocks `codex exec` commands unless a valid
 * TASK.md exists in the working directory with all required sections.
 * 
 * No AI. Pure file I/O + regex. Fail-closed: if validation can't run, block.
 * 
 * Created: 2026-02-24 after two failed delegations proved behavioral
 * protocols alone are insufficient.
 * 
 * Integration: Called from shield-gate.js when a codex exec command is detected.
 * 
 * v1.0.0
 */

const fs = require("fs");
const path = require("path");

// --- Required sections in TASK.md ---
// Each entry: { heading: regex to match the section heading, minChars: minimum content length }
const REQUIRED_SECTIONS = [
  { 
    name: "Root Cause",
    heading: /^##\s+(Root\s+Cause|Bug|Problem)/im,
    minChars: 50,
    description: "Exact technical explanation of why it's broken, with evidence"
  },
  {
    name: "Fix",
    heading: /^##\s+(Fix|Solution|Change|Implementation)/im,
    minChars: 30,
    description: "Exact description of what to change"
  },
  {
    name: "Files to Modify",
    heading: /^##\s+(Files?\s+to\s+Modify|Files?\s+Changed?|Scope)/im,
    minChars: 10,
    description: "List of files with what changes are needed"
  },
  {
    name: "Test Command",
    heading: /^##\s+(Test\s+Command|Testing|Verification|Acceptance\s+Criteria)/im,
    minChars: 20,
    description: "Command that validates the fix works"
  }
];

// Additional sections for mid-tier tasks
const MID_SECTIONS = [
  {
    name: "Acceptance Criteria",
    heading: /^##\s+(Acceptance\s+Criteria|Done\s+When|Success\s+Criteria)/im,
    minChars: 30,
    description: "Minimum 3 verifiable conditions that define 'done'"
  },
  {
    name: "Out of Scope",
    heading: /^##\s+(Out\s+of\s+Scope|Do\s+NOT|Exclusions?)/im,
    minChars: 15,
    description: "Explicit list of things NOT to touch or change"
  },
  {
    name: "Data Context",
    heading: /^##\s+(Data\s+Context|Data\s+Samples?|Sample\s+Data|Examples?)/im,
    minChars: 40,
    description: "Actual data samples, config values, or API responses — not descriptions but real values"
  },
  {
    name: "Preferences",
    heading: /^##\s+(Preferences?|Favour|Prefer|Trade-?offs?|Approach\s+Priority)/im,
    minChars: 20,
    description: "When multiple valid approaches exist, which to favour and why"
  },
  {
    name: "Escalation Triggers",
    heading: /^##\s+(Escalation\s+Triggers?|Stop\s+When|Ask\s+When|Bail\s+Out|When\s+to\s+Stop)/im,
    minChars: 20,
    description: "Conditions under which the agent should stop and report back instead of deciding"
  }
];

// Additional sections for large/design-tier tasks
const LARGE_SECTIONS = [
  {
    name: "Constraints",
    heading: /^##\s+(Constraints?|Must\s+NOT|Boundaries|Limits)/im,
    minChars: 20,
    description: "Hard constraints: must-not rules, performance limits, escalation triggers"
  },
  {
    name: "Context",
    heading: /^##\s+(Context|Background|Architecture|Environment)/im,
    minChars: 50,
    description: "Architecture context, data flow, environment details for self-contained understanding"
  }
];

// --- Anti-patterns: phrases that indicate a vague/lazy task ---
const VAGUE_PHRASES = [
  /\binvestigate\s+and\s+fix\b/i,
  /\blikely\s+(root\s+)?cause/i,
  /\bprobably\s+(the|a|an)\b/i,
  /\bmight\s+be\s+(the|a|an|caused)\b/i,
  /\bshould\s+be\s+(fixed|stable|working|correct)\b/i,
  /\blook\s+into\b/i,
  /\bcheck\s+if\s+(this|it|the)\b/i,
  /\btry\s+(to\s+)?(fix|change|update)\b/i,
  /\bnot\s+sure\s+(if|what|why|how)\b/i,
  /\bsomehow\b/i,
  /\bmaybe\b/i,
];

// --- Scope limits ---
const MAX_FILES_TO_MODIFY = 5;  // generous but bounded

/**
 * Extract section content from markdown.
 * Returns the text between a heading and the next heading of same or higher level.
 */
function extractSection(content, headingRegex) {
  const lines = content.split("\n");
  let capturing = false;
  let sectionContent = [];
  let sectionLevel = 0;
  
  for (const line of lines) {
    if (headingRegex.test(line)) {
      capturing = true;
      // Determine heading level (count #'s)
      const match = line.match(/^(#+)/);
      sectionLevel = match ? match[1].length : 2;
      continue;
    }
    
    if (capturing) {
      // Stop at next heading of same or higher level
      const headingMatch = line.match(/^(#+)\s/);
      if (headingMatch && headingMatch[1].length <= sectionLevel) {
        break;
      }
      sectionContent.push(line);
    }
  }
  
  return sectionContent.join("\n").trim();
}

/**
 * Count files listed in "Files to Modify" section.
 * Looks for backtick-wrapped paths or lines starting with bullet markers.
 */
function countFilesListed(filesSection) {
  // Extract file paths from backticks (most reliable)
  const backtickPaths = filesSection.match(/`([^`]+\.[a-zA-Z]+)`/g) || [];
  if (backtickPaths.length > 0) {
    return new Set(backtickPaths).size;
  }
  // Fallback: count bullet lines containing file-like paths
  const bulletLines = filesSection.match(/^[\s]*[-*]\s+.+\.[a-zA-Z]+/gm) || [];
  return bulletLines.length || 1; // minimum 1 if section exists
}

/**
 * Detect task tier from TASK.md content.
 * Returns "small", "mid", or "large".
 */
function detectTier(content) {
  try {
    // Explicit tier declaration (highest priority)
    const tierMatch = content.match(/^(?:#|##)\s*.*?\b(tier|scope|level)\s*:\s*(small|mid|large|design)/im);
    if (tierMatch) {
      const declared = tierMatch[2].toLowerCase();
      if (declared === "design") return "large";
      return declared;
    }

    // Check for design-level keywords in title or first 500 chars
    const header = content.slice(0, 500).toLowerCase();
    const designKeywords = /\b(new\s+protocol|architecture|system\s+design|new\s+agent|strategic|new\s+extension|new\s+system)\b/;
    if (designKeywords.test(header)) return "large";

    // Count files listed in Files to Modify section
    const filesSection = extractSection(content, REQUIRED_SECTIONS[2].heading);
    const fileCount = filesSection ? countFilesListed(filesSection) : 0;
    if (fileCount > 3) return "mid";

    // Check for line count hints
    const lineHint = content.match(/(\d+)\s*lines?\b/i);
    if (lineHint && parseInt(lineHint[1], 10) > 100) return "mid";

    return "small";
  } catch (e) {
    // Fail-closed per TASK constraints
    return "mid";
  }
}

/**
 * Validate a TASK.md file.
 * Returns { valid: boolean, errors: string[], warnings: string[] }
 */
function validateTaskMd(filePath) {
  const errors = [];
  const warnings = [];
  
  // 1. File must exist
  if (!fs.existsSync(filePath)) {
    return {
      valid: false,
      errors: [`TASK.md not found at ${filePath}. Create it before delegating.`],
      warnings: []
    };
  }
  
  let content;
  try {
    content = fs.readFileSync(filePath, "utf-8");
  } catch (e) {
    return {
      valid: false,
      errors: [`Cannot read TASK.md: ${e.message}`],
      warnings: []
    };
  }
  
  // 2. File must not be empty or trivially small
  if (content.trim().length < 100) {
    errors.push(`TASK.md is only ${content.trim().length} chars. Minimum 100 chars for a proper task spec.`);
  }
  
  // 3. Required sections must exist with sufficient content
  for (const section of REQUIRED_SECTIONS) {
    const sectionContent = extractSection(content, section.heading);
    if (!sectionContent) {
      errors.push(`Missing section: "${section.name}" — ${section.description}`);
    } else if (sectionContent.length < section.minChars) {
      errors.push(
        `Section "${section.name}" is too brief (${sectionContent.length} chars, need ≥${section.minChars}). ` +
        `Be specific: ${section.description}`
      );
    }
  }

  // Detect tier and validate additional sections
  const tier = detectTier(content);

  const additionalSections = [];
  if (tier === "mid" || tier === "large") {
    additionalSections.push(...MID_SECTIONS);
  }
  if (tier === "large") {
    additionalSections.push(...LARGE_SECTIONS);
  }

  for (const section of additionalSections) {
    const sectionContent = extractSection(content, section.heading);
    if (!sectionContent) {
      errors.push(`Missing section for ${tier}-tier task: "${section.name}" — ${section.description}`);
    } else if (sectionContent.length < section.minChars) {
      errors.push(
        `Section "${section.name}" is too brief (${sectionContent.length} chars, need ≥${section.minChars}). ` +
        `Be specific: ${section.description}`
      );
    }
  }

  // For mid/large: acceptance criteria must have at least 3 items
  if (tier === "mid" || tier === "large") {
    const acSection = extractSection(content, MID_SECTIONS[0].heading);
    if (acSection) {
      const bulletCount = (acSection.match(/^[\s]*[-*\d.]\s+/gm) || []).length;
      if (bulletCount < 3) {
        warnings.push(`Acceptance Criteria has ${bulletCount} items (recommend ≥3 for ${tier}-tier tasks).`);
      }
    }
  }
  
  // 4. Check for vague language in Root Cause section
  const rootCause = extractSection(content, REQUIRED_SECTIONS[0].heading);
  if (rootCause) {
    for (const pattern of VAGUE_PHRASES) {
      const match = rootCause.match(pattern);
      if (match) {
        errors.push(
          `Root Cause contains vague language: "${match[0]}". ` +
          `The orchestrator must confirm the root cause before delegating — don't ask the coder to investigate.`
        );
        break; // one vague match is enough to block
      }
    }
  }
  
  // 5. Check for vague language in Fix section
  const fix = extractSection(content, REQUIRED_SECTIONS[1].heading);
  if (fix) {
    for (const pattern of VAGUE_PHRASES) {
      const match = fix.match(pattern);
      if (match) {
        warnings.push(`Fix section contains potentially vague language: "${match[0]}". Consider being more specific.`);
        break;
      }
    }
  }
  
  // 6. Scope check: count files to modify
  const filesSection = extractSection(content, REQUIRED_SECTIONS[2].heading);
  if (filesSection) {
    const fileCount = countFilesListed(filesSection);
    if (fileCount > MAX_FILES_TO_MODIFY) {
      warnings.push(
        `Task modifies ${fileCount} files (limit: ${MAX_FILES_TO_MODIFY}). ` +
        `Consider breaking into smaller tasks.`
      );
    }
  }
  
  // 7. Test section should contain a code block
  const testSection = extractSection(content, REQUIRED_SECTIONS[3].heading);
  if (testSection && !testSection.includes("```")) {
    warnings.push("Test section has no code block. Include a runnable test command.");
  }
  
  return {
    valid: errors.length === 0,
    errors,
    warnings
  };
}

/**
 * Resolve the working directory for a codex exec command.
 * Checks -C/--cd flag, or falls back to the exec's workdir param, or cwd.
 */
function resolveWorkDir(command, execWorkdir) {
  // Check for -C or --cd flag in the command
  const cdMatch = command.match(/(?:-C|--cd)\s+["']?([^\s"']+)["']?/);
  if (cdMatch) return cdMatch[1];
  
  // Use exec tool's workdir param if set
  if (execWorkdir) return execWorkdir;
  
  // Default to cwd
  return process.cwd();
}

/**
 * Check if a command is a codex exec invocation.
 */
function isCodexExec(command) {
  if (!command || typeof command !== "string") return false;
  const trimmed = command.trim();
  // Must match codex exec/e as an actual command invocation, not inside quotes/arguments.
  // Strategy: split on && / || / ; and check if any segment starts with codex or has codex after cd/env/etc.
  const segments = trimmed.split(/\s*(?:&&|\|\||;)\s*/);
  for (const seg of segments) {
    const s = seg.trim();
    // Direct invocation: "codex exec ..." or "codex e ..."
    if (/^codex\s+(exec|e)\b/.test(s)) return true;
    // After env vars or cd: "VAR=val codex exec" or similar
    if (/(?:^|\s)codex\s+(exec|e)\b/.test(s) && !/['"].*codex\s+(exec|e).*['"]/.test(s)) return true;
  }
  return false;
}

// --- Exports ---
module.exports = {
  validateTaskMd,
  resolveWorkDir,
  isCodexExec,
  extractSection,
  countFilesListed,
  detectTier,
  REQUIRED_SECTIONS,
  MID_SECTIONS,
  LARGE_SECTIONS,
  VAGUE_PHRASES,
  MAX_FILES_TO_MODIFY
};
