# Getting Started with ResonantOS

> You don't need to learn to code. You need to learn to manage the thing that codes for you.

ResonantOS is an experience layer built on [OpenClaw](https://github.com/openclaw/openclaw). It turns your AI assistant from a chatbot into a managed, persistent, trustworthy collaborator.

This guide covers the five skills that separate people who ship with AI agents from people who fight with them. ResonantOS handles most of this structurally — but understanding *why* matters.

---

## Skill 1: Save Points

**The problem:** Your agent breaks something. You want to go back to the version that worked. You can't find it.

**The principle:** Every time your project is in a working state, save a snapshot. That snapshot is permanent. No matter what your agent does next, one command and you're back.

**How ResonantOS handles it:**
- **Git** is your save point system. Every verified change gets committed immediately — not "later," not "when I remember." Now.
- **Shield** (ResonantOS's security layer) runs a pre-push scan on every commit. Nothing leaves your machine without passing checks.
- **The habit:** After your agent completes a task and you've confirmed it works, commit. The command is `git add . && git commit -m "description of what works"`. That's your save point.

**What you need to do:**
1. Install git (your setup agent will check this for you)
2. After every working change, commit
3. If something breaks: `git stash` (undo uncommitted changes) or `git checkout <commit>` (go back to a save point)

Your agent can help you with git commands. Just ask.

---

## Skill 2: Context Is Finite

**The problem:** Your agent is brilliant for the first 30 minutes. Then it starts ignoring instructions, rewriting things it already wrote, introducing bugs into features that were working. It feels like it forgot everything.

**The principle:** It did forget. Agents have a fixed amount of memory (context window). When it fills up, older information gets compressed or dropped. Your instructions from the beginning of the conversation? Gone.

**How ResonantOS handles it:**
- **MEMORY.md** — Your agent's long-term memory. Curated knowledge that persists across every session. Think of it as the agent's notebook.
- **Memory Logs** — Structured records of what happened, what went wrong, and what was learned. Written automatically throughout the day.
- **LCM (Lossless Context Management)** — A context engine that compresses old conversation without losing information. When the agent needs something from 3 hours ago, it can retrieve it.
- **R-Awareness** — Automatically injects relevant system documentation into the agent's context based on what you're talking about. The agent gets the right reference material without you having to paste it.

**What you need to do:**
1. For long tasks, break them into sessions. Don't try to do everything in one conversation.
2. If your agent seems confused, start a fresh session. Your memory files mean it won't start from zero.
3. Keep your MEMORY.md clean — it competes for the same context space as your conversation.

---

## Skill 3: Standing Orders

**The problem:** You've told your agent to use dark mode five times. It keeps defaulting to light mode. Every session starts from zero.

**The principle:** Agents need persistent instructions that survive across conversations. Not instructions you repeat — instructions that are *always there*.

**How ResonantOS handles it:**
- **SOUL.md** — Who your agent is. Its principles, style, behavior rules, and boundaries. Read at the start of every session, automatically.
- **USER.md** — Who you are. Your preferences, communication style, timezone, background. So the agent doesn't have to re-learn you.
- **AGENTS.md** — How the workspace operates. Conventions, safety rules, file organization.

These three files are your "employee handbook." The agent reads them before every conversation.

**How to build them (the right way):**
1. Start simple. A few lines about your project and preferences.
2. Every time your agent does something wrong, add a line to prevent it.
3. Over a few weeks, these files become a precise reflection of what your project needs.
4. Keep them under ~200 lines each. Every line should earn its place.

The setup agent will help you create initial versions during onboarding. You refine them over time.

---

## Skill 4: Small Bets

**The problem:** You asked your agent to redesign the entire order system. It touched every file. Half the features broke. You have no idea which change caused which problem.

**The principle:** The bigger the change, the harder it is to figure out what went wrong. Give your agent focused, well-defined tasks. Verify between steps. Save between steps.

**How ResonantOS handles it:**
- **Shield's Direct Coding Gate** — Structurally prevents large, sweeping code changes. Forces decomposition into smaller pieces.
- **Delegation Protocol** — Every task delegated to a coding agent is scoped: specific files, specific changes, testable outcome.
- **The pattern:** Plan → Execute one piece → Verify → Save → Next piece.

**What you need to do:**
1. Before giving your agent a task, ask: *how big is this?*
2. **Small** (change a color, fix a typo) — just do it.
3. **Medium** (add a new feature) — ask the agent to plan it in steps first. Execute and verify one step at a time.
4. **Large** (redesign a system) — break it into multiple medium tasks. Each one gets its own plan, execution, and save point.

Think of it like building a house. You don't say "build me a house" and walk away. You say "pour the foundation," inspect it, then "frame the walls," inspect them. Same thing.

---

## Skill 5: Questions Your Agent Won't Ask

**The problem:** Your app works when you test it. Then real users submit empty forms, click buttons twice, paste emojis into number fields, and generally use it like humans.

**The principle:** There's a category of problems your agent will never raise on its own. You have to ask.

**The three questions:**

### "What happens when things fail?"

Tell your agent: *Every time the app communicates with a server, handle failure with a clear, friendly message. Never show a blank screen or a crash.*

Payments get declined. Servers go down. Connections drop. If your app doesn't handle these gracefully, your users see a white page.

### "Is customer data safe?"

Tell your agent: *Each user should only see their own data. Never log customer emails or payment information. Handle payments through a service like Stripe — don't store card details yourself.*

If you're handling real user data, this isn't optional. Add it to your rules file (SOUL.md or AGENTS.md).

### "How big will this get?"

Tell your agent your growth expectations upfront. An app for 10 users and an app for 10,000 users are built differently. Without this context, your agent will guess — and it'll guess wrong in both directions.

**How ResonantOS handles it:**
- **Shield** prevents secret keys and sensitive data from leaking into git commits or chat logs (pre-push scanning, file protection).
- **Standing orders** in SOUL.md are where you encode these expectations permanently.
- The rest is on you. These are product decisions, not tool decisions. But now you know to make them.

---

## The ResonantOS Difference

Most of what's described above, you'd have to do manually with a vanilla AI coding tool. Set up git yourself. Remember to commit. Write rules files from scratch. Hope you don't forget.

ResonantOS makes this structural:

| Skill | Manual Approach | ResonantOS |
|-------|----------------|------------|
| Save points | Remember to commit | Shield enforces verified commits |
| Context management | Start over and hope | 4-layer memory stack (MEMORY.md → Headers → LCM → RAG) |
| Standing orders | Write a rules file | SOUL.md + USER.md + AGENTS.md (generated during onboarding) |
| Small bets | Self-discipline | Shield gates enforce task decomposition |
| Defensive questions | Remember to ask | Persistent rules + secret scanning |

The wall between "vibe coding" and building real things with agents isn't made of code. It's made of management habits. ResonantOS turns those habits into infrastructure.

---

## Next Steps

1. **Run the setup agent** — It'll interview you and generate your initial SOUL.md, USER.md, and workspace files.
2. **Explore the dashboard** — `localhost:19100` — see your agents, skills, memory logs, and system status.
3. **Start small** — Pick one thing you want to build. Give your agent a focused task. Verify. Commit. Repeat.
4. **Refine your files** — Every mistake is a new line in SOUL.md. Every lesson is a memory log entry. The system gets better because you're teaching it.

Welcome to the Alpha. Build something.
