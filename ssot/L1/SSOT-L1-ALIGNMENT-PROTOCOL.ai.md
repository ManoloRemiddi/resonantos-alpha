[AI-OPTIMIZED] ~380 tokens | src: SSOT-L1-ALIGNMENT-PROTOCOL.md | Updated: 2026-03-10

| Field | Value |
|-------|-------|
| ID | SSOT-L1-ALIGNMENT-PROTOCOL-V1 |
| Created | 2026-02-27 | Level | L1 | Status | Draft |
| Depends | SSOT-L0-PHILOSOPHY, SSOT-L0-CONSTITUTION, SSOT-L0-OVERVIEW |

## Purpose
Constitutional compiler for ResonantOS. AI evaluates contributions against criteria → scored alignment report. Attach to PRs/bounties/proposals. Not a style guide — defines boundaries, not what to build.

## Evaluation Order (for AI)
1. Core Principles (P1-P10) → 2. Alignment Tests (Section 4) → 3. Red Lines (Section 5) → 4. Architectural Constraints (Section 6) → 5. Score (Section 7) → 6. Report (Section 8)

## Core Principles (non-negotiable)
| ID | Principle | Test |
|----|-----------|------|
| P1 | Sovereignty Above All | Can user walk away with data? Switch providers? Run locally? |
| P2 | Augmentation not Replacement | Does human remain final decision-maker? |
| P3 | Transparency via Separation | Human/AI/org contributions trackable + auditable? |
| P4 | Deterministic Enforcement | Rules coded, not prompted? |
| P5 | OSS + Local First | Runs without internet? Source available? No mandatory cloud? |
| P6 | Anti-Capture | Data exportable? Exit path exists? |
| P7 | Quality Over Speed | Deterministic evidence of verification? |
| P8 | Process Is Product | Reasoning documented? |
| P9 | Multiverse Over Monoculture | Adapts to individual identity, not forced? |
| P10 | Human Accountability Chain | Responsible human identifiable/verifiable? |

## Alignment Tests
**Technical (T1-T7):** integrates not duplicates, local-first capable, provider-agnostic, data stays local, OSS core, deterministic where possible, fails safely.
**Philosophical (A1-A7):** sovereignty↑, augments not replaces, identity diversity respected, contribution tracking, accountable AI chain, no capture, process documented.
**Economic (E1-E4):** correct token type, no gaming vectors, genuine ecosystem value, sustainable cost.

## Red Lines (Hard Fail — any = score 0)
R1 exfiltrates data w/o consent | R2 single mandatory cloud provider | R3 removes human from governance | R4 hardcoded secrets/keys | R5 claims "fixed" w/o evidence | R6 recursive AI self-replication w/o auth | R7 modifies L0 w/o governance proposal | R8 token-earning bypass quality gates | R9 obfuscated code | R10 discrimination

## Architectural Constraints
- **OpenClaw:** Use extension API hooks (agent_start, agent_end, llm_output, session_before_compact). Memory via MEMORY.md/memory_search only. Tools via OpenClaw tool system. Config via openclaw.json.
- **Solana:** DevNet for testing; Token-2022 new types; Symbiotic PDA for DAO ops; Phantom for human signing; document PDA derivation seeds.
- **Dashboard:** Flask+Jinja2+vanilla JS only. Dark theme CSS vars. Routes in server_v2.py.
- **SSoT:** Correct level (L0-L4). Naming `SSOT-L{n}-{NAME}.md`. Metadata header. `.ai.md` if >2000 tokens.

## Scoring Rubric
90-100 Fully Aligned | 70-89 Aligned | 50-69 Partial | 30-49 Misaligned | 0-29 Rejected
**Weights:** Red Lines=hard gate | Phil (A1-A7)=40% | Tech (T1-T7)=35% | Economic (E1-E4)=15% | Process=10%

## Report Format
```
# Alignment Report
Contribution: type, description, author, date
Red Line Check: R1-R10 table → PASS/FAIL
Technical/Phil/Economic tables with ✅/⚠️/❌/N/A
Overall Score: 0-100
Summary + Issues + Recommendation
```

## Governance Genome (Inheritance)
Every Entity inherits this protocol. Locked sections marked [INHERITED — READ ONLY]. Entities can ADD stricter rules, never weaken. Chain: ResonantOS Constitution → DAO Alignment Protocol → Entity Protocols → Swarm Agents. Cross-entity bounties/portable reputation enabled by shared constitutional root.

## Change Process
Add/modify test → simple majority | Red line change → supermajority all 3 chambers | Core principle → constitutional amendment + timelock | Typos → PR + reviewer
