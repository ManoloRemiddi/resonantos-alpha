# GitHub Project Agent Workflow For `resonantos-alpha`

Updated: 2026-03-20
Audience: Humans and agents working on the shared-branch backlog in `ResonantOS/resonantos-alpha`

## Purpose
This runbook defines the required day-to-day flow for claiming, executing, and handing off work through a GitHub Project board.

Supported tools:

- `git`
- `gh`

No MCP path, custom API client path, or alternate board integration is part of this workflow.

In this repo, this guide lives at:

- `agents/GITHUB/GITHUB_PROJECT_AGENT_WORKFLOW.md`

## Project Configuration

This workflow uses the **ResonantOS Alpha Readiness** project (project number 2).

Configuration file: `scripts/github-project/project.env`

To set up for the first time:
```bash
# Ensure gh is installed and logged in
gh auth login

# Refresh project scope (required for project board access)
gh auth refresh -s project

# Verify auth
gh auth status
```

## Preconditions

Before doing any task work, confirm:

- `git` access to the shared repository works
- `gh` is installed and is version `2.88.1` or newer
- `gh auth status` succeeds with `project` scope
- Project access is valid for the current `gh` session
- `scripts/github-project/project.env` exists and points at the correct owner, project number, and repo

This repo is public. Do not place tokens, secrets, or private notes in tracked workflow files.

If `gh` Project auth is missing or expired, run:
```bash
gh auth refresh -s project
```

## Standard Work Loop

1. Run `git pull` on the shared branch.
2. Use `scripts/github-project/list-todos` to list Project items with `Status = TODOS`.
3. Pick exactly one task from `TODOS`.
4. Claim it and move to `In Progress` using the workflow scripts.
5. Perform the work locally.
6. Run `git pull` again before `git push`.
7. Reconcile any merge conflicts locally.
8. Push to the shared branch.
9. Move the task to `In Review`.
10. Add a short completion note on the Issue.

## Hard Rules

- Only claim tasks from `TODOS`.
- Never start coding before moving the task to `In Progress`.
- Never claim more than one task unless the workflow owner explicitly allows it.
- Never move a task to `In Review` until the push has succeeded.
- If a task is already `In Progress`, leave it alone.
- Every agent must pull before starting work and again before pushing.
- If blocked, move the task to `Blocked` and explain why on the Issue.

## Required Command Surface

Prefer repo-owned wrappers when available:

- `scripts/github-project/list-todos`
- `scripts/github-project/claim-task`
- `scripts/github-project/move-to-review`
- `scripts/github-project/block-task`

Use `scripts/github-project/create-task` only when generating new backlog items. Use `scripts/github-project/project.env.example` to create the required local `scripts/github-project/project.env` config file.

The wrappers may use `gh api graphql` internally, but the operating rule does not change: use `git` for code sync and `gh`-backed wrappers for board operations.

## Task Notes And Handoff

When moving a task to `In Review`, add a short Issue comment that covers:

- what changed
- any known risks
- anything the reviewer or next agent should verify
- only information that is safe to expose in a public issue thread

The preferred path is:

- `scripts/github-project/move-to-review ISSUE_NUMBER --comment "summary"`

When moving a task to `Blocked`, add a short Issue comment that covers:

- what is blocking progress
- what has already been attempted
- what outside action is needed
- only information that is safe to expose publicly

The preferred path is:

- `scripts/github-project/block-task ISSUE_NUMBER --note "blocking reason"`

## Failure Handling

### Expired `gh` auth

- Do not claim, move, or close tasks until `gh auth status` is healthy again.
- Re-authenticate first, then retry the board operation.

### Claim races

- If another actor moved the item out of `TODOS`, do not continue.
- Pick a different `TODOS` item instead of overriding the existing claim.

### Merge conflicts on the shared branch

- Resolve conflicts locally after the second `git pull`.
- Do not move the task to `In Review` until the reconciled work is pushed successfully.
- If the conflict prevents safe completion, move the task to `Blocked` and explain the collision on the Issue.

### Blocked or partially finished work

- Keep the task in `In Progress` if it is still actively owned and expected to resume soon.
- Move the task to `Blocked` if progress depends on outside input, missing access, or unresolved upstream work.
- Do not mark partially completed work as `In Review`.

## Status Meanings

- `TODOS`: available to claim
- `In Progress`: actively owned by one agent or human
- `In Review`: pushed to the shared branch and ready for verification
- `Done`: verified complete
- `Blocked`: cannot continue without outside help or clarification
