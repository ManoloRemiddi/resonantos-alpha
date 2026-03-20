# ResonantOS Dashboard

## Overview

Local web dashboard for managing your ResonantOS instance. Runs on `localhost:19100`, no cloud dependency.

| Component | Technology |
|-----------|------------|
| Backend | Python Flask |
| Frontend | Vanilla JS, Jinja2 templates |
| Database | SQLite (local) |
| Dependencies | flask, flask-cors, psutil |

## Pages

| Route | Purpose |
|-------|---------|
| `/` | System health, agent status, uptime |
| `/agents` | Agent orchestrator view, R-Memory model selector |
| `/chatbots` | Chatbot builder, widget embeds |
| `/r-memory` | SSoT document manager, keyword editor, file locking |
| `/wallet` | Symbiotic Wallet, leaderboard, NFTs, protocol store |
| `/projects` | Project tracking |
| `/docs` | Documentation browser |
| `/settings` | System configuration |

## SSoT Manager

The R-Memory page provides a visual document management interface:

- **Document tree** — Browse L0–L4 hierarchy
- **Markdown editor** — Live preview with syntax highlighting
- **Keyword management** — Configure R-Awareness trigger words per document
- **Token display** — Compare raw vs compressed document sizes
- **File locking** — Protect critical documents from accidental modification

## Document Layer Hierarchy

| Layer | Default State | Purpose |
|-------|--------------|---------|
| L0 | Locked | Foundation — vision, philosophy, principles |
| L1 | Locked | Architecture — system specs, component designs |
| L2 | Unlocked | Active projects — current work |
| L3 | Unlocked | Drafts — proposals, experiments |
| L4 | Unlocked | Working notes — session logs, scratch |

Higher layers (L0–L1) are locked by default to prevent accidental modification of foundational documents.

## Starting the Dashboard

```bash
cd ~/resonantos-alpha/dashboard
python3 server_v2.py
```

Access at `http://localhost:19100`

## Design Principles

- **Local-first** — No cloud services, no external APIs, no telemetry
- **Single-file backend** — One Python file, minimal complexity
- **Dark theme** — Easy on the eyes for extended sessions
- **No build step** — No webpack, no npm, no compilation
- **Template auto-reload** — HTML changes reflect immediately (Python changes require restart)
