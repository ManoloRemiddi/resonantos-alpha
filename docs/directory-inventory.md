# Directory Inventory - ResonantOS Alpha

## Purpose
This document maps every top-level directory to a classification and proposes consolidation.

## Classification Key
- **Core**: Active, supported, must work for alpha
- **Optional**: Works but may have issues
- **Experimental**: Known issues, high risk
- **Legacy**: Deprecated, superseded
- **Archive**: Moved here, preserved for reference

---

## Current Directories

### Core (Supported)

| Directory | Purpose | Notes |
|-----------|---------|-------|
| `dashboard/` | Flask web UI (server_v2.py) on port 19100 | Main user-facing app |
| `agents/` | Agent workflow definitions and runbooks | Contains GITHUB_PROJECT_AGENT_WORKFLOW.md |
| `config/` | Runtime configuration | |
| `docs/` | Project documentation | |
| `scripts/` | Maintenance and setup scripts | |
| `tools/` | Maintenance utilities | Overlaps with scripts/ |
| `bin/` | Binary utilities | Small, unclear purpose |
| `assets/` | Static assets | |
| `workspace-templates/` | OpenClaw workspace templates | |
| `templates/` | General templates | Overlaps with workspace-templates/ |

### Extensions (OpenClaw Plugins)

| Directory | Purpose | Notes |
|-----------|---------|-------|
| `extensions/` | OpenClaw extension packages | Contains r-awareness.js, r-memory.js, shield-gate, etc. |
| `r-awareness/` | Contextual document injection | **EMPTY** - only config.json, content in extensions/r-awareness.js |
| `r-memory/` | Conversation compression | **EMPTY** - only config.json, content in extensions/r-memory.js |

### Security

| Directory | Purpose | Notes |
|-----------|---------|-------|
| `shield/` | Security components | daemon.py, file_guard.py, shield-gate.js, watchdog/, delegation-gate.js |
| `shield-gate/` | Security gate implementation | **OVERLAP** - only index.js, shield-gate.js exists in shield/ |

### Knowledge/Reasoning (Optional)

| Directory | Purpose | Notes |
|-----------|---------|-------|
| `logician/` | Deterministic Policy Engine | rules/, skills/, mangle-service/, scripts/ |
| `ssot/` | Single Source of Truth levels | L1/, L2/, L4/ |
| `ssot-template/` | SSOT doc templates | L0/, L1/, L2/, L3/, L4/, SSOT-STRUCTURE.md |

### Solana (Optional/Experimental)

| Directory | Purpose | Notes |
|-----------|---------|-------|
| `solana-toolkit/` | Solana blockchain utilities | DevNet only |

### Experimental

| Directory | Purpose | Notes |
|-----------|---------|-------|
| `logician/` | See above | |
| `self-improver/` | Self-improvement engine | engine.py, requirements.txt |
| `watchdog/` | Process watchdog | watchdog.py, plist |
| `mcp-server/` | MCP server implementation | |
| `research/` | Unclear | No clear purpose |

### Skills (Uncategorized)

| Directory | Purpose | Notes |
|-----------|---------|-------|
| `skills/` | Skills/agents | **EMPTY or near-empty** |

---

## Identified Problems

### 1. extensions/ vs r-awareness/ vs r-memory/
- `r-awareness/` contains only config.json - actual code is in `extensions/r-awareness.js`
- `r-memory/` contains only config.json and config.json.bak - actual code is in `extensions/r-memory.js`
- **Proposed**: Move config.json files to `config/extensions/` and remove the empty wrappers

### 2. shield/ vs shield-gate/
- `shield/` contains `shield-gate.js` (and more)
- `shield-gate/` contains only `index.js`
- **Proposed**: `shield-gate/` is redundant - merge into `shield/` or clarify that `shield-gate/` is the "real" implementation

### 3. ssot/ vs ssot-template/
- `ssot/` contains L1/, L2/, L4/ (implementation levels)
- `ssot-template/` contains L0/, L1/, L2/, L3/, L4/ (templates)
- **Proposed**: `ssot/` = actual docs, `ssot-template/` = template source. Clarify naming.

### 4. scripts/ vs tools/
- Both contain maintenance utilities
- **Proposed**: Consolidate into `scripts/`, move `tools/` contents

### 5. workspace-templates/ vs templates/
- Overlapping purpose
- **Proposed**: Consolidate into `workspace-templates/`

### 6. Experimental code at root level
- `logician/`, `self-improver/`, `watchdog/`, `mcp-server/`, `research/` all at root
- **Proposed**: Move to `experiments/` subdirectory

### 7. skills/ is empty/unused
- **Proposed**: Remove or document purpose

---

## Proposed Structure

After Phase 2 consolidation:

```
resonantos-alpha/
├── dashboard/           # Core: Flask web UI
├── agents/             # Core: Agent workflows
├── config/             # Core: Configuration (including extension configs)
├── docs/               # Core: Documentation
├── scripts/            # Core: Maintenance scripts (merged from tools/)
├── workspace-templates/ # Core: OpenClaw templates (merged from templates/)
├── extensions/          # Core: OpenClaw extensions (r-awareness, r-memory, shield, etc.)
├── shield/              # Core: Security components (merged shield-gate/ into here)
├── ssot/                # Optional: SSOT documents (L1, L2, L4)
├── logician/            # Optional: Policy engine
├── solana-toolkit/     # Experimental: Solana utilities
├── experiments/        # Archive: Experimental code
│   ├── self-improver/
│   ├── watchdog/
│   ├── mcp-server/
│   └── research/
├── .github/            # GitHub config (CI, PR template, issue template)
├── install.js         # Root entry point
└── AGENTS.md          # Root agent instructions
```

**Target: ~12 directories at root (down from 26)**

---

## Phase 3: Root Cleanup Checklist

- [ ] Add README.md to every remaining root directory
- [ ] Create CONTRIBUTING.md with directory conventions
- [ ] Update AGENTS.md architecture diagram to reflect new structure
