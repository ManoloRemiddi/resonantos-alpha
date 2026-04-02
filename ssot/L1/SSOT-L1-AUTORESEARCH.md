<!-- TEMPLATE: Customize this file for your deployment -->
# Autoresearch — Autonomous AI Experimentation
Updated: 2026-03-24

**Status:** Cloned — Adapting to GX10 Stack
**Created:** 2026-03-24
**Source:** [karpathy/autoresearch](https://github.com/karpathy/autoresearch) (MIT license)
**Parent:** Project Human Data, Internal Benchmark V7, R-Memory

---

## 1. What It Is

An autonomous experimentation loop where an AI agent modifies code, trains for a fixed time budget, evaluates results, keeps improvements or discards, and repeats — indefinitely without human intervention.

Created by Andrej Karpathy (March 2026). 42K GitHub stars in first week. MIT licensed.

**The paradigm shift:** You don't write code. You write `program.md` — the research strategy. The agent does the experimentation. Karpathy calls it "programming the program."

---

## 2. Why We Need It

### The Problem
We have multiple models that need optimization for OUR specific workload:
- Audio transcription accuracy for Manolo's accent
- Memory compression quality
- WHY extraction from transcripts
- Agent-specific fine-tuning

Cloud APIs cost money. Manual experimentation is slow. GX10 will sit idle overnight.

### The Solution
GX10 runs autoresearch loops 24/7. While Manolo sleeps: ~100 experiments per night. Each experiment trains, evaluates, keeps or discards. Autonomous improvement.

### The Connection
This is Augmentatism applied to itself. The system improves the system. Sovereign, local, no cloud dependency. The AI researcher runs on our hardware, improving our models, for our use cases.

---

## 3. Architecture (Original)

```
program.md (human writes strategy)
     │
     ▼
AI Agent (Claude/Codex/etc.)
     │
     ├─► Reads program.md + train.py + prepare.py
     ├─► Modifies train.py (architecture, hyperparams, optimizer)
     ├─► Runs: uv run train.py (5-min fixed budget)
     ├─► Evaluates: val_bpb (lower = better)
     ├─► Keeps improvement OR reverts
     └─► Logs to results.tsv
         │
         └─► LOOP FOREVER (until human stops)
```

**Three files that matter:**
| File | Role | Who Edits |
|------|------|-----------|
| `prepare.py` | Fixed: data prep, tokenizer, evaluation harness | Nobody (read-only) |
| `train.py` | Training code: model, optimizer, loop | Agent only |
| `program.md` | Research strategy and instructions | Human only |

**Design constraints:**
- Single GPU, single file
- Fixed 5-min training budget (wall clock)
- Metric: val_bpb (validation bits per byte) — lower is better
- ~12 experiments/hour, ~100 overnight
- Keep/discard based on metric improvement
- Git branch per run, commit per experiment

---

## 4. Our Adaptation

### 4.1 Hardware Target

| Spec | Original (Karpathy) | Ours (GX10) |
|------|---------------------|-------------|
| GPU | H100 (80GB) | GB10 Blackwell (128GB unified) |
| Framework | PyTorch + FA3 | PyTorch + NGC containers |
| Platform | Linux | Linux (NVIDIA Ubuntu) |
| Runtime | uv + Python | NGC container + uv |
| Availability | Overnight | 24/7 |

**Key difference:** GB10 has 128GB unified memory vs H100's 80GB HBM3. Can train larger models. But GB10 may have different compute characteristics (tensor core config, memory bandwidth). First experiments will establish our baseline.

### 4.2 Research Programs (Our Use Cases)

Each use case gets its own `program.md` and dedicated branch.

#### Program 1: Audio Transcription Optimization
**Goal:** Fine-tune Parakeet v3 or train a custom model for Manolo's accent/vocabulary.
**Metric:** WER on known recordings (TOL sessions with manual transcripts).
**Why:** Standard models misinterpret non-native English. Custom vocabulary + accent adaptation = dramatically better transcription.
**When:** After GX10 setup + audio pipeline Phase 2 (late March/early April).

#### Program 2: Memory Compression
**Goal:** Fine-tune a small model (1-4B) for lossless context compression.
**Metric:** Fidelity score — compress then decompress, measure information retention.
**Why:** R-Memory needs a local compression model. We have 186+ compression pairs and 207 narrative pairs for training data. Currently using cloud models.
**When:** After Program 1 baseline established.

#### Program 3: WHY Extraction
**Goal:** Train a model to extract reasoning/decisions/intent from raw transcripts.
**Metric:** Structured output quality score (automated eval: does output contain WHY for each decision?).
**Why:** Core requirement of Project Human Data. Granola extracts WHAT. We need WHY.
**When:** After audio pipeline produces initial transcripts.

#### Program 4: Agent Role Optimization
**Goal:** Fine-tune small models for specific ResonantOS agent roles.
**Metric:** Internal Benchmark V7 scores per agent category.
**Why:** MiniMax M2.7 is generic. Purpose-built models for heartbeat, content scout, research could outperform at lower cost.
**When:** Future — after programs 1-3 demonstrate the loop works.

#### Program 5: General Research
**Goal:** Open-ended experimentation on any topic.
**Metric:** Varies per experiment.
**Why:** The loop is a general-purpose tool. Any ML question can be explored autonomously.
**When:** Ongoing, whenever GX10 has idle cycles.

### 4.3 Orchestration Architecture

```
Mac Mini (orchestrator)
     │
     ├─► Selects program.md for tonight's research
     ├─► Triggers GX10 via HTTP API
     ├─► Monitors progress (results.tsv polling)
     └─► Morning: generates digest → memory log
         │
GX10 (executor)
     │
     ├─► Runs AI agent (local Nemotron or cloud API)
     ├─► Agent reads program.md
     ├─► LOOP: modify → train → evaluate → keep/discard
     ├─► Logs all experiments to results.tsv + git
     └─► Runs until stopped or program.md says done
```

**Agent choice for the loop:**
- **Phase 1 (cloud):** Codex CLI or Claude Code — proven with autoresearch, reliable
- **Phase 2 (sovereign):** Nemotron Super 120B on GX10 — the agent runs on the same machine it's training on. Full sovereignty.

### 4.4 Adaptations Required

| Component | Original | Our Version |
|-----------|----------|-------------|
| `prepare.py` | Climbmix-400B dataset, BPE tokenizer | Custom per-program (audio data, memory data, etc.) |
| `train.py` | GPT architecture, Muon+AdamW | Varies: LoRA fine-tuning, custom architectures |
| `program.md` | Generic "lower val_bpb" | Research-specific strategy per use case |
| GPU | H100 CUDA | GB10 Blackwell CUDA (NGC container) |
| Metric | val_bpb only | Program-specific (WER, fidelity, quality scores) |
| Agent | Claude/Codex (cloud) | Phase 1: cloud agent, Phase 2: local Nemotron |
| Runtime | 5-min budget | Configurable per program (5-30 min) |
| Logging | results.tsv only | results.tsv + memory log integration |

---

## 5. Implementation Phases

### Phase 0: Clone + Understand (Now — 2026-03-24) ✅
- [x] Clone repo to `research/autoresearch/`
- [x] Read all three core files
- [x] Understand the loop mechanics
- [x] Create SSoT doc
- [ ] Create adapted `program.md` template for our stack
- [ ] Create `program-audio.md` (Program 1 draft)

### Phase 1: GX10 Baseline (Sat Mar 28 — GX10 arrives)
- [ ] Install uv + dependencies in NGC container
- [ ] Run original autoresearch baseline (5-min train on default nanochat)
- [ ] Record GX10-specific baseline numbers (val_bpb, VRAM, MFU)
- [ ] Compare to Karpathy's H100 results
- [ ] Verify the full loop works: agent modifies → trains → evaluates → keeps/discards

### Phase 2: First Custom Program (Week of Mar 31)
- [ ] Prepare custom dataset (Manolo's audio transcripts with corrections)
- [ ] Write custom `prepare.py` for audio domain
- [ ] Write `program-audio.md` research strategy
- [ ] Run first autonomous overnight session
- [ ] Morning review: analyze results, update strategy

### Phase 3: Multi-Program Rotation (April)
- [ ] Program scheduler: rotate between research programs
- [ ] Memory integration: experiment results → breadcrumbs → memory logs
- [ ] Dashboard: Autoresearch page showing experiment history + charts
- [ ] Nemotron as local agent (sovereignty milestone)

---

## 6. File Layout

```
research/autoresearch/           # Original Karpathy repo (upstream)
research/autoresearch-resonant/  # Our adapted version
├── programs/
│   ├── program-audio.md         # Audio transcription optimization
│   ├── program-memory.md        # Memory compression
│   ├── program-why.md           # WHY extraction
│   ├── program-agent.md         # Agent role optimization
│   └── program-general.md       # Open-ended research
├── prepare/
│   ├── prepare-audio.py         # Audio domain data prep
│   ├── prepare-memory.py        # Memory compression data prep
│   └── prepare-why.py           # WHY extraction data prep
├── train.py                     # Agent-modified training code
├── orchestrator.py              # Mac Mini → GX10 coordination
├── results/                     # Per-program results
│   ├── audio-results.tsv
│   ├── memory-results.tsv
│   └── why-results.tsv
└── README.md                    # Our adaptation docs
```

---

## 7. Key Principles

1. **program.md IS the research.** The quality of the research strategy determines the quality of results. Iterate on programs like you iterate on code.
2. **Fixed time budget = fair comparison.** Every experiment gets the same wall-clock time. Architecture changes, hyperparameter sweeps, model size — all comparable.
3. **Keep/discard is binary.** No "maybe." Improvement = keep. No improvement = revert. This prevents drift.
4. **Git branch = experiment lineage.** Full history of what was tried, what worked, what failed. Reviewable.
5. **Never stop.** The loop runs until manually interrupted. Out of ideas? Think harder. Combine near-misses. Try radical changes. Read papers.
6. **Memory integration.** Unlike Karpathy's version, ours feeds results into the ResonantOS memory system. Every overnight session produces a memory log with WHAT was tried, WHAT worked, and WHY.

---

## 8. References

- Repo: `research/autoresearch/` (upstream clone)
- Karpathy tweet: https://x.com/karpathy/status/2029701092347630069
- VentureBeat: "lets you run hundreds of AI experiments a night"
- Notable fork (memory): tonitangpotato/autoresearch-engram (persistent cognitive memory across sessions)
- Audio pipeline: `SSOT-L1-AUDIO-INTAKE-PIPELINE.md`
- Project Human Data: `SSOT-L2-PROJECT-HUMAN-DATA.md`
- Internal Benchmark: V7 spec in MEMORY.md
