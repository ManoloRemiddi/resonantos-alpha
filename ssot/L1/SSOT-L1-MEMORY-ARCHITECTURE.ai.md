Updated: 2026-03-27
[AI-OPTIMIZED] ~350 tokens | src: SSOT-L1-MEMORY-ARCHITECTURE.md | Updated: 2026-03-27

# Memory Architecture — 4-Layer Stack

| Layer | What | ~Tokens | Delivery |
|-------|------|---------|----------|
| MEMORY.md | Curated long-term | ~15K | Workspace injection (main only) |
| RECENT-HEADERS.md | Last 20 log headers | ~5K | R-Awareness always-on |
| LCM | Session compression | Session | Context engine plugin (v0.3.0) |
| RAG | Semantic search | On-demand | Ollama/nomic-embed-text, 4810 chunks |

## Memory Log Pipeline
Logs in `memory/shared-log/` (113+ files), 3-part DNA format (Process Log, Trilemma, DNA Sequencing).
- **Intraday cron** (3h, Opus): live session → DNA log
- **Daily cron** (04:30, Opus): nightly safety net
- **Header gen** (06:00, MiniMax): rebuild RECENT-HEADERS.md
- **Archivist** (05:30, MiniMax): SSoT drift detection

Breadcrumbs: `memory/breadcrumbs.jsonl` (real-time capture, cleared after log written).
