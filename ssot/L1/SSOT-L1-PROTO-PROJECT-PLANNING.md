# PROTO-PROJECT-PLANNING — Multi-Phase Project Orchestration
Updated: 2026-03-24

**Type:** Orchestrator Protocol
**Created:** 2026-03-24
**Trigger:** Any project spanning >3 files, >1 session, or >2 delegations. NOT for single-fix tasks.
**Source:** GSD pattern (absorbed), existing TASK.md + Verification Protocol (extended).

---

## Purpose

Prevent ad-hoc drift on multi-phase projects. Enforce a repeatable cycle: scope → plan → execute → verify. Each project gets a living PLAN.md that tracks atomic tasks, dependencies, and proof of completion.

---

## When This Applies

| Scope | Protocol |
|---|---|
| Single bug fix (≤3 files, ≤100 lines) | TASK.md only |
| Feature or system change (>3 files OR multi-session) | **This protocol** |
| Design-level / architectural | This protocol + Autonomous Development Protocol (self-debate) |

---

## Artifacts

### PLAN.md

Lives at project root or `ssot/L3/PLAN-{PROJECT-NAME}.md` for cross-cutting work.

Structure:

```markdown
# PLAN: {Project Name}

**Status:** scoping | planning | executing | verifying | complete
**Created:** YYYY-MM-DD
**Last Updated:** YYYY-MM-DD
**Owner:** Augmentor (orchestrator)

## Objective
One paragraph. What does "done" look like?

## Phases

### Phase 1: {Name}
**Status:** pending | active | done
**Depends on:** (none | Phase N)

| # | Task | Files | Delegated To | Status | Verification |
|---|------|-------|-------------|--------|-------------|
| 1.1 | Description | path/to/file.py | Codex | ✅ done | curl returned 200 |
| 1.2 | Description | path/a.py, path/b.py | Codex | ⚠️ code-reviewed | needs manual test |
| 1.3 | Description | path/c.py | — | ❌ blocked | waiting on 1.1 |

### Phase 2: {Name}
...

## Decisions
- YYYY-MM-DD: {decision and rationale}

## Open Questions
- {question}
```

### Rules

1. **Every task gets a verification column.** No task closes without ✅, ⚠️, or ❓ (per Verification Protocol).
2. **Tasks are atomic.** One task = one TASK.md delegation. If a task needs >3 files or >100 lines, split it.
3. **Dependencies are explicit.** No task starts if its dependency is not ✅.
4. **Parallel when independent.** Tasks without dependencies on each other CAN be spawned simultaneously.
5. **Status updates are immediate.** After each delegation completes, update PLAN.md before doing anything else.
6. **Phase gates.** A phase is "done" only when ALL its tasks are ✅ or ⚠️ (no ❌ or blank).
7. **Decisions are logged.** Any architectural or scope decision goes in the Decisions section with date.

---

## Lifecycle

### 1. Scope (Before Writing PLAN.md)

- Read relevant SSoT docs and source code
- Identify all files that will be touched
- Identify dependencies between changes
- Determine phase boundaries (what can ship independently?)
- If design-level: run self-debate first (per Autonomous Development Protocol)

### 2. Plan (Write PLAN.md)

- Create PLAN.md with all phases and tasks
- Each task has: description, files, delegation target, verification method
- Review the plan: could tasks be parallelised? Are dependencies correct?
- Set status to "planning"

### 3. Execute (Per Phase)

For each phase, in dependency order:

1. Identify independent tasks → spawn in parallel where possible
2. For each task:
   a. Write TASK.md (per DELEGATION_PROTOCOL.md)
   b. Delegate to Codex CLI
   c. On completion: verify, update PLAN.md task status + verification column
3. When all tasks in phase are done: update phase status
4. Commit completed phase work

### 4. Verify (Phase Gate)

Before moving to next phase:
- All tasks ✅ or ⚠️?
- Any ⚠️ items need escalation?
- Run integration check if tasks touched shared code
- Update PLAN.md status

### 5. Close

When all phases complete:
- Set PLAN.md status to "complete"
- Move to `ssot/archive/` or delete (ephemeral projects)
- Update OPEN-ITEMS.md
- Drop breadcrumb in memory

---

## Parallel Execution Rules

- **Max 3 simultaneous Codex agents** (resource constraint on Mac Mini M4)
- Independent tasks in the same phase CAN run in parallel
- Each parallel agent gets its own TASK.md (use TASK-{N}.md for concurrent ones)
- Orchestrator monitors all spawned agents, updates PLAN.md as each completes
- If agent A's output changes the scope of agent B's task: kill B, re-plan, re-spawn

---

## Integration with Existing Protocols

| Existing Protocol | How It Connects |
|---|---|
| DELEGATION_PROTOCOL.md | Each task row generates one TASK.md. Two-stage review (spec → quality) after each. |
| Verification Protocol | Verification column uses same labels (✅ ⚠️ ❓) |
| TDD Flag | Tasks with `TDD: yes` require red-green-refactor. Orchestrator rejects implementation-before-test. |
| Shield Layer 1.5 (Delegation Gate) | Each TASK.md still passes through delegation gate |
| Git Worktrees (future) | Parallel agents get isolated worktrees. Requires swarm mode (GX10 + Mac Mini). |
| OPEN-ITEMS.md | Active projects tracked there, PLAN.md linked |
| Breadcrumbs | Major decisions + phase completions get breadcrumb entries |

---

## Git Worktrees for Parallel Isolation (Future — Swarm Mode)

**Status:** DOCUMENTED, NOT ACTIVE. Enable when: GX10 online + multiple agents working same repo.

**Problem:** When 3+ Codex agents edit the same repo simultaneously, they step on each other's files, create merge conflicts, and corrupt working directory state.

**Solution:** Git worktrees — each agent gets an isolated working directory on its own branch, all sharing the same `.git` history.

```bash
# Setup: create worktrees for parallel agents
git worktree add ../project-task-1 -b task/1.1-api-endpoint
git worktree add ../project-task-2 -b task/1.2-database-schema
git worktree add ../project-task-3 -b task/1.3-frontend-component

# Each Codex agent works in its own directory
# Agent 1: cd ../project-task-1 && codex exec ...
# Agent 2: cd ../project-task-2 && codex exec ...
# Agent 3: cd ../project-task-3 && codex exec ...

# After all complete: merge sequentially
git checkout main
git merge task/1.1-api-endpoint
git merge task/1.2-database-schema
git merge task/1.3-frontend-component

# Cleanup
git worktree remove ../project-task-1
git worktree remove ../project-task-2
git worktree remove ../project-task-3
```

**Rules (when activated):**
- One worktree per parallel task, named `../project-task-{N}`
- Branch naming: `task/{phase}.{task}-{short-description}`
- Orchestrator creates worktrees BEFORE spawning agents
- Orchestrator merges AFTER phase gate (not per-task)
- Merge conflicts = orchestrator resolves, never the agent
- Cleanup worktrees after phase completion

**Swarm scenario (GX10 + Mac Mini):**
- Mac Mini agents: worktrees on local disk
- GX10 agents: worktrees on GX10 local disk, push to shared remote
- Orchestrator coordinates merge order based on dependency graph

**Prerequisite:** PROTO-PROJECT-PLANNING must be active. Worktrees without a PLAN.md = chaos.

---

## Anti-Patterns

- **"Phase 1: Everything"** — If a phase has >7 tasks, split it.
- **Phantom dependencies** — Don't mark tasks as dependent unless they truly share state.
- **Stale PLAN.md** — If PLAN.md hasn't been updated in >4 hours during active work, something is wrong.
- **Orchestrator coding** — If you're writing code instead of writing TASK.md, stop.

---

## Example: GX10 Setup (Retroactive)

```
Phase 1: Research (complete)
  1.1 Hardware specs research → ✅ GX10-SETUP-ACTION-PLAN.md
  1.2 OpenClaw node docs → ✅ SSOT-L1-GX10-ARCHITECTURE.md

Phase 2: Day-One Setup (pending — Mar 28)
  2.1 Unbox + first boot → pending
  2.2 SSH + Tailscale + security → pending (depends: 2.1)
  2.3 CUDA verification → pending (depends: 2.1)
  2.4 TRT-LLM + Nemotron models → pending (depends: 2.3)
  2.5 OpenClaw node registration → pending (depends: 2.2)
  2.6 ComfyUI + Flux.1 → pending (depends: 2.3)
  2.7 Parakeet + audio pipeline → pending (depends: 2.4)
```
