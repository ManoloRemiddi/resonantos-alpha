% ============================================================================
% DELEGATION PROTOCOL RULES
% ResonantOS Logician - Orchestrator → Coder handoff enforcement
% ============================================================================
% Created: 2026-02-24 after two failed Codex delegations
% Root cause: orchestrator delegated without understanding the system

% ----------------------------------------------------------------------------
% PRE-DELEGATION REQUIREMENTS
% ----------------------------------------------------------------------------

% Orchestrator must complete these before spawning coder
pre_delegation_required(understand_source_code).
pre_delegation_required(trace_data_flow).
pre_delegation_required(identify_root_cause).
pre_delegation_required(specify_exact_fix).
pre_delegation_required(define_test_criteria).
pre_delegation_required(write_task_md).

% A delegation is ready when all pre-reqs are met
delegation_ready(Task) :-
    pre_delegation_required(Step),
    completed_pre_delegation(Task, Step).

% VIOLATION: Delegating without completing pre-work
violation(orchestrator, premature_delegation) :-
    delegated(orchestrator, Task, coder),
    pre_delegation_required(Step),
    \+ completed_pre_delegation(Task, Step).

% ----------------------------------------------------------------------------
% TASK.MD QUALITY REQUIREMENTS
% ----------------------------------------------------------------------------

% TASK.md must contain these sections
task_md_required_section(root_cause).
task_md_required_section(exact_fix).
task_md_required_section(files_to_modify).
task_md_required_section(test_command).
task_md_required_section(acceptance_criteria).

% VIOLATION: TASK.md with vague root cause
violation(orchestrator, vague_task_md) :-
    task_md_contains(root_cause, Text),
    contains_vague_language(Text).

% Vague language in task specifications
vague_task_language("likely root cause").
vague_task_language("investigate").
vague_task_language("probably").
vague_task_language("might be").
vague_task_language("should be").
vague_task_language("check if").
vague_task_language("look into").

contains_vague_language(Text) :-
    vague_task_language(Phrase),
    substring(Phrase, Text).

% ----------------------------------------------------------------------------
% SCOPE LIMITS
% ----------------------------------------------------------------------------

% Maximum files per delegation
max_files_per_task(3).

% Maximum new/modified lines per delegation
max_lines_per_task(100).

% VIOLATION: Over-scoped delegation
violation(orchestrator, over_scoped_task) :-
    task_files_count(Task, N),
    max_files_per_task(Max),
    N > Max.

% If task exceeds scope → must break into subtasks
should_break_task(Task) :-
    task_files_count(Task, N),
    N > 3.

should_break_task(Task) :-
    estimated_lines_changed(Task, N),
    N > 100.

% ----------------------------------------------------------------------------
% POST-DELEGATION VERIFICATION
% ----------------------------------------------------------------------------

% Orchestrator must verify coder's output independently
post_delegation_required(run_test_command).
post_delegation_required(inspect_changed_files).
post_delegation_required(verify_no_scope_creep).

% VIOLATION: Forwarding "done" without verification
violation(orchestrator, unverified_forwarding) :-
    coder_reported_done(Task),
    reported_done_to_human(orchestrator, Task),
    \+ verified_independently(orchestrator, Task).

% VIOLATION: "Fixed" without running tests
violation(orchestrator, false_fixed_claim) :-
    claimed_fixed(orchestrator, Task),
    \+ test_output_observed(orchestrator, Task).

% ----------------------------------------------------------------------------
% ANTI-PATTERNS (Explicit)
% ----------------------------------------------------------------------------

% "Investigate and fix" is never acceptable
violation(orchestrator, investigate_and_fix) :-
    task_md_contains(fix, "investigate").

% Multiple possible causes = not ready
violation(orchestrator, undiagnosed_delegation) :-
    task_md_root_cause_count(Task, N),
    N > 1.

% Delegating architectural decisions to coder
violation(orchestrator, delegated_architecture) :-
    task_contains_architectural_decision(Task),
    delegated(orchestrator, Task, coder).

% --- Diagnosis Gate (2026-03-01) ---
% Diagnostic claims on issues require deterministic evidence.
% Failure mode: Issue #6 — "on-chain program issue" asserted without
% testing the program. Program was fine. Bug was 1-line commitment fix.

violation(orchestrator, unverified_diagnosis) :-
    action(close_issue),
    comment_has_diagnostic_claim(Comment),
    \+ comment_has_evidence(Comment).

violation(orchestrator, unverified_diagnosis) :-
    action(comment_issue),
    comment_has_diagnostic_claim(Comment),
    \+ comment_has_evidence(Comment),
    \+ comment_has_uncertainty(Comment).

% Shield enforcement: shield/diagnosis_gate.py check "<comment>"
% Exit 0 = pass, Exit 1 = blocked
