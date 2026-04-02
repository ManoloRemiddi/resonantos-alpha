/**
 * Shield Gate + Delegation Gate — Integration Tests
 * Run: node test-shield-gate-delegation.js
 * 
 * Simulates the OpenClaw before_tool_call hook with codex exec commands.
 */

const fs = require("fs");
const path = require("path");
const os = require("os");

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
  return fs.mkdtempSync(path.join(os.tmpdir(), "shield-integ-"));
}

// Load the shield gate extension
const shieldGateFn = require(path.join(os.homedir(), ".openclaw/agents/main/agent/extensions/shield-gate.js"));

// Mock the OpenClaw API to capture the hook handler
let hookHandler = null;
const mockApi = {
  on(event, handler) {
    if (event === "before_tool_call") hookHandler = handler;
  }
};
shieldGateFn(mockApi);

function simulateExec(command, workdir) {
  return hookHandler({
    toolName: "exec",
    params: { command, workdir }
  });
}

// ============ Integration Tests ============

// --- codex exec without TASK.md → BLOCKED ---
{
  const dir = tempDir();
  const result = simulateExec(`codex exec --full-auto -C ${dir} 'Fix the bug'`, null);
  assert(result && result.block === true, "integ: codex exec without TASK.md is blocked");
  assert(result.blockReason && result.blockReason.includes("Delegation Gate"),
    "integ: block reason mentions Delegation Gate");
  fs.rmSync(dir, { recursive: true });
}

// --- codex exec with valid TASK.md → ALLOWED ---
{
  const dir = tempDir();
  fs.writeFileSync(path.join(dir, "TASK.md"), `# TASK: Fix the widget

## Root Cause
The widget renders incorrectly because renderWidget() in src/widget.js line 42 
passes a null context object when the parent container is not mounted yet.
This causes the CSS class calculation to fall through to the default branch.

## Fix
Add a null check for the context object before calling renderWidget().

## Files to Modify
- \`src/widget.js\` line 42: add null check

## Test Command
\`\`\`bash
node -e "require('./src/widget').test()"
\`\`\`
`);
  const result = simulateExec(`codex exec --full-auto -C ${dir} 'Fix the widget'`, null);
  assert(!result || !result.block, "integ: codex exec with valid TASK.md is allowed — got: " + JSON.stringify(result));
  fs.rmSync(dir, { recursive: true });
}

// --- codex exec with vague TASK.md → BLOCKED ---
{
  const dir = tempDir();
  fs.writeFileSync(path.join(dir, "TASK.md"), `# TASK: Fix dashboard

## Root Cause
The numbers are wrong. We need to investigate and fix the token savings calculation.
It should be stable across refreshes but it's not.

## Fix
Look into the endpoint and fix the data flow.

## Files to Modify
- \`server.py\`

## Test Command
\`\`\`bash
curl localhost:19100/api/token-savings
\`\`\`
`);
  const result = simulateExec(`codex exec --full-auto -C ${dir} 'Fix it'`, null);
  assert(result && result.block === true, "integ: vague TASK.md is blocked");
  assert(result.blockReason && result.blockReason.includes("vague language"),
    "integ: block reason mentions vague language — got: " + result.blockReason.slice(0, 200));
  fs.rmSync(dir, { recursive: true });
}

// --- Non-codex commands pass through normally ---
{
  const result = simulateExec("ls -la /tmp", null);
  assert(!result || !result.block, "integ: normal commands not affected");
}

// --- codex exec with workdir param (no -C flag) → validates TASK.md in workdir ---
{
  const dir = tempDir();
  // No TASK.md in this dir
  const result = simulateExec("codex exec 'Fix something'", dir);
  assert(result && result.block === true, "integ: workdir param used when no -C flag");
  fs.rmSync(dir, { recursive: true });
}

// --- Destructive commands still blocked (regression check) ---
{
  const result = simulateExec("rm -rf /", null);
  assert(result && result.block === true, "integ: destructive commands still blocked");
  assert(result.blockReason.includes("Shield Gate"), "integ: destructive uses Shield Gate message");
}

// --- codex e (alias) also caught ---
{
  const dir = tempDir();
  const result = simulateExec(`codex e --full-auto -C ${dir} 'test'`, null);
  assert(result && result.block === true, "integ: codex e alias also caught");
  fs.rmSync(dir, { recursive: true });
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
