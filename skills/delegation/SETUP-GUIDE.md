# Delegation Skill Setup Guide

This skill teaches your AI agent to delegate code implementation to a specialized coding agent instead of writing code directly.

## Quick Start

1. **Install the skill** (if using skill loader):
   ```bash
   openclaw skills install delegation.skill
   ```

2. **Configure your coding agent** in workspace files:
   - Edit the placeholders in `SKILL.md` OR
   - Configure via your agent's workspace setup

3. **Test the skill**:
   - Ask your agent: "Implement a hello world function in Python"
   - Agent should create TASK.md and delegate instead of writing code directly

## Placeholders to Configure

Replace these placeholders in `SKILL.md` (or configure via setup agent):

### Required Placeholders

| Placeholder | Description | Example |
|------------|-------------|---------|
| `{{CODING_AGENT_COMMAND}}` | Command to invoke your coding agent | `codex exec --dangerously-bypass-approvals-and-sandbox "Read TASK.md and follow it exactly"` OR `aider --yes-always` |
| `{{CODING_FILE_EXTENSIONS}}` | File extensions that trigger delegation | `.py, .js, .html, .css, .sh, .ts, .jsx, .tsx` |

### Optional Placeholders (for examples)

| Placeholder | Description | Example |
|------------|-------------|---------|
| `{{TOKEN}}` | Sample API token for tests | `eyJhbGc...` |
| `{{API_URL}}` | Your API base URL | `http://localhost:19100` |

## Supported Coding Agents

This skill works with any coding agent that:
1. Can read TASK.md from a project directory
2. Executes code changes based on specifications
3. Returns success/failure status

### Examples

**OpenAI Codex CLI:**
```bash
codex exec --dangerously-bypass-approvals-and-sandbox "Read TASK.md and follow it exactly"
```

**Aider:**
```bash
aider --yes-always --message "Read TASK.md and implement the specified changes"
```

**Cursor (manual):**
```
Open TASK.md, review, implement in IDE
```

**Custom agent:**
```bash
your-coding-agent --task TASK.md --auto-approve
```

## Shield Integration (Optional)

If your ResonantOS installation has Shield enabled, this skill works with:

- **Direct Coding Gate** — Blocks direct code writes, redirects to delegation
- **Delegation Gate** — Requires TASK.md before running coding agent

No additional configuration needed — the skill auto-detects Shield.

## Testing

Create a test file to verify delegation works:

```bash
echo "Create a Python function that adds two numbers" > test-request.txt
```

Your agent should:
1. ✅ Create TASK.md in current directory
2. ✅ Run `{{CODING_AGENT_COMMAND}}`
3. ✅ Verify the result
4. ❌ NOT write code directly

## Troubleshooting

**"Coding agent not found" error:**
- Check `{{CODING_AGENT_COMMAND}}` is correct
- Verify the agent is installed (`which codex` / `which aider`)

**Agent runs but doesn't read TASK.md:**
- Ensure workdir is set to project directory
- Check TASK.md exists in the correct location

**Shield blocks delegation:**
- Report to your human — gate logic may need adjustment
- Include: TASK.md path, agent command, error message

## Advanced: Multiple Agents

You can configure different agents for different contexts:

```markdown
**Python projects:** `{{PYTHON_CODING_AGENT}}`
**JavaScript projects:** `{{JS_CODING_AGENT}}`
**Data analysis:** `{{DATA_AGENT}}`
```

Your setup agent can populate these based on project detection.

## Learn More

- See `references/task-examples.md` for complete TASK.md examples
- Read SKILL.md for full delegation protocol
- Check OpenClaw docs: https://docs.openclaw.ai

---

_Part of ResonantOS — the experience layer for OpenClaw._
