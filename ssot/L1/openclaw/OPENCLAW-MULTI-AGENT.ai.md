[AI-OPTIMIZED] ~1100 tokens | src: openclaw/docs/concepts/multi-agent.md
Updated: 2026-02-14

# Multi-Agent Routing

Goal: Multiple isolated agents (separate workspace + `agentDir` + sessions) + multiple channel accounts (e.g. 2 WhatsApps) in one Gateway. Inbound routed via bindings.

## What is "one agent"?

**Agent**: fully scoped brain with own:
- **Workspace** (files, AGENTS.md/SOUL.md/USER.md, local notes, persona)
- **State dir** (`agentDir`) - auth profiles, model registry, per-agent config
- **Session store** - chat history + routing state under `~/.openclaw/agents/<agentId>/sessions`

Auth profiles per-agent:
```
~/.openclaw/agents/<agentId>/agent/auth-profiles.json
```

⚠️ Never reuse `agentDir` (causes auth/session collisions). Copy `auth-profiles.json` to share creds.

Skills per-agent via `skills/` in workspace; shared skills at `~/.openclaw/skills`. See [Skills](/tools/skills).

Workspace = default cwd (not hard sandbox). Relative paths resolve in workspace; absolute paths can reach host unless sandboxing enabled. See [Sandboxing](/gateway/sandboxing).

## Paths

- Config: `~/.openclaw/openclaw.json` (or `OPENCLAW_CONFIG_PATH`)
- State dir: `~/.openclaw` (or `OPENCLAW_STATE_DIR`)
- Workspace: `~/.openclaw/workspace` (or `~/.openclaw/workspace-<agentId>`)
- Agent dir: `~/.openclaw/agents/<agentId>/agent`
- Sessions: `~/.openclaw/agents/<agentId>/sessions`

### Single-agent (default)

- `agentId` = `main`
- Sessions: `agent:main:<mainKey>`
- Workspace: `~/.openclaw/workspace` (or `~/.openclaw/workspace-<profile>` with `OPENCLAW_PROFILE`)
- State: `~/.openclaw/agents/main/agent`

## Add Agent

```bash
openclaw agents add work
```

Verify:
```bash
openclaw agents list --bindings
```

## Multiple Agents = Multiple Personas

Each `agentId` is fully isolated:
- Different phone numbers/accounts (per channel `accountId`)
- Different personalities (AGENTS.md, SOUL.md)
- Separate auth + sessions (no cross-talk unless explicit)

Enables **multiple people** sharing one Gateway with isolated AI brains + data.

## One WhatsApp, Multiple DMs (Split)

Route different WhatsApp DMs to different agents on **same account**. Match sender E.164 (e.g. `+15551234567`) with `peer.kind: "dm"`. Replies from same WhatsApp number (no per-agent sender).

⚠️ Direct chats collapse to agent's **main session key**; true isolation needs **one agent per person**.

Example:
```json5
{
  agents: {
    list: [
      { id: "alex", workspace: "~/.openclaw/workspace-alex" },
      { id: "mia", workspace: "~/.openclaw/workspace-mia" },
    ],
  },
  bindings: [
    { agentId: "alex", match: { channel: "whatsapp", peer: { kind: "dm", id: "+15551230001" } } },
    { agentId: "mia", match: { channel: "whatsapp", peer: { kind: "dm", id: "+15551230002" } } },
  ],
  channels: {
    whatsapp: {
      dmPolicy: "allowlist",
      allowFrom: ["+15551230001", "+15551230002"],
    },
  },
}
```

DM access control = global per WhatsApp account (pairing/allowlist), not per agent. For shared groups, bind to one agent or use [Broadcast groups](/broadcast-groups).

## Routing Rules (Message → Agent)

**Deterministic; most-specific wins**:
1. `peer` match (exact DM/group/channel id)
2. `guildId` (Discord)
3. `teamId` (Slack)
4. `accountId` match for channel
5. channel-level match (`accountId: "*"`)
6. fallback: default agent (`agents.list[].default` or first entry, default: `main`)

## Multiple Accounts / Phone Numbers

Channels supporting multiple accounts (e.g. WhatsApp) use `accountId` to identify each login. Each `accountId` can route to different agent; one server = multiple phone numbers without session mixing.

## Concepts

- **agentId**: one "brain" (workspace, per-agent auth, per-agent session store)
- **accountId**: one channel account instance (e.g. WhatsApp `"personal"` vs `"biz"`)
- **binding**: routes inbound messages to `agentId` by `(channel, accountId, peer)` + optional guild/team ids
- **Direct chats**: collapse to `agent:<agentId>:<mainKey>` (per-agent "main"; `session.mainKey`)

## Example: Two WhatsApps → Two Agents

```js
{
  agents: {
    list: [
      {
        id: "home",
        default: true,
        name: "Home",
        workspace: "~/.openclaw/workspace-home",
        agentDir: "~/.openclaw/agents/home/agent",
      },
      {
        id: "work",
        name: "Work",
        workspace: "~/.openclaw/workspace-work",
        agentDir: "~/.openclaw/agents/work/agent",
      },
    ],
  },

  bindings: [
    { agentId: "home", match: { channel: "whatsapp", accountId: "personal" } },
    { agentId: "work", match: { channel: "whatsapp", accountId: "biz" } },
    {
      agentId: "work",
      match: {
        channel: "whatsapp",
        accountId: "personal",
        peer: { kind: "group", id: "1203630...@g.us" },
      },
    },
  ],

  tools: {
    agentToAgent: {
      enabled: false,
      allow: ["home", "work"],
    },
  },

  channels: {
    whatsapp: {
      accounts: {
        personal: {},
        biz: {},
      },
    },
  },
}
```

## Example: WhatsApp + Telegram (Split by Channel)

Fast Sonnet for WhatsApp; Opus for Telegram:

```json5
{
  agents: {
    list: [
      {
        id: "chat",
        name: "Everyday",
        workspace: "~/.openclaw/workspace-chat",
        model: "anthropic/claude-sonnet-4-5",
      },
      {
        id: "opus",
        name: "Deep Work",
        workspace: "~/.openclaw/workspace-opus",
        model: "anthropic/claude-opus-4-6",
      },
    ],
  },
  bindings: [
    { agentId: "chat", match: { channel: "whatsapp" } },
    { agentId: "opus", match: { channel: "telegram" } },
  ],
}
```

For multiple accounts: add `accountId` to binding (e.g. `{ channel: "whatsapp", accountId: "personal" }`). Route single DM/group to Opus via `match.peer` binding (peer matches always win).

## Example: One DM to Opus, Rest on Chat

```json5
{
  agents: {
    list: [
      {
        id: "chat",
        name: "Everyday",
        workspace: "~/.openclaw/workspace-chat",
        model: "anthropic/claude-sonnet-4-5",
      },
      {
        id: "opus",
        name: "Deep Work",
        workspace: "~/.openclaw/workspace-opus",
        model: "anthropic/claude-opus-4-6",
      },
    ],
  },
  bindings: [
    { agentId: "opus", match: { channel: "whatsapp", peer: { kind: "dm", id: "+15551234567" } } },
    { agentId: "chat", match: { channel: "whatsapp" } },
  ],
}
```

Peer bindings always win; keep above channel-wide rule.

## Family Agent on WhatsApp Group

Dedicated family agent + mention gating + tight tool policy:

```json5
{
  agents: {
    list: [
      {
        id: "family",
        name: "Family",
        workspace: "~/.openclaw/workspace-family",
        identity: { name: "Family Bot" },
        groupChat: {
          mentionPatterns: ["@family", "@familybot", "@Family Bot"],
        },
        sandbox: {
          mode: "all",
          scope: "agent",
        },
        tools: {
          allow: [
            "exec",
            "read",
            "sessions_list",
            "sessions_history",
            "sessions_send",
            "sessions_spawn",
            "session_status",
          ],
          deny: ["write", "edit", "apply_patch", "browser", "canvas", "nodes", "cron"],
        },
      },
    ],
  },
  bindings: [
    {
      agentId: "family",
      match: {
        channel: "whatsapp",
        peer: { kind: "group", id: "120363999999999999@g.us" },
      },
    },
  ],
}
```

⚠️ Tool allow/deny = tools, not skills. For skill binaries, ensure `exec` allowed + binary in sandbox.

## Per-Agent Sandbox + Tools (v2026.1.6+)

```js
{
  agents: {
    list: [
      {
        id: "personal",
        workspace: "~/.openclaw/workspace-personal",
        sandbox: { mode: "off" },
      },
      {
        id: "family",
        workspace: "~/.openclaw/workspace-family",
        sandbox: {
          mode: "all",
          scope: "agent",
          docker: {
            setupCommand: "apt-get update && apt-get install -y git curl",
          },
        },
        tools: {
          allow: ["read"],
          deny: ["exec", "write", "edit", "apply_patch"],
        },
      },
    ],
  },
}
```

`setupCommand` under `sandbox.docker`; runs once on container creation. Per-agent `sandbox.docker.*` ignored when scope = `"shared"`.

**Benefits**:
- Security isolation (restrict untrusted agents)
- Resource control (sandbox specific agents)
- Flexible policies (per-agent permissions)

⚠️ `tools.elevated` = global + sender-based; not per-agent configurable. For per-agent boundaries, use `agents.list[].tools.deny` for `exec`. Use `agents.list[].groupChat.mentionPatterns` for group targeting.

See [Multi-Agent Sandbox & Tools](/multi-agent-sandbox-tools) for detailed examples.
