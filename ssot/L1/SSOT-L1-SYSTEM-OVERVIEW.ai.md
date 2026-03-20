[AI-OPTIMIZED] ~1350 tokens | src: SSOT-L1-SYSTEM-OVERVIEW.md | Updated: 2026-03-16

## 1. System Stack

ResonantOS: experience layer ON TOP of OpenClaw. Integrates, never fights the kernel.

## 2. OpenClaw Kernel

**Gateway:** port 18789, Node.js daemon. Config: ~/.openclaw/config file.
**Sessions:** Main (agent:main:main) + sub-agents (isolated). SQLite-backed.
**LCM:** Lossless Context Management (v0.3.0) — context engine plugin, handles compaction.

### 2.1 Models
| Model | Role |
|-------|------|
| Opus 4.6 | Main session + memory log crons (reasoning) |
| MiniMax-M2.5 | Sub-agents, heartbeat, most crons (workhorse) |
| Codex CLI (gpt-5.4) | All code writing — external tool, NOT an OpenClaw agent |
| Sonnet 4.5 | First fallback |

### 2.2 Agents (10)
| Category | Agents |
|----------|--------|
| Stateful | main, deputy, voice, setup, website, dao |
| Tool | acupuncturist, blindspot |
| Task | researcher, creative |

Deputy mirrors main's spawn permissions, shares memory via symlinks. Cross-agent spawning via Logician rules.

### 2.3 Channels
**Telegram:** Primary (chatId: YOUR_TELEGRAM_CHAT_ID). **Webchat:** Secondary.

### 2.4 Platform Security Configuration

| Setting | Value | Rationale |
|---------|-------|-----------|
| tools.sessions.visibility | tree (explicit) | Own session + spawned subagents only. self=breaks monitoring, agent=leaks cross-session, all=dangerous. |
| session.dmScope | main (default) | DMs collapse to one session. Multi-user: per-channel-peer. |

**Key distinctions:** Session key = routing (not auth). Lane = single-writer correctness (not privacy). Queue modes: collect (default), followup (wait), steer (inject at tool boundaries).

## 3. Memory Architecture (4-Layer Stack)

| Layer | What | Tokens | Persistence |
|-------|------|--------|-------------|
| MEMORY.md | Long-term curated knowledge | ~15K | Permanent, main session only |
| RECENT-HEADERS.md | Last 20 memory log headers | ~5K | FIFO, always-on via R-Awareness |
| LCM | Session history compression | Session | Automatic via context engine |
| RAG | Semantic vector search | On-demand | Ollama/nomic-embed-text embeddings |

### Key Paths
- Memory logs: memory/shared-log/MEMORY-LOG-YYYY-MM-DD[-suffix].md
- Breadcrumbs: memory/breadcrumbs.jsonl
- Headers: ssot/L1/RECENT-HEADERS.md (auto-generated, 20-header FIFO)
- Research: ~/resonantos-alpha/research/ (19 files, RAG-indexed)

### Memory Log Crons
| Cron | Schedule | Model | Purpose |
|------|----------|-------|---------|
| intraday-memory-log | Every 3h | Opus | DNA-format log from live session |
| daily-memory-log-dna | 04:30 Rome | Opus | Nightly safety net |
| Memory Archivist | 05:30 Rome | MiniMax | SSoT drift detection |
| header-generation | 06:00 Rome | MiniMax | Rebuild RECENT-HEADERS.md |

## 4. ResonantOS Components

| Component | Status | Deep Dive |
|-----------|--------|-----------|
| Shield | Active, 14 blocking layers | SSOT-L1-SHIELD |
| Logician | Active, 285 facts, 10 rules | SSOT-L1-LOGICIAN |
| Dashboard | Active, Flask :19100, 17 pages | SSOT-L1-DASHBOARD |
| R-Awareness | Active V3, compound keywords | SSOT-L1-R-AWARENESS |
| Watchdog | Active, 2 LaunchAgents | SSOT-L1-WATCHDOG-ARCHITECTURE |
| LCM | Active, context engine v0.3.0 | - |
| Heuristic Auditor | Active, post-response audit | - |
| Guardian/Wallet/DAO | Design phase | respective SSoTs |

### Plugins (6 active)
coherence-gate, heuristic-auditor, lossless-claw, r-awareness, shield-gate, usage-tracker. R-Memory v6: DISABLED.

## 5. Extension Architecture

5 custom plugins + 1 stock (LCM). Source of truth: `repo/extensions/{name}/`. Deployed to `~/.openclaw/extensions/` via `scripts/sync-extensions.sh`.

| Extension | Purpose |
|-----------|---------|
| shield-gate | 16 blocking security layers |
| coherence-gate | Task coherence enforcement |
| r-awareness | SSoT keyword injection, coldStartDocs |
| heuristic-auditor | Post-response quality audit |
| usage-tracker | Token/cost tracking |
| lossless-claw | LCM context engine (stock) |

Symlinks blocked by OpenClaw boundary security. Deploy via copy script only. Never edit `~/.openclaw/extensions/` directly.

Shield layers: 1 (destructive), 1.5 (delegation), 2 (coherence), 3 (coding gate), 4 (context isolation), 5 (research discipline), 6a-g+6l (7 gates), 7 (external action), 8 (post-compaction), 10 (network allowlist, fail-closed), 11 (sensitive path, main exempt). Total: 16 blocking.

## 6. SSoT Navigation

| Level | Path | How to Access |
|-------|------|---------------|
| L0 | ssot/L0/ | Always-on overview + keyword triggers |
| L1 | ssot/L1/ | Keyword triggers or /R load |
| L2 | ssot/L2/ | Keyword triggers |
| L3-L4 | ssot/L3-L4/ | Manual read |
| archive | ssot/archive/ | Manual read only |

Convention: .md = source of truth. Compressed derivatives (50-80% smaller). Edit .md first, regenerate compressed version.

## 6. Infrastructure

- Host: Mac Mini M4 (16GB, 256GB SSD)
- Backup: Time Machine + Backblaze + git
- LaunchAgents: 7 (gateway, dashboard, shield, logician, watchdog, watchdog-health, mangle-server)
- GitHub: ResonantOS org (alpha=public, augmentor=private NEVER reference publicly)
- Version: 0.5.3
