<!-- TEMPLATE: Customize this file for your deployment -->
# ResonantOS Dashboard -- Architecture
Updated: 2026-03-27

| Field | Value |
|-------|-------|
| ID | SSOT-L1-DASHBOARD-V2 |
| Created | 2026-02-11 |
| Updated | 2026-03-27 |
| Author | Augmentor |
| Level | L1 (Architecture) |
| Status | Active |
| Stale After | 90 days |

---

## 1. Overview

Local web dashboard for managing ResonantOS. Runs on `localhost:19100`. Not a cloud service -- everything stays on the user's machine. 160+ API routes, 16 navigable pages, 5 Settings sub-tabs.

## 2. Stack

| Component | Technology |
|-----------|-----------|
| Backend | Python Flask (single `server_v2.py`) |
| Templates | Jinja2 with dark theme |
| Database | SQLite (`chatbots.db` for chatbot manager) |
| Frontend | Vanilla JS, Cytoscape.js (policy graph), no npm/node dependencies |
| CSS | Custom dark theme with CSS variables |
| Port | 19100 (default) |

## 3. Pages

### 3.1 Navigation Pages

| Page | Route | Purpose |
|------|-------|---------|
| Overview | `/` | System health, agent status, uptime, activity feed, LCM status |
| Shield | `/shield` | Security layers status, file guard summary, Memory Doorman, YARA scan results |
| Agents | `/agents` | Agent management, agent cards with model/channel info |
| Chatbots | `/chatbots` | Chatbot builder with visual customizer, widget embeds, knowledge base |
| SSoT | `/ssot` | SSoT document browser and staleness tracker |
| Projects | `/projects` | Monday.com-inspired project manager with Kanban boards, drag-and-drop tasks |
| Wallet | `/wallet` | Solana wallet interface, token balances, NFT minting, Alpha onboarding |
| Tribes | `/tribes` | Community tribe management, membership |
| Bounties | `/bounties` | Bounty board, task claiming, rewards |
| Protocol Store | `/protocol-store` | Protocol marketplace |
| Policy Graph | `/policy-graph` | Visual policy graph (Cytoscape.js + dagre), protocol flows, enforcement badges |
| Docs | `/docs` | Documentation browser with semantic search |
| TODO | `/todo` | Task management |
| License | `/license` | License agreement page |
| Settings | `/settings` | System configuration (5 sub-tabs, see below) |

### 3.2 Settings Sub-Tabs

| Tab | Purpose |
|-----|---------|
| General | System config, model info, gateway status |
| Rules | Logician rules viewer (Mangle/Datalog), working/available rules |
| Memory Bridge | MCP server configuration for external AI access |
| Skills | 55 skills × 10 agents matrix, status shapes (circle/diamond), two-axis filtering, setup popovers |
| Plugins | 7 custom + 43 stock plugins, status labels (Active/On-demand/Retired), allow-list chips, filter buttons |

## 4. Key Page Details

### 4.1 SSoT

Visual interface for managing Single Source of Truth (SSoT) documents.

**Features:**
- Document tree: Browse SSoTs by layer (L0-L4)
- Markdown editor: Split-pane with live preview, token counter
- Keywords per document: Configure trigger words for R-Awareness injection
- Dual token display: Shows both compressed (.ai.md) and raw (.md) token counts
- File locking: OS-level immutable flags (`chflags uchg` on macOS, `chattr +i` on Linux)
- Lock state shown as 🔒/🔓 per document and per layer

**Layer Hierarchy:**

| Layer | Name | Purpose | Lock Default |
|-------|------|---------|-------------|
| L0 | Foundation | Vision, mission, philosophy, manifesto, business plan | Locked |
| L1 | Architecture | System architecture, technical specs, integration patterns | Locked |
| L2 | Active Projects | Current project status, milestones, decisions | Unlocked |
| L3 | Drafts | Plans, proposals, research in progress | Unlocked |
| L4 | Notes | Working notes, session logs, incidents | Unlocked |

**Compression:** Each SSoT has `.md` (source, human-readable) + `.ai.md` (compressed, 55-80% smaller). R-Awareness injects `.ai.md` to save tokens. Edit `.md` first, regenerate `.ai.md` via `regenerate-ai-md.sh`. Shield Layer 6l enforces this workflow.

### 4.2 Shield Page

Dedicated security monitoring interface.

**Features:**
- Security layer status cards (14 blocking layers with descriptions)
- File Guard summary (1,800+ guarded files, lazy group loading for performance)
- Memory Doorman status (fswatch sanitizer for memory/ dirs)
- YARA scan results and history
- Performance: uses `os.stat()` for flag checks (140x faster than subprocess)

### 4.3 Policy Graph

Visual representation of the entire policy system using Cytoscape.js + dagre layout.

**Features:**
- Interactive graph: agents, rules, protocols as nodes with edges showing relationships
- Category-based color coding: teal (stateful agents), gray (tool agents), amber (task agents)
- 18 policy rules with enforcement badges (blocking/advisory)
- 6 protocol flows visualized
- Click-to-inspect nodes

### 4.4 Projects

Monday.com-inspired project management with Kanban boards.

**Features:**
- Project cards with icon, priority, progress bar, task summary, deadline
- 4-column Kanban board (To Do / In Progress / Blocked / Done)
- Drag-and-drop task management
- File-based JSON storage (`dashboard/data/projects/`)

### 4.5 Wallet

Solana wallet interface for Alpha onboarding and token management.

**Features:**
- Token balances ($RCT soulbound + $RES transferable + 5 REX sub-tokens)
- NFT minting (Identity NFTs)
- Alpha onboarding flow (6 steps: Wallet → Agreement → License → Manifesto → Identity NFT → Badge)
- Reputation and XP system, leaderboard

### 4.6 Settings Sub-Tab: Plugins

**Features:**
- 6 custom plugins (coherence-gate, heuristic-auditor, lossless-claw, r-awareness, shield-gate, usage-tracker)
- 43 stock OpenClaw plugins
- Status labels: Active (green ●), On-demand (blue ⟳), Retired (with explanation note)
- Allow-list chips, filter buttons (All/Custom/Stock)

### 4.7 Settings Sub-Tab: Skills

**Features:**
- 55 skills × 10 agents matrix UI
- Status shapes: circle (available), diamond (on-demand)
- Two-axis filtering (by skill, by agent)
- Setup popovers with agent configuration

## 5. API Structure

160+ routes organized by domain:

| Domain | Prefix | Example Endpoints |
|--------|--------|-------------------|
| Overview | `/api/overview` | status, agents, sessions, lcm |
| Shield | `/api/shield` | layers, guard/summary, guard/group, yara, doorman |
| Projects | `/api/projects` | CRUD, tasks, reorder |
| Wallet | `/api/wallet` | balances, mint-nft, onboarding-status, reputation, leaderboard |
| Tribes | `/api/tribes` | CRUD, join/leave |
| Bounties | `/api/bounties` | CRUD, claim/submit/review |
| Docs | `/api/docs` | tree, file, search, semantic |
| Logician | `/api/logician` | rules, facts, query |
| Settings | `/api/settings` | plugins, skills, config |
| Policy Graph | `/api/rules` | rules, protocols |

## 6. File Structure

```
dashboard/
├── server_v2.py           # Flask backend (160+ routes, single file)
├── templates/
│   ├── base.html          # Sidebar + layout shell (dark theme)
│   ├── index.html          # Overview
│   ├── shield.html         # Security monitoring
│   ├── policy-graph.html   # Cytoscape.js visual graph
│   ├── settings.html       # 5 sub-tabs (General, Rules, Memory Bridge, Skills, Plugins)
│   ├── wallet.html         # Solana wallet + onboarding
│   └── ... (21 templates total)
├── static/
│   ├── css/dashboard.css   # Dark theme styles
│   ├── css/dashboard-branded.css  # Brand overrides
│   └── js/dashboard.js    # Shared JS utilities
├── data/
│   └── projects/           # JSON project files
├── chatbots.db             # SQLite database
└── README.md
```

## 7. Design Principles

- **Local-first**: Everything runs on the user's machine, no cloud dependency
- **Single file backend**: One `server_v2.py`, easy to understand and modify
- **Dark theme**: Consistent with terminal/dev aesthetic
- **AI-friendly**: The AI can read this doc and help users extend/customize the dashboard
- **No build step**: Pure Python + vanilla JS (+ Cytoscape.js for graph), no npm/webpack/bundler

## 8. Dependencies

- Python 3.x
- Flask, flask-cors
- psutil
- markdown2 (optional, for server-side rendering)
- Cytoscape.js + dagre (CDN, for policy graph)

## 9. Related Documents

- Shield spec: `SSOT-L1-SHIELD.md`
- R-Awareness spec: `SSOT-L1-R-AWARENESS.md`
- Logician spec: `SSOT-L1-LOGICIAN.md`
- System overview: `SSOT-L1-SYSTEM-OVERVIEW.md`
