# AGENTS.md — ResonantOS Alpha

**Read [docs/SUPPORTED-MATRIX.md](docs/SUPPORTED-MATRIX.md) before working.**

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

## File Limits

| Language | Hard Limit |
|----------|------------|
| Python | 1000 lines |
| JavaScript | 1000 lines |

## Module Organization

- Routes → feature files (e.g., `dashboard/routes/agents.py`)
- One feature per file
- `server_v2.py` = thin router only

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
