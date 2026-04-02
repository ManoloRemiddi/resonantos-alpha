# Contributing to ResonantOS

Keep contributions public, reproducible, and reviewable.

## Scope

- Contribute product code, tests, and documentation that belongs in a public alpha.
- Do not add personal notes, live operational logs, secrets, credentials, or machine-specific setup residue.

## Working Rules

- Prefer small, reviewable changes.
- Update documentation when behavior or architecture changes.
- Keep paths portable. Use relative or environment-driven configuration instead of user-specific paths.
- Do not commit generated private data, local databases, chat exports, or local runtime state.

## Verification

Before opening a PR:

- Run the narrowest relevant test or syntax check for the files you changed.
- Re-read the edited files for accidental placeholders, secrets, or environment-specific values.
- Confirm the change still makes sense without any private workspace context.

## Documentation

- `README.md` is the public entry point.
- `docs/SSOT_TEMPLATE.md` is the template for public SSoT documents.
- `ssot/L0/` and `ssot/L1/` contain the public foundation and architecture layer for this snapshot.

## Pull Requests

- Describe the problem, the change, and how you verified it.
- Call out any residual risk or follow-up work directly.
- Keep commit messages specific.
