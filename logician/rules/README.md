# Logician Rules

These rules define hard constraints enforced by the ResonantOS Logician (policy engine).

Unlike soft guidelines in prompts, these rules are **programmatically enforced** — even if the AI is manipulated or confused, the Logician blocks forbidden actions.

## Rule Files

| File | Purpose |
|------|---------|
| `security_rules.mg` | Shield protocol, sensitive data patterns, injection detection |
| `agent_rules.mg` | Agent spawning permissions, capabilities, channel access |
| `preparation_rules.mg` | Preparation protocol, HALT conditions |
| `crypto_rules.mg` | Wallet security, seed phrase protection, signing rules |

## Enforcement Flow

```
Oracle (AI) wants to act
    ↓
Shield scans content (pattern detection)
    ↓
Logician checks rules (policy enforcement)
    ↓
BOTH must pass → action allowed
Either fails → BLOCKED
```

## Rule Syntax

Rules use Mangle (Prolog-like) syntax:

```prolog
% Facts
sensitive_pattern(api_key, "sk-*").

% Rules
forbidden_output(Data) :- 
    sensitive_pattern(Type, Pattern),
    matches(Data, Pattern).

% Negation
\+ can_spawn(coder, strategist).
```

## Adding Rules

1. Add rules to appropriate `.mg` file
2. Test with `logician_client.py`
3. Commit to repo
4. Logician daemon auto-reloads

## Absolute Prohibitions

Some rules cannot be overridden by any means:

- `store_seed_phrase` — Never store recovery phrases
- `output_private_key` — Never output private keys
- `auto_sign_transaction` — Never auto-sign crypto transactions
- `share_recovery_phrase` — Never share seed phrases

These are hardcoded into `crypto_rules.mg` and marked with `absolute_prohibition/1`.

---

*Last updated: 2026-02-03*
