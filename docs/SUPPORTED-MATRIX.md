# Supported Feature Matrix — ResonantOS Alpha

**Status: DRAFT — Subject to Change**

This document defines what is supported, optional, experimental, or legacy in the ResonantOS Alpha. All contributors should use this as the source of truth for "what should I work on?" and "what is the product?"

---

## Core

These features are actively supported, tested, and expected to work. They are the product.

| Feature | Location | Status | Notes |
|---------|---------|--------|-------|
| OpenClaw integration | `extensions/`, `install.js` | ✅ Active | Core extension system |
| Workspace templates | `workspace-templates/` | ✅ Active | Installed by default |
| Setup agent | `install.js` | ✅ Active | Main entry point |
| Dashboard shell | `dashboard/server_v2.py` | ✅ Active | Flask app on port 19100 |
| Core pages | `dashboard/server_v2.py` | ✅ Active | overview, agents, docs, settings |
| Extension hooks | `extensions/r-*.js` | ✅ Active | before_turn, after_turn, etc. |
| R-Awareness | `extensions/r-awareness.js` | ✅ Active | Document injection |
| R-Memory | `extensions/r-memory.js` | ✅ Active | Conversation compression |
| Agent workflows | `agents/GITHUB/` | ✅ Active | Project board integration |
| GitHub project scripts | `scripts/github-project/` | ✅ Active | CI/CD tooling |
| Shell scripts | `scripts/` | ✅ Active | Install, setup, maintenance |

---

## Optional

These features work but may have issues. They are supported with best-effort.

| Feature | Location | Status | Notes |
|---------|---------|--------|-------|
| Tandem integration | `dashboard/` (routes) | ⚠️ Works | Integration present, may have rough edges |
| Projects/Todo board | `dashboard/` (routes) | ⚠️ Works | GitHub Projects integration |
| Logician | `logician/` | ⚠️ Works | Policy engine, functional but complex |
| MCP server | `experiments/mcp-server/` | ⚠️ Moved | Moved to experiments pending stabilization |
| Shield/Security | `shield/` | ⚠️ Works | File guard, delegation gate present |

---

## Experimental

These features are known to have issues, high failure risk, or are incomplete. Use with caution.

| Feature | Location | Status | Known Issues |
|---------|---------|--------|-------------|
| Wallet / Solana | `solana-toolkit/` | 🔴 Issues | DevNet only, may fail |
| Tribes | `dashboard/` (routes) | 🔴 Issues | Incomplete implementation |
| Bounties | `dashboard/` (routes) | 🔴 Issues | Incomplete implementation |
| DAO features | `dashboard/` (routes) | 🔴 Issues | Incomplete implementation |
| Protocol Store | `dashboard/` (routes) | 🔴 Issues | Incomplete implementation |
| Self-improver | `experiments/self-improver/` | 🔴 Issues | Archived, incomplete |
| Watchdog | `experiments/watchdog/` | 🔴 Issues | Archived, incomplete |

---

## Legacy

These features are deprecated, superseded, or archived. Do not modify unless fixing critical bugs.

| Feature | Location | Status | Replacement |
|---------|---------|--------|-------------|
| Old dashboard | `dashboard/server.py` | ❌ Deprecated | `dashboard/server_v2.py` |
| Old path references | Various | ❌ Deprecated | Use centralized path resolution |
| MCP server (root) | `mcp-server/` → `experiments/` | ❌ Archived | `experiments/mcp-server/` |

---

## Decision Tree for Contributors

```
Is it in Core?
  → YES: Work on it, ensure CI passes
  → NO: Is it in Optional?
    → YES: Work on it, document any issues
    → NO: Is it in Experimental?
      → YES: Be careful, high risk of issues
      → NO: Is it in Legacy?
        → YES: Don't modify unless critical bug fix
        → NO: Ask before working on it
```

---

## How to Update This Document

When making changes that affect feature status:

1. Update this matrix in the same PR
2. If adding a new feature, classify it appropriately
3. If deprecating a feature, move it to Legacy
4. If a feature stabilizes, move it from Experimental → Optional or Core

---

## Related Documents

- [Directory Inventory](directory-inventory.md) — Directory structure and ownership
- [Developer Conventions](../AGENTS.md) — Coding standards and testing requirements
- [CI Workflow](../.github/workflows/ci.yml) — Automated testing
