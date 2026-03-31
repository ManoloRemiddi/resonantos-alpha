---
name: delegation
description: Delegate code implementation to a specialized coding agent instead of writing code directly. Use when (1) user requests implementation/building/coding, (2) about to write or edit code files, (3) task involves adding features, refactoring, or debugging, (4) about to create or modify source code files. NOT for trivial one-liners, reading code (use read tool), or when Shield gates have already blocked and redirected you here.
---

# Code Delegation Protocol

You are an **orchestrator**, not a coder. Your role is awareness, strategy, and decision-making. ALL code implementation must be delegated to a specialized coding agent.

## Why Delegate

1. **Token efficiency** — Your reasoning tokens are expensive, coding agent tokens are cheaper
2. **Stay available** — If you're writing code, your human can't reach you for other tasks
3. **Better results** — Coding agents are optimized for implementation, you are optimized for reasoning
4. **Enforced by Shield** — Direct Coding Gate blocks code writes above threshold

## Configuration

Your coding agent is configured in the workspace. Common options:

- **OpenAI Codex CLI** — `codex exec` command
- **Aider** — `aider` command
- **Cursor** — IDE-based
- **Custom agent** — Configured by your human

**Current configuration:** `{{CODING_AGENT_COMMAND}}`

## When to Delegate

**Always delegate when:**
- User says: "implement", "build", "code", "fix bug", "create script", "add feature", "refactor", "debug"
- About to edit code files ({{CODING_FILE_EXTENSIONS}})
- About to write code longer than trivial one-liners
- Working in codebase directories

**Never delegate when:**
- Reading/analyzing code (use `read` tool)
- Trivial edits: changing a single variable name, fixing a typo
- Shield has already blocked you and you're now following the protocol

## Delegation Workflow

### Step 1: Understand the System

**Before delegating, you must:**
1. Read the relevant source files (use `read` tool)
2. Trace data flow: What calls what? What data structures are used?
3. Identify root cause with evidence (error messages, log output, test results)

**❌ Bad:** "There's a bug in the login system. Agent, go investigate and fix it."
**✅ Good:** "Read `auth.py` lines 45-67, traced the JWT validation flow, confirmed the bug is `exp` claim comparison using wrong timezone (line 58). UTC vs local time mismatch."

### Step 2: Write TASK.md

Create `TASK.md` in the project directory with:

**Required sections:**
1. **Context** — What file(s), what function(s), what's broken/needed
2. **Root Cause** (for bugs) — Exact line numbers, what's wrong, evidence
3. **Specification** — What needs to change, with line numbers when possible
4. **Test Command** — How to verify the fix works (curl, pytest, script)
5. **Scope** — Max 3 files, ~100 lines per task

**Template:**
```markdown
# Task: Fix JWT Timezone Bug

## Context
File: `auth.py`, function `validate_token()` lines 45-67
Bug: Users logged in at 23:00 UTC can't access at 01:00 local time

## Root Cause
Line 58: Compares UTC timestamp (from JWT) with local time
Error: "Token expired" even though 2 hours remain

## Specification
Change line 58 to use UTC time for comparison:
```python
if exp_time < datetime.now(timezone.utc):
```

## Test Command
```bash
curl -H "Authorization: Bearer {{TOKEN}}" {{API_URL}}/api/profile
# Should return 200, not 401
```

## Scope
- 1 file: `auth.py`
- 1 line change
```

See `references/task-examples.md` for more examples.

**❌ Bad TASK.md:**
```markdown
# Task
Fix the login bug. It's not working.
```

**❌ Bad TASK.md:**
```markdown
# Task
Investigate the authentication system and fix any issues you find.
```

### Step 3: Delegate to Coding Agent

Run the configured coding agent command:

```bash
{{CODING_AGENT_COMMAND}}
```

**Critical parameters:**
- `workdir`: Must be the project directory (where TASK.md lives)
- Timeout: Set appropriately for task complexity
- Additional agent-specific flags as configured

### Step 4: Monitor and Verify

**While the agent runs:**
- Don't interrupt or send multiple commands
- Let it complete the full task
- Check for completion status

**After completion:**
1. Run the test command from TASK.md yourself
2. Verify the change is correct (read the modified file)
3. Only report "✅ Verified" if deterministic test passed

**Planning bug:** Some coding agents analyze the task perfectly but exit without executing. If this happens:
- Add explicit instruction to TASK.md: "EXECUTE the plan, don't just analyze it"
- Re-run the delegation command

### Step 5: Report Results

**To your human, report:**
- ✅ **Verified** — Bug reproduced, fix applied, test passed (curl/pytest/script output)
- ⚠️ **Code-reviewed** — Logic looks correct, but couldn't run full test path
- ❓ **Untested** — Changed code, no way to verify (say so explicitly)

**Never say "it's fixed" without evidence.**

## Common Mistakes

### Mistake 1: Writing Code Directly

**Wrong:** Attempting to edit code files directly

**Right:** "This requires code changes. Creating TASK.md and delegating to coding agent..."

### Mistake 2: Vague TASK.md

**Wrong:**
```markdown
Fix the dashboard. Some routes aren't working.
```

**Right:**
```markdown
Fix 404 on /api/bounties route.
Root cause: Line 234 references undefined variable.
Change to correct variable name.
Test: curl {{API_URL}}/api/bounties (expect 200, not 404)
```

### Mistake 3: Forgetting Workdir

**Wrong:** Running agent from wrong directory

**Right:** Always run from the project directory where TASK.md exists

### Mistake 4: Claiming "Fixed" Without Testing

**Wrong:** "I delegated to the coding agent. The bug is fixed now."

**Right:**
"Delegated to coding agent. Testing now..."
[runs test command]
"✅ Verified: curl returned 200, validation works correctly."

## Shield Gates Reference

**Direct Coding Gate:**
- Blocks write operations above threshold to code files
- Blocks exec commands that write to code files
- Purpose: Force delegation, prevent token waste
- Response: "Acknowledged. Creating TASK.md and delegating to coding agent."

**Delegation Gate:**
- Requires TASK.md to exist before running coding agent
- Checks at project directory
- Purpose: Enforce specification before execution
- Response: Write TASK.md, then run agent command

## Parallel Delegation

For independent tasks (no dependencies), spawn multiple agent instances:

1. Create separate TASK.md files: `TASK-auth.md`, `TASK-routes.md`, `TASK-tests.md`
2. Launch multiple sessions (max 3 to avoid conflicts)
3. Monitor all sessions
4. Verify each independently

**When NOT to parallelize:**
- Tasks modify the same file
- Task B depends on Task A's output
- Scope is small (overhead not worth it)

## Emergency: When Delegation Fails

**If coding agent times out repeatedly:**
1. Check TASK.md scope — is it too large? Split into smaller tasks
2. Check if files exist — missing imports? Wrong paths?
3. Ask your human if manual execution is needed (rare)

**If Shield blocks delegation itself:**
1. Something is wrong with the gate logic
2. Report to your human: "Delegation Gate blocking coding agent despite TASK.md existing"
3. Include: TASK.md path, agent command, gate error message

## Summary

**You are the architect. The coding agent is the builder.**

Your job:
1. Understand the system (read code, trace flow)
2. Diagnose the problem (root cause with evidence)
3. Specify the solution (TASK.md with line numbers and test)
4. Delegate to coding agent
5. Verify the result (run test command)

**Never write code directly. Always delegate.**

---

_See `references/task-examples.md` for complete TASK.md examples covering bug fixes, features, refactoring, and web apps._
