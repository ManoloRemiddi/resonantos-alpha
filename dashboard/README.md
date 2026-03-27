# ResonantOS Dashboard

Flask application serving the ResonantOS web interface.

## Architecture

**Entry point:** `server_v2.py` (Flask app with blueprint registration)

**Modular structure:**
- `routes/` — 26 Flask blueprints (agents, bounties, chatbots, docs, knowledge, logician, memory, protocols, projects, settings, shield, system, wallet, etc.)
- `templates/` — Jinja2 HTML templates
- `static/` — CSS, JS, images
- `data/` — Runtime data (logs, session state)

**Path resolution:** `routes/config.py` centralizes all paths:
- `REPO_DIR` — Repository root
- `DASHBOARD_DIR` — Dashboard directory
- `OPENCLAW_HOME` — OpenClaw config/data directory
- `SSOT_ROOT` — SSoT documentation root

All route modules import from `routes.config` for consistent path handling.

## Running

```bash
cd ~/resonantos-alpha/dashboard
python3 server_v2.py
```

**Default port:** 19100

**Requirements:**
- Python 3.9+
- Flask 3.x
- waitress (production server)
- See `package.json` for full dependencies

## Development

The dashboard is organized into modular Flask blueprints:

| Blueprint | Routes | Purpose |
|-----------|--------|---------|
| `agents` | /agents | Agent management |
| `bounties` | /bounties | DAO bounty system |
| `chatbots` | /chatbots | Chatbot configuration |
| `docs` | /docs | Documentation viewer |
| `gateway` | /gateway | Gateway control |
| `knowledge` | /knowledge | Knowledge base |
| `logician` | /logician | Logician rule viewer |
| `memory_bridge` | /memory | Memory system interface |
| `projects` | /projects | Project management |
| `protocols` | /protocols | Protocol registry |
| `settings` | /settings | System configuration |
| `shield` | /shield | Security layer monitoring |
| `wallet` | /wallet | Crypto wallet interface |

Each blueprint is self-contained with its own route handlers.

## Configuration

**Config files:**
- `config.json` — Dashboard-specific settings (port, paths, feature flags)
- `config.example.json` — Template for new installations

**OpenClaw integration:**
- Dashboard reads from `~/.openclaw/openclaw.json` for gateway state
- SSoT documentation loaded from `ssot/` directory
- Memory logs from `memory/` directory

## Legacy Files

Old monolithic server files archived in `.archive/`:
- `.archive/legacy-servers/` — Old server.py (172KB monolith) and variant files
- `.archive/tests/` — Test scaffolding and temp files
- `.archive/docs/` — Planning/spec documentation from development

These are preserved for reference but not used in production.

## Testing

Run the dashboard in development mode:
```bash
FLASK_ENV=development python3 server_v2.py
```

Navigate to `http://localhost:19100` to verify all pages load correctly.

## Deployment

For production, the dashboard runs as a LaunchAgent managed by OpenClaw:
- Service: `com.openclaw.dashboard`
- Auto-restart on crash
- Logs to `data/logs/dashboard.log`

See `dashboard-watchdog.sh` for the production startup script.
