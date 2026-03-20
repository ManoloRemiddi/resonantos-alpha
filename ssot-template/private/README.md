# Private SSoT

**This directory is NEVER shared, committed, or distributed.**

Contents are specific to this deployment instance:
- Infrastructure details (VM, hosting, hardware)
- Business plans and financial projections
- Camouflage/operational security strategies
- Model pricing and token strategies
- Wallet addresses and deployment configs
- Any doc containing information specific to THIS operator

## Enforcement
- `.gitignore` blocks this directory
- Shield data leak scanner blocks `ssot/private/` in git diffs
- Logician rule: `protected_path("ssot/private/")`
- Pre-push hook rejects commits containing these files

## For ResonantOS users
Your private docs go here. The `L0-L4` directories contain generic, shareable system knowledge. This directory is YOUR space.
