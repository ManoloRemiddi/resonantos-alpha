# TASK.md Examples

Good TASK.md files for common scenarios. Use these as templates.

## Example 1: Bug Fix (Simple)

```markdown
# Task: Fix 404 Error on Bounties API

## Context
File: `dashboard/server_v2.py`, route `/api/bounties` (lines 230-245)
User report: Accessing `/api/bounties` returns 404 instead of bounty list

## Root Cause
Line 234: Variable name mismatch
```python
return jsonify(bounty_list)  # ❌ bounty_list is undefined
```
Variable is actually named `bounties` (defined at line 228)

## Specification
Change line 234 from:
```python
return jsonify(bounty_list)
```
to:
```python
return jsonify(bounties)
```

## Test Command
```bash
curl -s http://localhost:19100/api/bounties | jq '.success'
# Expected: true
# Current: (404 error)
```

## Scope
- 1 file: `dashboard/server_v2.py`
- 1 line: line 234
- Estimated time: <2 minutes
```

---

## Example 2: Feature Addition (Medium)

```markdown
# Task: Add Search Filter to Bounties API

## Context
File: `dashboard/server_v2.py`, function `get_bounties()` (lines 228-245)
New requirement: Support `?status=open` query parameter to filter bounties by status

## Current Behavior
`/api/bounties` returns all bounties regardless of status

## Desired Behavior
- `/api/bounties` → returns all bounties (unchanged)
- `/api/bounties?status=open` → returns only open bounties
- `/api/bounties?status=completed` → returns only completed bounties
- Invalid status → returns empty array (not 400 error)

## Specification
Modify `get_bounties()` function:

1. **Line 229** — Extract query parameter:
```python
status_filter = request.args.get('status', None)
```

2. **Line 235** — Add filtering logic before return:
```python
if status_filter:
    bounties = [b for b in bounties if b.get('status') == status_filter]
```

## Test Commands
```bash
# Test 1: No filter (should return all)
curl -s http://localhost:19100/api/bounties | jq '. | length'
# Expected: 17 (current count)

# Test 2: Filter by "open"
curl -s http://localhost:19100/api/bounties?status=open | jq '. | length'
# Expected: 5 (manual count from DB)

# Test 3: Filter by "completed"
curl -s http://localhost:19100/api/bounties?status=completed | jq '. | length'
# Expected: 12

# Test 4: Invalid status
curl -s http://localhost:19100/api/bounties?status=invalid | jq '. | length'
# Expected: 0
```

## Scope
- 1 file: `dashboard/server_v2.py`
- 2 lines added (lines 229, 235)
- Estimated time: 5 minutes
```

---

## Example 3: Refactoring (Complex)

```markdown
# Task: Extract Shield Rule Loading into Separate Function

## Context
File: `shield/daemon.py`, function `initialize_shield()` (lines 145-210)
Problem: Function is 65 lines long and does 3 distinct things (rule loading, YARA compilation, hook validation)
Goal: Extract rule loading (lines 150-175) into `load_shield_rules()` function for reusability

## Current Structure
```python
def initialize_shield():
    # Lines 145-149: Setup
    logger.info("Initializing Shield...")
    
    # Lines 150-175: Rule loading (TO EXTRACT)
    rules = []
    for file in glob.glob("rules/*.json"):
        with open(file) as f:
            rules.append(json.load(f))
    # ... more rule loading logic
    
    # Lines 176-195: YARA compilation
    # Lines 196-210: Hook validation
```

## Specification

### Step 1: Create new function (after line 144)
```python
def load_shield_rules(rules_dir="rules"):
    """Load all Shield rules from JSON files.
    
    Args:
        rules_dir: Directory containing rule JSON files
        
    Returns:
        List of loaded rule dictionaries
    """
    rules = []
    for file in glob.glob(f"{rules_dir}/*.json"):
        try:
            with open(file) as f:
                rule = json.load(f)
                rules.append(rule)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse {file}: {e}")
    return rules
```

### Step 2: Replace lines 150-175 in initialize_shield()
```python
def initialize_shield():
    logger.info("Initializing Shield...")
    
    # Load rules
    rules = load_shield_rules()
    logger.info(f"Loaded {len(rules)} Shield rules")
    
    # YARA compilation (existing code continues from line 176)
    ...
```

## Test Command
```bash
# Test 1: Unit test the new function
python3 -c "
from shield.daemon import load_shield_rules
rules = load_shield_rules()
print(f'Loaded {len(rules)} rules')
assert len(rules) == 18, f'Expected 18 rules, got {len(rules)}'
print('✅ Rule loading works')
"

# Test 2: Full Shield initialization still works
curl http://localhost:9999/health
# Expected: {"status": "ok", "rules_loaded": 18}
```

## Scope
- 1 file: `shield/daemon.py`
- ~30 lines: new function + modifications
- Estimated time: 10 minutes
- Risk: Medium (refactoring existing code)
```

---

## Example 4: Web App Creation (Large)

```markdown
# Task: Create SSoT Template Comparison Web App

## Context
Need side-by-side comparison tool for reviewing 18 L0/L1 SSoT templates.
- Originals: `/Users/augmentor/resonantos-augmentor/ssot/L0/` and `L1/`
- Templates: `/Users/augmentor/resonantos-alpha/ssot/L0/` and `L1/`

## Requirements

### 1. Single-File HTTP Server
- Python Flask app (inline HTML/CSS/JS)
- Port: 9876
- Output: `/tmp/ssot-reviewer.py`

### 2. UI Layout
```
┌─────────────────────────────────────────┐
│  SSoT Template Reviewer                 │
├──────────┬──────────────────────────────┤
│          │ Original │ Template          │
│ Sidebar  ├──────────┼──────────────────┤
│ (18 docs)│          │                   │
│          │   left   │   right           │
│          │  panel   │   panel           │
│          │          │                   │
└──────────┴──────────┴──────────────────┘
```

### 3. Sidebar Navigation
- 18 documents listed (L0 first, then L1)
- Click → loads both original and template
- Show stats: original lines, template lines, placeholder count

### 4. Comparison Panels
- Left: Original file from augmentor repo
- Right: Template file from alpha repo
- Syntax highlighting for markdown
- Highlight `{{PLACEHOLDERS}}` in yellow (#facc15)

### 5. Document Mapping
Some files have naming mismatches between repos:
- `SSOT-L1-RECENT-HEADERS.md` vs `SSOT-L1-RECENT-HEADERS.ai.md`
- Handle these gracefully

## API Endpoints
```python
GET / → Serve HTML/CSS/JS
GET /api/list → Return document list (18 items)
GET /api/load?path=<doc-id> → Return {original_content, template_content, stats}
```

## Test Commands
```bash
# Test 1: Server starts
python3 /tmp/ssot-reviewer.py
# Expected: "Running on http://localhost:9876"

# Test 2: HTML response
curl -s http://localhost:9876/ | head -20
# Expected: <!doctype html>

# Test 3: API response
curl -s 'http://localhost:9876/api/load?path=l0-overview' | jq '.stats'
# Expected: {"original_lines": 136, "template_lines": 164, "placeholder_count": 31}
```

## Scope
- 1 file: `/tmp/ssot-reviewer.py`
- ~500 lines estimated (inline HTML/CSS/JS)
- Dark theme UI
- Estimated time: 30 minutes
- Risk: Low (temporary tool, no production impact)

## Notes
- No external dependencies beyond Flask (already installed)
- Files are static (no live editing needed)
- Mobile responsive not required (desktop only)
```

---

## Bad Example: Too Vague

```markdown
# Task: Fix the Dashboard

There's something wrong with the dashboard. Some pages don't load correctly. Please investigate and fix it.
```

**Problems:**
- No specific file mentioned
- No root cause identified
- No test criteria
- "Investigate" violates delegation protocol (you investigate, Codex executes)

---

## Bad Example: Too Large

```markdown
# Task: Implement Complete Authentication System

Build a full authentication system with:
- User registration
- Email verification
- Password reset
- JWT tokens
- Session management
- 2FA support
- OAuth integration (Google, GitHub)
- Rate limiting
- Audit logging

Test by creating a full user workflow from registration to authenticated API access.
```

**Problems:**
- Scope too large (>3 files, >100 lines)
- Multiple independent features (should be 5+ separate tasks)
- Test criteria too vague
- Would take >30 minutes (Codex timeout risk)

**Fix:** Break into 7 separate tasks, starting with "Implement User Registration Endpoint"

---

## Template Checklist

Before delegating, verify your TASK.md has:

- [ ] **Context** — Which files? Which functions? Line numbers?
- [ ] **Root Cause** (for bugs) — What's wrong? Evidence?
- [ ] **Specification** — Exact changes needed, with line numbers when possible
- [ ] **Test Command** — Deterministic verification (curl/pytest/script)
- [ ] **Scope** — Max 3 files, ~100 lines, <30 min estimate
- [ ] **Risk Level** — Low/Medium/High based on production impact

If missing any of these, your TASK.md is not ready for delegation.
