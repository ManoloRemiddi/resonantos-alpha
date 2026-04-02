[AI-OPTIMIZED] ~700 tokens | src: openclaw/docs/concepts/agent-workspace.md
Updated: 2026-02-14

# Agent Workspace

**Home directory.** Only cwd for file tools & workspace context. Separate from `~/.openclaw/` (config/creds/sessions).

**Important:** Default cwd, not hard sandbox. Relative paths resolve vs workspace; absolute paths access elsewhere unless sandboxing enabled. Use [`agents.defaults.sandbox`](/gateway/sandboxing) for isolation.

## Default Location

- Default: `~/.openclaw/workspace`
- If `OPENCLAW_PROFILE` set (not `"default"`): `~/.openclaw/workspace-<profile>`
- Override in `~/.openclaw/openclaw.json`:
```json5
{ agent: { workspace: "~/.openclaw/workspace" } }
```

`openclaw onboard|configure|setup` creates workspace & seeds bootstrap files.

Disable bootstrap creation:
```json5
{ agent: { skipBootstrap: true } }
```

## Extra Workspace Folders

Older installs may have `~/openclaw`. Keep single active workspace to avoid auth/state drift. Recommend: `trash ~/openclaw` if unused. If multiple intentional, set `agents.defaults.workspace` to active.

`openclaw doctor` warns of extras.

## Workspace File Map

| File | Purpose |
|------|---------|
| `AGENTS.md` | Operating instructions, memory rules, behavior guidelines. Loaded every session. |
| `SOUL.md` | Persona, tone, boundaries. Loaded every session. |
| `USER.md` | User identity & address. Loaded every session. |
| `IDENTITY.md` | Agent name, vibe, emoji. Created/updated during bootstrap. |
| `TOOLS.md` | Local tool notes, conventions. No tool availability control. |
| `HEARTBEAT.md` | *(optional)* Tiny heartbeat checklist. Keep short. |
| `BOOT.md` | *(optional)* Startup checklist (gateway restart, internal hooks). Keep short. |
| `BOOTSTRAP.md` | *(once-only)* First-run ritual. Delete after complete. |
| `memory/YYYY-MM-DD.md` | Daily log. Read today + yesterday on session start. |
| `MEMORY.md` | *(optional)* Curated long-term memory. Only load in main session (not shared). |
| `skills/` | *(optional)* Workspace-specific skills. Override managed/bundled by name. |
| `canvas/` | *(optional)* Canvas UI files (e.g., `canvas/index.html`). |

Missing bootstrap files: OpenClaw injects marker, continues. Large files truncated (default max: `agents.defaults.bootstrapMaxChars = 20000`). `openclaw setup` recreates missing defaults without overwriting.

## NOT in Workspace

These live in `~/.openclaw/`, exclude from repo:
- `openclaw.json` (config)
- `credentials/` (OAuth, API keys)
- `agents/<agentId>/sessions/` (transcripts, metadata)
- `skills/` (managed skills)

Migrate separately; keep out of version control.

## Git Backup (Recommended, Private)

Treat workspace as private memory. **Private repo only.**

### 1) Initialize
```bash
cd ~/.openclaw/workspace
git init
git add AGENTS.md SOUL.md TOOLS.md IDENTITY.md USER.md HEARTBEAT.md memory/
git commit -m "Add agent workspace"
```

### 2) Add Private Remote

**Option A (GitHub UI):**
1. Create private repo (no README)
2. Copy HTTPS URL
```bash
git branch -M main
git remote add origin <https-url>
git push -u origin main
```

**Option B (GitHub CLI):**
```bash
gh auth login
gh repo create openclaw-workspace --private --source . --remote origin --push
```

**Option C (GitLab UI):** Same as GitHub UI.

### 3) Ongoing
```bash
git status
git add .
git commit -m "Update memory"
git push
```

## Do Not Commit Secrets

Avoid in private repo:
- API keys, OAuth tokens, passwords, credentials
- Anything under `~/.openclaw/`
- Raw chat dumps, sensitive attachments

Use placeholders; store real secrets in password manager, env vars, `~/.openclaw/`.

`.gitignore` starter:
```gitignore
.DS_Store
.env
**/*.key
**/*.pem
**/secrets*
```

## Move Workspace to New Machine

1. Clone repo to desired path (default: `~/.openclaw/workspace`)
2. Set `agents.defaults.workspace` in `~/.openclaw/openclaw.json`
3. Run `openclaw setup --workspace <path>` to seed missing files
4. If need sessions: copy `~/.openclaw/agents/<agentId>/sessions/` separately

## Advanced

- Multi-agent routing: different workspaces per agent. See [Channel routing](/concepts/channel-routing).
- Sandboxing enabled: non-main sessions use per-session sandbox under `agents.defaults.sandbox.workspaceRoot`.
