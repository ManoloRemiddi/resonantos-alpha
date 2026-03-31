# ResonantOS Logician

**The Verifiable Reasoning Engine for ResonantOS**

The Logician is the "second brain" of ResonantOS — a deductive reasoning engine powered by [Google Mangle](https://github.com/google/mangle) that can **prove** things, not just guess them.

## Architecture

```
Claude (Oracle) ←→ Semantic Bridge ←→ Mangle (Logician)
     ↓                                       ↓
  Generate                              Verify Rules
  Hypothesize                          Check Facts  
  Reason                               Deduce New Facts
```

**Oracle (Claude):** Creative, probabilistic reasoning  
**Logician (Mangle):** Deterministic, provable deduction

## Quick Start

### 1. Start the Mangle Server

```bash
cd mangle-service
./mangle-server --source=../poc/demo_rules.mg
```

### 2. Run the Python Demo

```bash
python3 poc/logician_client.py
```

### 3. Query Directly (grpcurl)

```bash
cd mangle-service
~/go/bin/grpcurl -plaintext -import-path ./proto -proto mangle.proto \
  -d '{"query": "can_spawn(/strategist, X)", "program": ""}' \
  localhost:8080 mangle.Mangle.Query
```

## Example Queries

| Query | Description | Result |
|-------|-------------|--------|
| `agent(X)` | List all agents | /strategist, /coder, /designer, /researcher |
| `can_spawn(/strategist, X)` | Who can Strategist spawn? | /coder, /designer, /researcher |
| `can_spawn(/coder, X)` | Who can Coder spawn? | (empty - no permissions) |
| `requires_verification(X)` | Actions needing verification | /send_email, /delete_file |
| `is_admin(/user1)` | Prove admin status | TRUE |

## Use Cases

### 1. Constitutional Checks (Shield)
```datalog
requires_verification(Action) :-
    action_type(Action, /external).
```
→ "Send email requires verification — this is provable from the rules"

### 2. Agent Permissions  
```datalog
can_spawn(Agent, Target) :-
    agent(Agent),
    agent(Target),
    allowlist(Agent, Target).
```
→ "Strategist CAN spawn Coder — proven by allowlist rule"

### 3. Memory Consistency
```datalog
contradiction(Fact1, Fact2) :-
    memory(Fact1),
    memory(Fact2),
    contradicts(Fact1, Fact2).
```
→ "Contradiction detected — user can't be in Rome AND Milan"

## Files

```
logician/
├── PROJECT.md              # Project overview and roadmap
├── README.md               # This file
├── mangle-service/         # Mangle gRPC server
└── poc/                    # Proof of concept rules + demo client
    ├── demo_rules.mg       # Mangle rules for ResonantOS
    └── logician_client.py  # Python client
```

## Requirements

- Go 1.16+ (for mangle-service)
- Python 3.8+ (for client)
- grpcurl (for direct queries)

## Status

- [x] Mangle server running
- [x] Python client working
- [x] Basic rules (agents, permissions, verification)
- [ ] Semantic Bridge (NL → Mangle)
- [ ] Shield integration
- [ ] Memory integration
- [ ] Production daemon

## Research

See `$HOME/clawd/research/MANGLE_DEEP_RESEARCH.md` for comprehensive research on Mangle integration.

## License

Part of ResonantOS. See main repository for license.

---

*"The Logician doesn't guess — it proves."*
