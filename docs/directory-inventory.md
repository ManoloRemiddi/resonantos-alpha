# Directory Inventory - ResonantOS Alpha

**Updated: 2026-03-20**

This document maps every top-level directory to a classification. The directory structure has been consolidated from 26 → 16 directories.

---

## Classification Key

- **Core**: Active, supported, must work for alpha
- **Optional**: Works but may have issues
- **Experimental**: Known issues, high risk, in archive
- **Legacy**: Deprecated, superseded

---

## Current Directories (16 total)

### Core (11 directories)

| Directory | Purpose | Consolidation Notes |
|-----------|---------|-------------------|
| `dashboard/` | Flask web UI (server_v2.py) on port 19100 | Main user-facing app |
| `agents/` | Agent workflow definitions and runbooks | Contains GITHUB_PROJECT_AGENT_WORKFLOW.md |
| `config/` | Runtime configuration | Now includes `extensions/` subdir with extension configs |
| `docs/` | Project documentation | |
| `scripts/` | Maintenance and setup scripts | Merged from `tools/` |
| `workspace-templates/` | OpenClaw workspace templates | Merged from `templates/` |
| `extensions/` | OpenClaw plugin packages | |
| `shield/` | Security components | Merged `shield-gate/` into this dir |
| `ssot/` | Single Source of Truth documents | Now includes `templates/` subdir |
| `logician/` | Policy engine | |
| `solana-toolkit/` | Solana blockchain utilities | Experimental - DevNet only |

### Optional/Supporting (4 directories)

| Directory | Purpose | Notes |
|-----------|---------|-------|
| `data/` | Data files | Contains nft_registry.json |
| `assets/` | Static assets | Contains banner.png |
| `skills/` | Active skill definitions | Contains node-deploy/ |
| `experiments/` | Archived experimental code | Moved from root (mcp-server, research, self-improver, watchdog) |

**Note:** `bin/` was removed from git. Compiled binaries belong in setup/build flow, not in repo.

---

## Removed/Consolidated Directories

| Old Directory | Action | Date |
|--------------|--------|------|
| `r-awareness/` | Merged into `config/extensions/` | 2026-03-20 |
| `r-memory/` | Merged into `config/extensions/` | 2026-03-20 |
| `shield-gate/` | Merged into `shield/` | 2026-03-20 |
| `ssot-template/` | Merged into `ssot/templates/` | 2026-03-20 |
| `templates/` | Merged into `workspace-templates/` | 2026-03-20 |
| `tools/` | Merged into `scripts/` | 2026-03-20 |
| `mcp-server/` | Moved to `experiments/` | Phase 1 |
| `research/` | Moved to `experiments/` | Phase 1 |
| `self-improver/` | Moved to `experiments/` | Phase 1 |
| `watchdog/` | Moved to `experiments/` | Phase 1 |

---

## Current Root Structure

```
resonantos-alpha/
├── dashboard/              # Core: Flask web UI
├── agents/               # Core: Agent workflows
├── config/               # Core: Configuration (with extensions/ subdir)
├── docs/                 # Core: Documentation
├── scripts/              # Core: Scripts (merged from tools/)
├── workspace-templates/  # Core: Templates (merged from templates/)
├── extensions/           # Core: OpenClaw extensions
├── shield/              # Core: Security (merged shield-gate/)
├── logician/            # Optional: Policy engine
├── ssot/                # Optional: SSOT docs (merged ssot-template/)
├── solana-toolkit/     # Experimental: Solana utilities
├── bin/                 # Supporting: Binary utilities
├── data/                # Supporting: Data files
├── assets/              # Supporting: Static assets
├── skills/              # Supporting: Skills
├── experiments/          # Archive: Experimental code
├── install.js           # Root: Main installer
└── AGENTS.md            # Root: Agent instructions
```

---

## Classification Summary

| Status | Count | Directories |
|--------|-------|-------------|
| Core | 11 | dashboard, agents, config, docs, scripts, workspace-templates, extensions, shield, logician, solana-toolkit, bin |
| Supporting | 4 | data, assets, skills, install.js |
| Archive | 1 | experiments/ |

---

## Related Documents

- [Supported Feature Matrix](SUPPORTED-MATRIX.md) — Feature classification
- [Developer Conventions](../AGENTS.md) — Coding standards
