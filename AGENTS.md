# AGENTS.md — ResonantOS Alpha

**Read [docs/SUPPORTED-MATRIX.md](docs/SUPPORTED-MATRIX.md) before working.**

## Architecture

```
resonantos-alpha/
├── dashboard/           # Flask web UI (server_v2.py) on port 19100
├── agents/             # Agent workflow definitions
├── config/              # Runtime config (incl. extensions/)
├── docs/               # Project documentation
├── extensions/          # OpenClaw plugin extensions
├── scripts/             # Maintenance scripts
├── workspace-templates/  # OpenClaw templates
├── shield/             # Security components
├── logician/           # Policy engine
├── ssot/               # SSOT documents
├── solana-toolkit/     # Solana utilities (DevNet)
├── data/               # Data files
├── assets/             # Static assets
├── skills/             # Skill definitions
├── experiments/         # Archived experimental code
├── archive/            # Archived legacy files
├── install.js          # Main installer
└── AGENTS.md          # This file
```

## Key Components

### Dashboard (server_v2.py)
- Flask app, port 19100
- Pages: home, agents, chatbots, r-memory, wallet, bounties, tribes, projects, docs, settings
- Imports from `solana-toolkit/` for blockchain operations
- Uses `config.json` for network settings and program IDs

### Extensions
- Must export a function that receives an `api` object
- Hooks: `before_turn`, `after_turn`, `before_tool_call`, `after_tool_call`
- Extensions live in `~/.openclaw/extensions/` when installed

### Solana Toolkit
- `wallet.py` — SolanaWallet class, reads keypair from `~/.config/solana/id.json`
- `nft_minter.py` — NFTMinter for soulbound NFTs (identity, license, manifesto)
- Network: DevNet by default

## Core Rules

1. **No private data.** Public repo. No keys, paths, or memory files.
2. **Graceful degradation.** Missing deps → friendly error, not crash.
3. **DevNet only.** Solana ops target devnet. Never mainnet.
4. **Test before claiming fixed.** Run the server, hit the route, verify.
5. **git pull before push.** Always pull latest before pushing.

## Conventions

- **Python**: Flask, f-strings, no type hints required
- **JavaScript**: CommonJS (`require`), no TypeScript
- **HTML/CSS**: Vanilla JS in templates
- **Error handling**: Graceful fallbacks

## File Limits

| Language | Hard Limit |
|----------|------------|
| Python | 1000 lines |
| JavaScript | 1000 lines |

## Module Organization

- Routes → feature files (e.g., `dashboard/routes/agents.py`)
- One feature per file
- `server_v2.py` = thin router only
- Shared code → `shared/` or `lib/`

## Git Hygiene

- Rebase only — no merge commits
- PRs reference issues: `Fixes #XX`
- Branch naming: `feature/`, `fix/`, `docs/`, `cleanup/`, `test/`

## Testing

- **New features**: smoke tests required
- **Bug fixes**: include regression test
- **Location**: `dashboard/tests/`, `scripts/`
- Run local verification before commit/push

## CI

Checks on every PR: Python syntax, ShellCheck, file length, smoke test.

See `.github/workflows/ci.yml`
