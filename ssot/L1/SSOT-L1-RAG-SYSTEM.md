# SSOT-L1-RAG-SYSTEM — Knowledge Base & RAG System

**Level:** L1 (Architecture)  
**Last Updated:** 2026-03-06  
**Status:** Active

---

## Overview

The Knowledge Base system provides per-agent RAG (Retrieval-Augmented Generation) capabilities. Each agent has its own SQLite database containing embedded documents that can be searched at runtime.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Dashboard UI                              │
│  Settings → Knowledge Base                                  │
│  - SSoT toggles (L0/L1/L2)                                 │
│  - Memory Log (Common KB)                                  │
│  - File upload/delete                                       │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                 Flask API (server_v2.py)                    │
│  /api/knowledge/base     - KB folders & files              │
│  /api/knowledge/ssot    - SSoT access config              │
│  /api/knowledge/ssot-access - Toggle SSoT per agent        │
│  /api/knowledge/common-access - Toggle Common KB per agent │
│  /api/knowledge/upload  - Upload file to agent KB          │
│  /api/knowledge/file   - Preview/delete files              │
└────────────────────────┬────────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         ▼               ▼               ▼
    ┌─────────┐   ┌─────────┐   ┌─────────┐
    │  main   │   │  voice  │   │  coder  │
    │.sqlite  │   │.sqlite  │   │.sqlite  │
    └─────────┘   └─────────┘   └─────────┘
```

## Per-Agent SQLite Schema

Each agent database (`~/.openclaw/memory/{agent}.sqlite`):

| Table | Purpose |
|-------|---------|
| `files` | Original source files (path, name, hash) |
| `chunks` | Text chunks extracted from files |
| `embedding_cache` | Cached embeddings |
| `chunks_fts` | Full-text search index |

## SSoT Level Access

| Level | Path | Purpose |
|-------|------|---------|
| L0 | `ssot/L0/` | Foundational docs (Philosophy, Constitution) |
| L1 | `ssot/L1/` | Architecture & system specs |
| L2 | `ssot/L2/` | Project docs, guides |

Each agent can be granted/denied access to each SSoT level via dashboard toggles.

## Common KB

Shared folder accessible to multiple agents:
- Path: `~/.openclaw/knowledge/common/`
- Controlled via Memory Log toggle per agent
- Allows sharing knowledge across agents

## API Reference

### GET /api/knowledge/base
Returns knowledge base folders and files per agent.

### GET /api/knowledge/ssot
Returns SSoT access config for all agents.

### POST /api/knowledge/ssot-access
```json
{"agentId": "main", "level": "L0", "enabled": true}
```

### POST /api/knowledge/common-access
```json
{"agentId": "main", "enabled": true}
```

### POST /api/knowledge/upload
Form-data: `folder=main`, `file=<binary>`

## Current Data

| Agent | Files | Chunks |
|-------|-------|--------|
| main | 1,246 | 20,806 |
| voice | 166 | 1,067 |

---

## References

- Dashboard: `/dashboard/templates/settings.html`
- Server: `/dashboard/server_v2.py` (knowledge API routes)
- Storage: `~/.openclaw/memory/*.sqlite`
