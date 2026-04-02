# NemoClaw Is Not the Fix. Here Is What Is Missing.

## NVIDIA just locked down OpenClaw. But security was never the real problem.

*March 2026*

---

NVIDIA announced NemoClaw at GTC last week and the OpenClaw community exhaled. Finally, someone serious tackled security. Landlock filesystem restrictions, seccomp syscall filtering, network namespacing, an operator approval dashboard. Default-deny everything. The agent cannot touch what it cannot reach.

The reaction was predictable: "NemoClaw fixes OpenClaw."

It does not. And the reason matters more than the gap.

---

## What NemoClaw actually solves

Credit where it is due. NemoClaw addresses real, dangerous problems:

- **Filesystem containment.** Landlock restricts the agent to `/sandbox` and `/tmp`. Your SSH keys, AWS credentials, browser cookies, Solana wallet? Unreachable.
- **Network isolation.** All traffic routes through a namespace proxy. Default-deny. The agent cannot phone home to an exfiltration endpoint unless you explicitly allowlist the domain.
- **Syscall filtering.** seccomp blocks privilege escalation. The agent cannot `ptrace`, cannot load kernel modules, cannot escape the sandbox.
- **Operator approval.** Blocked actions queue in a TUI for human review before execution.

This is serious infrastructure work. If you are running OpenClaw on a Linux server with untrusted agents or multiple users, NemoClaw is a meaningful upgrade. It makes the perimeter real.

But here is the question nobody in the NemoClaw excitement is asking:

**What happens inside the perimeter?**

---

## The scenario NemoClaw cannot catch

Your agent has legitimate access to your codebase. It is inside the sandbox, operating within its permissions. It finds a bug, writes a fix, commits it, and pushes. It reports: "Fixed."

You merge it. The deployment goes out.

Except the agent never tested the fix. It read the error message, wrote a plausible patch, and claimed victory. The CI passed because your test suite does not cover that path. The bug is still there, buried under a confident commit message.

NemoClaw saw nothing wrong. The agent had permission to edit files, permission to run git, permission to push. Every syscall was allowed. Every network call was within the allowlist. The sandbox worked perfectly.

The code is still broken.

This is not a security failure. It is a **trust failure**. And it is the failure mode that actually costs you time, money, and reliability every single day.

---

## Security is not trust

The industry conflates these two concepts and it is causing real damage.

**Security** answers: *Can the agent do this?*
Sandboxes, permissions, network rules. Binary. Allowed or denied.

**Trust** answers: *Should the agent do this right now, given what it knows and does not know?*
Context-aware. Behavioural. Requires understanding what the agent is supposed to be doing, not just what it is technically capable of.

NemoClaw is a security tool. It is excellent at security. But security and trust are different problems that require different architectures.

Here is what that looks like in practice:

| Scenario | NemoClaw (Security) | ResonantOS (Trust) |
|----------|--------------------|--------------------|
| Agent reads credential files | Blocked. Outside sandbox. | Blocked. Sensitive path gate, sub-agents restricted. |
| Agent calls an exfiltration domain | Blocked. Not in network allowlist. | Blocked. Domain on blocklist, fail-closed on unknown. |
| Agent claims "bug fixed" without testing | **Allowed.** All permissions valid. | **Blocked.** Verification gate requires test evidence before claiming completion. |
| Agent writes code directly instead of delegating to a coding tool | **Allowed.** Can write files. | **Blocked.** Coding gate enforces separation of concerns. Orchestrators orchestrate. |
| Agent reports system status from a single source | **Allowed.** Can read permitted files. | **Blocked.** State consistency gate requires cross-referencing multiple sources. |
| Agent edits a generated file instead of the source | **Allowed.** Both writable. | **Blocked.** Derivative protection enforces source-first workflow. |
| Agent tries to bypass its own governance rules via creative tool use | **Allowed.** Syscalls are valid. | **Blocked.** Behavioural integrity gate detects bypass patterns. |

The bottom five rows are where real damage happens. Not data breaches. Not credential theft. Slow, confident degradation of your system by an agent that has every permission it needs and no judgement about how to use them.

---

## What trust enforcement looks like

We built ResonantOS to solve this. It is not a platform. It is a set of OpenClaw plugins that sit on top of the kernel and enforce behavioural governance. It runs on bare OpenClaw. It runs inside NemoClaw. It does not compete with either; it fills the gap neither addresses.

Five capabilities:

### Shield: 16 blocking gates

A behavioural firewall. Not a sandbox. It intercepts tool calls and evaluates them against policy *before* execution.

**Real example:** An agent writes `sed -i 's/old/new/' src/server.js` to fix a bug directly. Shield's Coding Gate intercepts the call, recognises it as direct code modification, and blocks it. The agent must delegate to a dedicated coding tool. Why? An orchestrator buried in code cannot respond to its human. This is not about permissions. It is about discipline.

The 16 gates cover four categories:

| Category | What they enforce |
|----------|-------------------|
| **Security** | Destructive commands, network allowlists (31 allowed, 10 blocked, fail-closed), sensitive path protection (25 patterns), config change gates |
| **Quality** | Verification before claims, cross-reference before status reports, source-first editing, context coherence |
| **Architecture** | Coding delegation, repo contamination prevention, create-before-delete workflows, model cost hierarchy |
| **Governance** | Bypass detection, outbound communication gates, context loss recovery, research methodology validation |

### Logician: deterministic policy engine

A Datalog rule engine. Not AI reasoning. Actual logical inference over declared facts. 285 facts, 10 rule files. Deterministic: same input, same output, every time, regardless of which model is running.

It governs which agent can spawn which, what tools each agent can access (researcher gets web but no shell; creative gets local tools but no web), and trust hierarchies across the system.

### R-Awareness: contextual knowledge injection

Your agent wakes up every session knowing nothing. R-Awareness injects the right architecture documents at the right time based on what the conversation is about. 50-80% token savings versus loading everything upfront.

### Structured memory (4-layer stack)

| Layer | Purpose | Persistence |
|-------|---------|-------------|
| Curated knowledge | Long-term lessons and decisions | Permanent, human-reviewed |
| Session headers | Last 20 session summaries | Always-on, auto-maintained |
| Context compression | Lossless within-session management | Automatic |
| Semantic search | Vector search across all memory | On-demand |

Every work session produces a structured log: what happened, what went wrong, what to never repeat. The agent accumulates behavioural patterns. It gets measurably better at its job over time. No sandbox does this.

### Dashboard: see what your agent is doing

17-page web interface. Policy graph. Shield enforcement status. Agent management. If you cannot see what your agent is doing, you cannot trust it. Visibility is not optional.

---

## "But NemoClaw has an approval dashboard"

It does. For blocked syscalls and network requests. You review what was *denied*.

ResonantOS shows you what was *allowed and why*. That is a different category of visibility. The dangerous actions are not the ones that get blocked. They are the ones that pass through every gate and still degrade your system.

---

## So is NemoClaw useless?

No. NemoClaw is excellent at what it does. If you are deploying agents on Linux with multiple users or untrusted code, the kernel-level isolation is genuinely valuable. You cannot bypass Landlock from userspace. You cannot trick seccomp with prompt injection. That is real, hard security.

But NemoClaw is a lock on the door. ResonantOS is judgement about what happens inside the room.

You need both.

| Your situation | What to use | Why |
|----------------|-------------|-----|
| macOS (solo developer) | OpenClaw + ResonantOS | NemoClaw is Linux-only. ResonantOS gives you trust enforcement and knowledge management on any platform. |
| Linux server (multi-user) | OpenClaw + NemoClaw + ResonantOS | Defence in depth. NemoClaw locks the perimeter. ResonantOS governs behaviour inside it. |
| Just want infrastructure security | OpenClaw + NemoClaw | Safe agent, no behavioural governance. It will not leak your data. It may still push broken code. |

---

## Honest about where we are

We should be transparent.

ResonantOS does not match NemoClaw on infrastructure security. Our network allowlist operates at the application layer (plugin intercepts `web_fetch` calls), not the kernel layer. A sufficiently creative agent could theoretically find an unguarded tool path. NemoClaw's kernel restrictions are air-tight from userspace.

NemoClaw is early alpha. So are we. NVIDIA has more engineers. We have been running this system in production on our own work for months. Every gate exists because an agent actually did the thing it prevents. These are not theoretical scenarios. They are documented failures.

The question is not whether NemoClaw or ResonantOS is better. They solve different problems. The question is whether security alone is enough.

It is not. Trust is what is missing.

---

## The stack

```
+-------------------------------------------------------+
|                    ResonantOS                          |
|   Shield (16 gates) | Logician | R-Awareness | Dash   |
|   Trust enforcement, behavioural governance, memory    |
+-------------------------------------------------------+
|                    OpenClaw Kernel                      |
|     Gateway | Sessions | Tools | Cron | Memory | LCM   |
+-------------------------------------------------------+
|                    (optional)                          |
|                    NemoClaw Sandbox                     |
|           Landlock | seccomp | netns | proxy           |
+-------------------------------------------------------+
```

NemoClaw locks the door. OpenClaw builds the room. ResonantOS teaches the agent how to behave inside it.

They are not competitors. They are layers. Use what you need.

---

*ResonantOS is open source. Built by practitioners who got tired of agents that pass every security check and still break things.*

*[GitHub: resonantos-alpha](https://github.com/ResonantOS/resonantos-alpha)*
