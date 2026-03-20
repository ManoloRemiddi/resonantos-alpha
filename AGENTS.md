# AGENTS.md — ResonantOS Alpha (Public Repo)

## What This Is

ResonantOS is an experience layer built on [OpenClaw](https://github.com/openclaw/openclaw). This is the **public alpha repo** — everything here is user-facing and must work for external testers.

## Feature Support

**Before working on any feature, check the [Supported Feature Matrix](docs/SUPPORTED-MATRIX.md).**

This defines:
- **Core**: Actively supported, tested, expected to work
- **Optional**: Works but may have issues
- **Experimental**: Known issues, high failure risk
- **Legacy**: Deprecated, do not modify unless critical

## Architecture

```
resonantos-alpha/
├── dashboard/           # Flask web UI (server_v2.py) on port 19100
├── agents/             # Agent workflow definitions
├── config/              # Runtime configuration
├── docs/                # Project documentation
├── extensions/          # OpenClaw plugin extensions
├── scripts/             # Maintenance and setup scripts
├── workspace-templates/  # OpenClaw workspace templates
├── shield/              # Security components
├── solana-toolkit/      # Solana blockchain utilities (DevNet)
├── logician/            # Policy engine
├── ssot/                # Single Source of Truth documents
├── experiments/          # Archived experimental code
├── install.js           # One-command installer
└── AGENTS.md            # This file
```

## Key Components

### Dashboard (server_v2.py)
- Flask app, port 19100
- Pages: home, agents, chatbots, r-memory, wallet, bounties, tribes, projects, docs, settings
- Imports from `solana-toolkit/` for blockchain operations
- Uses `config.json` for network settings and program IDs
- Templates use Jinja2 with `base.html` as layout

### Solana Toolkit
- `wallet.py` — SolanaWallet class, reads keypair from `~/.config/solana/id.json`
- `nft_minter.py` — NFTMinter for soulbound NFTs (identity, license, manifesto)
- `token_manager.py` — TokenManager for $RCT and $RES token operations
- `symbiotic_client.py` — Symbiotic Wallet PDA operations
- `protocol_nft_minter.py` — Protocol Store NFT minting
- Network: DevNet by default

### Extensions
- Must export a function that receives an `api` object
- Hooks: `before_turn`, `after_turn`, `before_tool_call`, `after_tool_call`
- Extensions live in `~/.openclaw/extensions/` when installed

## Conventions

- **Python**: Flask, no type hints required, f-strings preferred
- **JavaScript**: CommonJS (`require`), no TypeScript
- **HTML/CSS**: Vanilla JS in templates, no frameworks
- **Blockchain**: Solana DevNet, Anchor framework for on-chain programs
- **Error handling**: Graceful fallbacks. If solana-toolkit is unavailable, routes should return friendly errors, not crash

## Testing

- Dashboard: `cd dashboard && python3 server_v2.py` then hit `http://localhost:19100`
- Solana operations need: `pip3 install solana solders anchorpy`
- Phantom wallet browser extension needed for wallet features (enable Developer Mode + Devnet)

## Important Rules

1. **No private data.** This is a public repo. No keys, no personal paths, no memory files.
2. **Graceful degradation.** If a dependency is missing, show a helpful error, don't crash.
3. **DevNet only.** All Solana operations target devnet. Never mainnet.
4. **Test before claiming fixed.** Run the server, hit the route, verify the response.

## Developer Conventions

These rules prevent single-file bloat and enforce maintainable structure. Follow these in all PRs.

### File Size Limits

| Language | Soft Limit | Hard Limit |
|----------|-----------|------------|
| Python   | 500 lines | 1000 lines |
| JavaScript | 400 lines | 1000 lines |

**If a file exceeds its hard limit, it MUST be split before merging.** No exceptions without explicit reviewer sign-off and a documented justification.

### Module Organization

- **Routes**: Group related routes in feature files (e.g., `dashboard/routes/agents.py`, `dashboard/routes/memory.py`)
- **One feature per file**: Don't dump unrelated functionality into the same file
- **Shared code**: Extract to `shared/` or `lib/` directories
- **Dashboard**: Keep `server_v2.py` as a thin router; actual logic in route modules

### Documentation Requirements

- **Every directory** needs a README.md or at minimum a purpose comment at the top
- **Every function > 20 lines** needs a docstring explaining: what it does, inputs, outputs
- **Update docs when changing behavior**, not after the fact
- **Architecture decisions** go in `docs/architecture/`

### Git Hygiene

- **Rebase only** on main branch — no merge commits
- **git pull before git push** — always pull latest before pushing to avoid conflicts
- **PRs must reference issues**: Include "Fixes #XX" or "Related to #XX" in PR description
- **Branch naming**:
  - `feature/` — new features
  - `fix/` — bug fixes
  - `docs/` — documentation only
  - `cleanup/` — refactoring without behavior change
  - `test/` — test additions only

### Code Review Requirements

- **No file > 500 lines** without explicit reviewer sign-off
- **No "WIP" merges** to main — PRs must be ready or draft
- **CI must pass** before merge (lint, syntax check, smoke tests)
- **Test coverage** for new features; bug fixes should include regression tests

### Testing Expectations

- **New features**: Include basic smoke tests (does it boot? does it return 200?)
- **Bug fixes**: Include a test case that would have caught the bug
- **No test = won't be merged**, except for trivial one-line fixes
- **Test location**: `dashboard/tests/` for dashboard tests, `scripts/` for smoke tests
- **Always run local verification before commit/push**: Execute relevant tests and checks for the files you changed
- **Never mark work done without verification**: If tests cannot run, clearly document what was attempted and why it could not be validated

### CI Enforcement

The following checks run on every PR:

1. Python syntax check (`python3 -m py_compile`)
2. Shellcheck on shell scripts
3. File length check (fail if any .py > 1000 lines or .js > 1000 lines)
4. Smoke test (dashboard boots, core routes return 200)

See `.github/workflows/ci.yml` for the full CI configuration.
