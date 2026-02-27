# ============================================================
# COHERENCE GATE RULES — Deterministic Task Enforcement
# ResonantOS Logician
# Purpose: Force agent to track tasks, enforce scope, detect drift
# ============================================================

# ============================================================
# TASK REQUIREMENT — "No task, no significant action"
# ============================================================

# Tools that REQUIRE an active CG task before use
significant_tool(/write).
significant_tool(/edit).
significant_tool(/exec).
significant_tool(/sessions_spawn).
significant_tool(/message_send).
significant_tool(/gateway).

# Tools exempt from task requirement (read-only / low-risk)
exempt_tool(/read).
exempt_tool(/web_search).
exempt_tool(/web_fetch).
exempt_tool(/memory_search).
exempt_tool(/memory_get).
exempt_tool(/session_status).
exempt_tool(/image).
exempt_tool(/tts).
exempt_tool(/browser_snapshot).

# Rule: block significant tool if no active task registered
cg_block_no_task(Tool) :-
  significant_tool(Tool),
  !exempt_tool(Tool),
  !cg_has_active_task.

# ============================================================
# SCOPE ENFORCEMENT — Task declares allowed paths
# ============================================================

# Rule: tool call touches a path outside declared scope → violation
cg_scope_violation(Tool, Path) :-
  significant_tool(Tool),
  cg_has_active_task,
  !cg_path_in_scope(Path).

# ============================================================
# DRIFT THRESHOLD — Hard block at high drift
# ============================================================

# Drift levels (scored by Coherence Gate extension)
cg_drift_warn :- cg_drift_score(Score), Score = 1.
cg_drift_block :- cg_drift_score(Score), Score >= 2.

# Rule: block tool calls when drift is too high
cg_block_drift(Tool) :-
  significant_tool(Tool),
  cg_drift_block.

# ============================================================
# STALE TASK ENFORCEMENT
# ============================================================

# Tasks older than 30 min (1800s) without update require action
cg_task_stale :- cg_task_age_seconds(Age), Age > 1800.

# ============================================================
# DELEGATION VERIFICATION
# ============================================================

# If task requires delegation but no spawn was made, flag it
cg_missing_delegation :- 
  cg_task_requires_delegation,
  !cg_has_spawned_agent.

# If delegation completed but result wasn't verified, flag it
cg_unverified_delegation :-
  cg_has_spawned_agent,
  cg_agent_completed,
  !cg_agent_result_reviewed.

# ============================================================
# COMPLETION ENFORCEMENT
# ============================================================

# Cannot claim completion without verification evidence
cg_premature_completion :-
  cg_claiming_done,
  !cg_has_verification_evidence.

# ============================================================
# COMBINED ENFORCEMENT — Single query point
# ============================================================

# Block reasons (queried by Shield Gate)
cg_block_reason(Tool, /no_task) :- cg_block_no_task(Tool).
cg_block_reason(Tool, /drift) :- cg_block_drift(Tool).
cg_block_reason(Tool, /stale_task) :- cg_task_stale, significant_tool(Tool).

# Warning reasons (logged but not blocked)
cg_warn_reason(/missing_delegation) :- cg_missing_delegation.
cg_warn_reason(/unverified_delegation) :- cg_unverified_delegation.
cg_warn_reason(/premature_completion) :- cg_premature_completion.
