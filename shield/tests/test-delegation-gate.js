/**
 * Delegation Gate — Unit Tests
 * Run: node test-delegation-gate.js
 * 
 * Tests the TASK.md validator deterministically.
 */

const fs = require("fs");
const path = require("path");
const os = require("os");

const gate = require("../delegation-gate.js");

let passed = 0;
let failed = 0;
const failures = [];

function assert(condition, testName) {
  if (condition) {
    passed++;
    process.stdout.write(".");
  } else {
    failed++;
    failures.push(testName);
    process.stdout.write("F");
  }
}

function tempDir() {
  return fs.mkdtempSync(path.join(os.tmpdir(), "delegation-test-"));
}

function writeTaskMd(dir, content) {
  fs.writeFileSync(path.join(dir, "TASK.md"), content);
}

// ============ isCodexExec tests ============

assert(gate.isCodexExec("codex exec 'fix the bug'"), "isCodexExec: basic codex exec");
assert(gate.isCodexExec("codex e 'fix the bug'"), "isCodexExec: alias codex e");
assert(gate.isCodexExec("  codex exec --full-auto 'prompt'"), "isCodexExec: with flags");
assert(gate.isCodexExec("cd /tmp && codex exec 'test'"), "isCodexExec: after cd");
assert(!gate.isCodexExec("echo codex"), "isCodexExec: not codex command");
assert(!gate.isCodexExec("ls -la"), "isCodexExec: unrelated command");
assert(!gate.isCodexExec(""), "isCodexExec: empty string");
assert(!gate.isCodexExec(null), "isCodexExec: null");
assert(!gate.isCodexExec(undefined), "isCodexExec: undefined");
assert(!gate.isCodexExec("git commit -m 'feat: codex exec delegation gate'"), "isCodexExec: codex exec inside git commit message");
assert(!gate.isCodexExec("echo 'codex exec test'"), "isCodexExec: codex exec inside echo quotes");
assert(gate.isCodexExec("cd /tmp && codex exec --full-auto 'do it'"), "isCodexExec: after cd &&");

// ============ resolveWorkDir tests ============

assert(gate.resolveWorkDir("codex exec -C /tmp/myproject 'test'", null) === "/tmp/myproject",
  "resolveWorkDir: -C flag");
assert(gate.resolveWorkDir("codex exec --cd /tmp/myproject 'test'", null) === "/tmp/myproject",
  "resolveWorkDir: --cd flag");
assert(gate.resolveWorkDir("codex exec 'test'", "/custom/dir") === "/custom/dir",
  "resolveWorkDir: exec workdir param");
assert(gate.resolveWorkDir("codex exec 'test'", null) === process.cwd(),
  "resolveWorkDir: falls back to cwd");

// ============ validateTaskMd tests ============

// --- Missing file ---
{
  const dir = tempDir();
  const result = gate.validateTaskMd(path.join(dir, "TASK.md"));
  assert(!result.valid, "validate: missing file is invalid");
  assert(result.errors.length === 1, "validate: missing file has 1 error");
  assert(result.errors[0].includes("not found"), "validate: missing file error message");
  fs.rmSync(dir, { recursive: true });
}

// --- Empty file ---
{
  const dir = tempDir();
  writeTaskMd(dir, "");
  const result = gate.validateTaskMd(path.join(dir, "TASK.md"));
  assert(!result.valid, "validate: empty file is invalid");
  fs.rmSync(dir, { recursive: true });
}

// --- Minimal valid TASK.md ---
{
  const dir = tempDir();
  writeTaskMd(dir, `# TASK: Fix the widget

## Root Cause
The widget renders incorrectly because \`renderWidget()\` in \`src/widget.js\` line 42 
passes a null context object when the parent container is not mounted yet. This causes
the CSS class calculation to fall through to the default branch.

## Fix
Add a null check for the context object before calling \`renderWidget()\`. If context 
is null, defer rendering to the next animation frame.

## Files to Modify
- \`src/widget.js\` line 42: add null check

## Test Command
\`\`\`bash
node -e "require('./src/widget').test()"
\`\`\`
`);
  const result = gate.validateTaskMd(path.join(dir, "TASK.md"));
  assert(result.valid, "validate: minimal valid TASK.md passes — errors: " + JSON.stringify(result.errors));
  assert(result.errors.length === 0, "validate: minimal valid has 0 errors");
  fs.rmSync(dir, { recursive: true });
}

// --- Missing Root Cause section ---
{
  const dir = tempDir();
  writeTaskMd(dir, `# TASK: Fix something

## Fix
Change line 42 in widget.js to add a null check for the context parameter.

## Files to Modify
- \`src/widget.js\` line 42

## Test Command
\`\`\`bash
node -e "require('./src/widget').test()"
\`\`\`
`);
  const result = gate.validateTaskMd(path.join(dir, "TASK.md"));
  assert(!result.valid, "validate: missing Root Cause is invalid");
  assert(result.errors.some(e => e.includes("Root Cause")), "validate: error mentions Root Cause");
  fs.rmSync(dir, { recursive: true });
}

// --- Vague Root Cause (investigate and fix) ---
{
  const dir = tempDir();
  writeTaskMd(dir, `# TASK: Fix the dashboard

## Root Cause
The dashboard costs are wrong. We need to investigate and fix the issue. 
It might be related to the usage stats or the gateway data or the pricing config.

## Fix
Look into the token-savings endpoint and figure out why numbers don't match.

## Files to Modify
- \`dashboard/server_v2.py\`

## Test Command
\`\`\`bash
curl http://localhost:19100/api/token-savings
\`\`\`
`);
  const result = gate.validateTaskMd(path.join(dir, "TASK.md"));
  assert(!result.valid, "validate: vague Root Cause is invalid");
  assert(result.errors.some(e => e.includes("vague language")), 
    "validate: error mentions vague language — errors: " + JSON.stringify(result.errors));
  fs.rmSync(dir, { recursive: true });
}

// --- Root Cause too short ---
{
  const dir = tempDir();
  writeTaskMd(dir, `# TASK: Fix bug

## Root Cause
It's broken.

## Fix
Change line 42 in widget.js to add a null check for the context parameter.

## Files to Modify
- \`src/widget.js\` line 42

## Test Command
\`\`\`bash
node test.js
\`\`\`
`);
  const result = gate.validateTaskMd(path.join(dir, "TASK.md"));
  assert(!result.valid, "validate: short Root Cause is invalid");
  assert(result.errors.some(e => e.includes("too brief")), "validate: error mentions too brief");
  fs.rmSync(dir, { recursive: true });
}

// --- Alternative section names (Bug, Problem, Solution) ---
{
  const dir = tempDir();
  writeTaskMd(dir, `# TASK: Fix the renderer

## Bug
The renderer crashes on null input because \`processFrame()\` in \`src/renderer.js\` 
line 87 doesn't validate the frame buffer before calling \`gl.texImage2D()\`. The null
propagates into the WebGL call which throws a TypeError.

## Solution
Add input validation at the top of \`processFrame()\` that returns early with a 
default empty frame if the buffer is null.

## Scope
- \`src/renderer.js\` line 87: add null guard

## Acceptance Criteria
\`\`\`bash
node -e "require('./test/renderer.test').runAll()"
\`\`\`
`);
  const result = gate.validateTaskMd(path.join(dir, "TASK.md"));
  assert(result.valid, "validate: alternative section names work — errors: " + JSON.stringify(result.errors));
  fs.rmSync(dir, { recursive: true });
}

// --- "maybe" in root cause ---
{
  const dir = tempDir();
  writeTaskMd(dir, `# TASK: Fix rendering

## Root Cause
The rendering is slow, maybe because the loop in \`draw()\` allocates new arrays each 
frame instead of reusing buffers. This allocation pressure triggers GC pauses.

## Fix
Pre-allocate the buffers in the constructor and reuse them in the draw loop.

## Files to Modify
- \`src/renderer.js\`

## Test Command
\`\`\`bash
node benchmark.js
\`\`\`
`);
  const result = gate.validateTaskMd(path.join(dir, "TASK.md"));
  assert(!result.valid, "validate: 'maybe' in root cause is invalid");
  fs.rmSync(dir, { recursive: true });
}

// ============ extractSection tests ============

{
  const content = `# Title

## Section A
Content A line 1
Content A line 2

## Section B
Content B

### Subsection B1
Sub content

## Section C
Content C`;

  const sectionA = gate.extractSection(content, /^##\s+Section A/im);
  assert(sectionA.includes("Content A line 1"), "extractSection: captures section A content");
  assert(!sectionA.includes("Content B"), "extractSection: doesn't leak into section B");
  
  const sectionB = gate.extractSection(content, /^##\s+Section B/im);
  assert(sectionB.includes("Content B"), "extractSection: captures section B");
  assert(sectionB.includes("Sub content"), "extractSection: includes subsections");
  assert(!sectionB.includes("Content C"), "extractSection: stops at next same-level heading");
}

// ============ countFilesListed tests ============

{
  const section1 = "- `src/widget.js` line 42\n- `src/styles.css` line 10";
  assert(gate.countFilesListed(section1) === 2, "countFiles: two backtick paths");
  
  const section2 = "- src/widget.js line 42\n- src/styles.css";
  assert(gate.countFilesListed(section2) === 2, "countFiles: two bullet paths");
  
  const section3 = "";
  assert(gate.countFilesListed(section3) === 1, "countFiles: empty returns 1");
}

// ============ Summary ============
console.log(`\n\n${passed + failed} tests: ${passed} passed, ${failed} failed`);
if (failures.length > 0) {
  console.log("\nFailed tests:");
  failures.forEach(f => console.log(`  ❌ ${f}`));
  process.exit(1);
} else {
  console.log("✅ All tests passed");
  process.exit(0);
}
