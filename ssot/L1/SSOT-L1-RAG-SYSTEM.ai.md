[AI-OPTIMIZED] ~160 tokens | src: SSOT-L1-RAG-SYSTEM.md | Updated: 2026-03-10

| Field | Value |
|-------|-------|
| Level | L1 | Status | Active | Updated | 2026-03-06 |

## Overview
Per-agent RAG via SQLite + Ollama embeddings (nomic-embed-text). Each agent has own DB with embedded documents searchable at runtime.

## Architecture
```
Dashboard UI (Settings → Knowledge Base)
  → Flask API (server_v2.py)
  → Per-agent SQLite: ~/.openclaw/memory/{agent}.sqlite
     Agents: main / voice / coder / ...
```

## SQLite Schema (per agent)
| Table | Purpose |
|-------|---------|
| files | Source files (path, name, hash) |
| chunks | Text chunks from files |
| embedding_cache | Cached embeddings |
| chunks_fts | Full-text search index |

## SSoT Level Access
| Level | Path | Purpose |
|-------|------|---------|
| L0 | ssot/L0/ | Foundation docs |
| L1 | ssot/L1/ | Architecture specs |
| L2 | ssot/L2/ | Project docs |
Each agent: L0/L1/L2 access toggled independently via dashboard.

## Common KB
Path: `~/.openclaw/knowledge/common/` | Shared across agents | Toggle per agent via Memory Log switch.

## API (server_v2.py)
- `GET /api/knowledge/base` — KB folders + files per agent
- `GET /api/knowledge/ssot` — SSoT access config
- `POST /api/knowledge/ssot-access` — `{agentId, level, enabled}`
- `POST /api/knowledge/common-access` — `{agentId, enabled}`
- `POST /api/knowledge/upload` — form-data: `folder=<agent>`, `file=<binary>`
- `GET/DELETE /api/knowledge/file` — preview/delete

## Current Data
main: 1,246 files, 20,806 chunks | voice: 166 files, 1,067 chunks

## Locations
Dashboard: `/dashboard/templates/settings.html`
Server: `/dashboard/server_v2.py`
Storage: `~/.openclaw/memory/*.sqlite`
