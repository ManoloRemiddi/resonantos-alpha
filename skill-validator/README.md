# Skill Validator

Security, testing, and approval pipeline for OpenClaw community skills.

## Overview

Before using any community skill, it must pass through the validation pipeline:

1. **Security Scan** — Static analysis to detect dangerous code patterns
2. **Sandbox Test** — Run tests in isolated environment to verify functionality
3. **Token Profiling** — Measure actual token usage vs. claimed costs
4. **Logician Approval** — Only approved skills can be used in production

## Quick Start

```bash
# Validate a skill (full pipeline)
./skill validate /path/to/skill

# Validate and auto-approve if passing
./skill validate /path/to/skill --approve

# List approved skills
./skill list

# Check if a skill is approved
./skill check skill-name

# Manually approve (after validation)
./skill approve skill-name

# Revoke approval
./skill revoke skill-name
```

## Validation Phases

### Phase 1: Security Scan

Detects dangerous patterns including:

| ID | Severity | Pattern |
|----|----------|---------|
| SEC001 | CRITICAL | API key theft (ANTHROPIC_API_KEY, OPENAI_KEY, etc.) |
| SEC003 | CRITICAL | Sensitive path access (/etc/passwd, ~/.ssh, .clawdbot/) |
| SEC007 | CRITICAL | Data exfiltration URLs (webhook.site, pastebin, ngrok) |
| SEC008 | CRITICAL | Dynamic code execution (eval, exec, Function()) |
| SEC010 | CRITICAL | Keylogger patterns |
| SEC012 | CRITICAL | Persistence mechanisms (crontab, .bashrc) |
| SEC004 | HIGH | File deletion operations |
| SEC009 | HIGH | Shell command injection |
| SEC011 | HIGH | Screen capture |
| SEC013 | HIGH | Code obfuscation (base64, hex encoding) |

**CRITICAL findings = AUTO-REJECT** (skill cannot be approved)

### Phase 2: Sandbox Tests

Tests are defined in the skill's `SKILL.md`:

```markdown
## Tests

### test_name
**Input:** `{"key": "value"}`
**Expected:** `expected output`
```

Or using code blocks:

````markdown
```test
name: test_name
input: {"key": "value"}
expected_output: expected output
```
````

**Expected output matchers:**
- Exact match: `expected output`
- Contains: `contains:substring`
- Regex: `regex:pattern.*`
- JSON structural match

### Phase 3: Token Profiling

Measures actual token usage during test runs and compares against claimed costs:

```markdown
# SKILL.md metadata
- **Token cost per call:** ~50
```

**FLAGS if actual > claimed + 20%** (false advertising warning)

### Phase 4: Logician Approval

Approval stored in `production_rules.mg`:

```mangle
approved_skill(/skill-name).
skill_version(/skill-name, "1.0.0").
skill_author(/skill-name, "author").
```

Query: `can_use_skill(/skill-name)` → true/false

## Creating a Validatable Skill

Your skill needs:

1. **SKILL.md** — Metadata and test cases
2. **Entry point** — `main.py`, `index.js`, or `skill.sh`

### Minimal SKILL.md

```markdown
# My Skill

## Metadata
- **Version:** 1.0.0
- **Author:** Your Name
- **Token cost per call:** ~100

## Description
What this skill does.

## Tests

### basic_test
**Input:** `{"query": "test"}`
**Expected:** `contains:result`
```

### Entry Point

Skills receive test input via environment variable:

**Python:**
```python
import os, json
input_data = json.loads(os.environ.get('SKILL_TEST_INPUT', '{}'))
# Process and print output
print(result)
```

**JavaScript:**
```javascript
const input = JSON.parse(process.env.SKILL_TEST_INPUT || '{}');
// Process and output
console.log(result);
```

## Integration

### With Clawdbot (Planned)

```bash
clawdbot skill install <name> --test  # Will use this validator
```

### Standalone

```bash
# Add to PATH
export PATH="$PATH:$HOME/clawd/projects/resonantos/skill-validator"

# Use anywhere
skill validate /path/to/skill
```

### Logician Query

```bash
# Check if skill is approved before use
./logician_client.py query "can_use_skill(/skill-name)"
```

## File Structure

```
skill-validator/
├── skill                    # CLI wrapper
├── skill_validator.py       # Main orchestrator
├── lib/
│   ├── security_scanner.py  # Phase 1: Static analysis
│   ├── sandbox_runner.py    # Phase 2: Test execution
│   └── token_profiler.py    # Phase 3: Cost measurement
├── test-skills/
│   ├── hello-world/         # Safe example skill
│   └── malicious-example/   # Malicious patterns (for testing)
└── README.md
```

## Security Model

- **Defense in depth**: Multiple validation phases
- **Fail-safe**: Critical findings = auto-reject
- **No execution of untrusted code**: Security scan runs BEFORE tests
- **Sandbox isolation**: Tests run with stripped credentials
- **Logician enforcement**: Even validated skills need explicit approval

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Passed / Approved |
| 1 | Failed validation |
| 2 | Error (file not found, etc.) |

## Future Enhancements

- [ ] Docker sandbox for full isolation
- [ ] Dependency vulnerability scanning (npm audit, pip-audit)
- [ ] Network call monitoring during tests
- [ ] Token usage graphs over time
- [ ] Skill reputation scores
