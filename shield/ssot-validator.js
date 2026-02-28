const fs = require("fs");
const path = require("path");

/**
 * Detect SSoT level from file path or metadata.
 * Returns 0-4 or -1 if unknown.
 */
function detectLevel(filePath, content) {
  // 1. Check file path for /L{0-4}/ directory
  const pathMatch = filePath.match(/[/\\\\]L([0-4])[/\\\\]/);
  if (pathMatch) return parseInt(pathMatch[1], 10);
  
  // 2. Check metadata header for Level field
  const levelMatch = content.match(/\|\s*Level\s*\|\s*L([0-4])/i);
  if (levelMatch) return parseInt(levelMatch[1], 10);
  
  return -1; // unknown
}

/**
 * Validate an SSoT file.
 * Returns { valid, errors, warnings, level, score }
 */
function validateSsot(filePath) {
  const errors = [];
  const warnings = [];
  let score = 100; // start perfect, deduct for failures
  
  // Read file
  if (!fs.existsSync(filePath)) {
    return { valid: false, errors: ["File not found: " + filePath], warnings: [], level: -1, score: 0 };
  }
  const content = fs.readFileSync(filePath, "utf-8");
  
  const level = detectLevel(filePath, content);
  
  // === UNIVERSAL RULES (all levels) ===
  
  // L4 has relaxed requirements
  if (level === 4) {
    // Only check: date in filename or header, at least one structural element
    const hasDate = /\d{4}-\d{2}-\d{2}/.test(path.basename(filePath)) || /\d{4}-\d{2}-\d{2}/.test(content.slice(0, 500));
    if (!hasDate) { warnings.push("L4 note: no date found in filename or header"); score -= 5; }
    
    const hasStructure = /^[#]+\s/m.test(content) || /^[-*]\s/m.test(content) || /\|.*\|/.test(content);
    if (!hasStructure) { warnings.push("L4 note: no structural element (heading, list, or table)"); score -= 5; }
    
    return { valid: true, errors, warnings, level, score };
  }
  
  // 1. Metadata header (table with ID, Level, Created, Status, Stale After, Related)
  const hasMetaTable = /\|\s*Field\s*\|\s*Value\s*\|/i.test(content) || /\|\s*ID\s*\|/i.test(content);
  if (!hasMetaTable) { errors.push("Missing metadata header table"); score -= 15; }
  else {
    // Check required fields
    const idMatch = content.match(/\|\s*ID\s*\|\s*(SSOT-L[0-4]-[A-Z0-9-]+-V\d+)\s*\|/i);
    if (!idMatch) { errors.push("Metadata: ID missing or doesn't match pattern SSOT-L{0-4}-{NAME}-V{n}"); score -= 10; }
    
    const statusMatch = content.match(/\|\s*Status\s*\|\s*(Active|Draft|Deprecated)\s*\|/i);
    if (!statusMatch) { errors.push("Metadata: Status missing or not one of Active/Draft/Deprecated"); score -= 5; }
    
    const createdMatch = content.match(/\|\s*Created\s*\|\s*(\d{4}-\d{2}-\d{2})\s*\|/i);
    if (!createdMatch) { errors.push("Metadata: Created date missing or not YYYY-MM-DD format"); score -= 5; }
    
    const staleMatch = content.match(/\|\s*Stale\s+After\s*\|/i);
    if (!staleMatch) { warnings.push("Metadata: Stale After field missing"); score -= 3; }
    
    const relatedMatch = content.match(/\|\s*Related\s*\|/i);
    if (!relatedMatch) { warnings.push("Metadata: Related field missing"); score -= 3; }
  }
  
  // 2. Problem statement
  const problemHeading = /^##\s+(The\s+Problem|Problem|Why\s+This\s+Exists)/im;
  const problemSection = extractSection(content, problemHeading);
  if (!problemSection || problemSection.length < 50) {
    errors.push("Missing or too brief Problem section (need ≥50 chars, got " + (problemSection ? problemSection.length : 0) + ")");
    score -= 10;
  }
  
  // 3. Solution section
  const solutionHeading = /^##\s+(The\s+Solution|Solution|Architecture|Design)/im;
  const solutionSection = extractSection(content, solutionHeading);
  if (!solutionSection || solutionSection.length < 100) {
    errors.push("Missing or too brief Solution/Architecture section (need ≥100 chars, got " + (solutionSection ? solutionSection.length : 0) + ")");
    score -= 10;
  }
  
  // === LEVEL-SPECIFIC RULES ===
  
  if (level === 0) {
    // L0: Audience, Principles (≥3 items)
    if (!/^##\s+(Audience|Who\s+Reads)/im.test(content)) { warnings.push("L0: missing Audience section"); score -= 5; }
    const principlesMatch = content.match(/^##\s+(Principles?|Core\s+Principles?)/im);
    if (!principlesMatch) { warnings.push("L0: missing Principles section"); score -= 5; }
    else {
      const princSection = extractSection(content, /^##\s+(Principles?|Core\s+Principles?)/im);
      const itemCount = (princSection.match(/^[\s]*[-*\d.]\s+/gm) || []).length;
      if (itemCount < 3) { warnings.push("L0: Principles has " + itemCount + " items (need ≥3)"); score -= 3; }
    }
  }
  
  if (level === 1) {
    // L1: Component table/diagram, Integration, Change Log
    const hasTable = /\|.*\|.*\|/m.test(content.replace(/\|\s*Field\s*\|\s*Value\s*\|/i, ''));
    const hasCodeBlock = /```/.test(content);
    if (!hasTable && !hasCodeBlock) { warnings.push("L1: no component table or architecture diagram found"); score -= 5; }
    
    if (!/^##\s+(Integration|How\s+It\s+Connects|Relationship)/im.test(content)) {
      warnings.push("L1: missing Integration/Relationship section"); score -= 3;
    }
    
    if (!/^##\s+(Change\s+Log|Changelog|History)/im.test(content)) {
      warnings.push("L1: missing Change Log"); score -= 3;
    }
  }
  
  if (level === 2) {
    // L2: Status in metadata, Current state, What's Next
    if (!/^##\s+(Current\s+State|Status|Where\s+We\s+Are)/im.test(content)) {
      warnings.push("L2: missing Current State section"); score -= 5;
    }
    if (!/^##\s+(What'?s?\s+Next|Next\s+Steps?|Roadmap)/im.test(content)) {
      warnings.push("L2: missing What's Next section"); score -= 5;
    }
  }
  
  if (level === 3) {
    // L3: Promotion criteria
    if (!/^##\s+(Promotion\s+Criteria|When\s+to\s+Promote|Ready\s+When)/im.test(content)) {
      warnings.push("L3: missing Promotion Criteria section"); score -= 5;
    }
    // Status should be Draft
    if (content.match(/\|\s*Status\s*\|\s*(\w+)/i)) {
      const status = content.match(/\|\s*Status\s*\|\s*(\w+)/i)[1];
      if (status.toLowerCase() !== 'draft') {
        warnings.push("L3: Status is '" + status + "' but should be 'Draft'"); score -= 3;
      }
    }
  }
  
  // Clamp score
  if (score < 0) score = 0;
  
  return {
    valid: errors.length === 0,
    errors,
    warnings,
    level,
    score
  };
}

/**
 * Extract section content (same logic as delegation-gate.js)
 */
function extractSection(content, headingRegex) {
  const lines = content.split("\n");
  let capturing = false;
  let sectionContent = [];
  let sectionLevel = 0;
  for (const line of lines) {
    if (headingRegex.test(line)) {
      capturing = true;
      const match = line.match(/^(#+)/);
      sectionLevel = match ? match[1].length : 2;
      continue;
    }
    if (capturing) {
      const headingMatch = line.match(/^(#+)\s/);
      if (headingMatch && headingMatch[1].length <= sectionLevel) break;
      sectionContent.push(line);
    }
  }
  return sectionContent.join("\n").trim();
}

module.exports = { validateSsot, detectLevel, extractSection };
