# Combined Rules - Auto-generated

# ============================================================
# ResonantOS — Logician Production Rules
# Engine: Mangle (Google Datalog)
# Purpose: Provable policy enforcement for agent orchestration
# ============================================================

# ============================================================
# AGENT REGISTRY
# ============================================================

agent(/main).
agent(/acupuncturist).
agent(/blindspot).
agent(/dao).
agent(/doer).
agent(/website).
agent(/researcher).
agent(/voice).
agent(/setup).
agent(/creative).

# Agent trust levels (1=lowest, 5=highest)
trust_level(/main, 5).
trust_level(/researcher, 4).
trust_level(/voice, 4).
trust_level(/creative, 4).
trust_level(/dao, 3).
trust_level(/doer, 3).
trust_level(/website, 3).
trust_level(/acupuncturist, 2).
trust_level(/blindspot, 2).
trust_level(/setup, 2).

# ============================================================
# SPAWN RULES
# ============================================================

# Direct spawn permissions (who can spawn whom)
can_spawn(/main, /acupuncturist).
can_spawn(/main, /blindspot).
can_spawn(/main, /dao).
can_spawn(/main, /doer).
can_spawn(/main, /website).
can_spawn(/main, /researcher).
can_spawn(/main, /voice).
can_spawn(/main, /setup).
can_spawn(/main, /creative).

# Derived: spawn is allowed if can_spawn (no blocks currently configured)
spawn_allowed(From, To) :- can_spawn(From, To).

# ============================================================
# DELEGATION RULES
# ============================================================

# Task type definitions
task_type(/code).
task_type(/research).
task_type(/test).
task_type(/design).
task_type(/strategy).
task_type(/security).
task_type(/archive).

# Delegation requirements: agent X must delegate task_type Y
requires_delegation(/main, /code).
requires_delegation(/main, /research).
requires_delegation(/main, /design).
requires_delegation(/main, /test).
requires_delegation(/website, /code).
requires_delegation(/creative, /code).

# Delegation targets: for a given (agent, task_type), delegate to whom
should_delegate(/main, /code, /doer).
should_delegate(/main, /research, /researcher).
should_delegate(/main, /design, /website).
should_delegate(/main, /test, /setup).
should_delegate(/website, /code, /doer).
should_delegate(/creative, /code, /doer).

# Derived: must_delegate_to resolves the full chain
must_delegate_to(Agent, Task, Target) :-
  requires_delegation(Agent, Task),
  should_delegate(Agent, Task, Target).

# ============================================================
# TOOL PERMISSIONS
# ============================================================

# Tool registry
tool(/brave_api).
tool(/perplexity).
tool(/web_fetch).
tool(/exec).
tool(/browser).
tool(/git).
tool(/solana_cli).
tool(/nft_minter).
tool(/token_manager).
tool(/file_write).
tool(/file_delete).
tool(/message_send).
tool(/tts).

# Tool permissions per agent
can_use_tool(/main, /brave_api).
can_use_tool(/main, /perplexity).
can_use_tool(/main, /web_fetch).
can_use_tool(/main, /exec).
can_use_tool(/main, /browser).
can_use_tool(/main, /git).
can_use_tool(/main, /solana_cli).
can_use_tool(/main, /nft_minter).
can_use_tool(/main, /token_manager).
can_use_tool(/main, /file_write).
can_use_tool(/main, /file_delete).
can_use_tool(/main, /message_send).
can_use_tool(/main, /tts).
can_use_tool(/acupuncturist, /browser).
can_use_tool(/acupuncturist, /message_send).
can_use_tool(/blindspot, /brave_api).
can_use_tool(/blindspot, /web_fetch).
can_use_tool(/dao, /brave_api).
can_use_tool(/dao, /perplexity).
can_use_tool(/dao, /message_send).
can_use_tool(/doer, /exec).
can_use_tool(/doer, /git).
can_use_tool(/doer, /file_write).
can_use_tool(/doer, /browser).
can_use_tool(/website, /file_write).
can_use_tool(/website, /browser).
can_use_tool(/researcher, /brave_api).
can_use_tool(/researcher, /perplexity).
can_use_tool(/researcher, /web_fetch).
can_use_tool(/voice, /brave_api).
can_use_tool(/voice, /web_fetch).
can_use_tool(/voice, /file_write).
can_use_tool(/voice, /tts).
can_use_tool(/voice, /message_send).
can_use_tool(/setup, /exec).
can_use_tool(/setup, /browser).
can_use_tool(/creative, /file_write).
can_use_tool(/creative, /browser).

# Dangerous tools require elevated trust
dangerous_tool(/exec).
dangerous_tool(/file_delete).
dangerous_tool(/solana_cli).
dangerous_tool(/nft_minter).
dangerous_tool(/token_manager).

# Derived: can agent use a dangerous tool?
can_use_dangerous(Agent, Tool) :-
  can_use_tool(Agent, Tool),
  dangerous_tool(Tool),
  trust_level(Agent, Level),
  Level >= 3.

# ============================================================
# SENSITIVE DATA & FORBIDDEN OUTPUT
# ============================================================

# Sensitive data types
sensitive_type(/api_key).
sensitive_type(/token).
sensitive_type(/private_key).
sensitive_type(/seed_phrase).
sensitive_type(/password).
sensitive_type(/keypair).

# Forbidden for output (never emit these)
forbidden_output_type(/api_key).
forbidden_output_type(/private_key).
forbidden_output_type(/seed_phrase).
forbidden_output_type(/password).
forbidden_output_type(/keypair).

# Known patterns for sensitive data
sensitive_pattern(/api_key, "sk-").
sensitive_pattern(/api_key, "sk-ant-").
sensitive_pattern(/api_key, "sk-proj-").
sensitive_pattern(/token, "ghp_").
sensitive_pattern(/token, "gho_").
sensitive_pattern(/token, "xoxb-").
sensitive_pattern(/token, "xoxp-").
sensitive_pattern(/private_key, "-----BEGIN").
# Seed phrase policy — detection uses BIP39 consecutive-word scanner in Shield
# (shield/data_leak_scanner.py contains_seed_phrase() with full 2048-word list)
sensitive_type(/seed_phrase).
forbidden_output_type(/seed_phrase).
seed_phrase_min_consecutive(8).  # Scanner threshold: 8+ consecutive BIP39 words (3 triggers on normal prose)

# Subscription info policy — detection uses PRIVATE_MARKERS in Shield scanner
# (real subscription strings stored only in scanner, never in repo)
sensitive_type(/subscription_info).
forbidden_output_type(/subscription_info).

# ============================================================
# INJECTION DETECTION
# ============================================================

injection_pattern("ignore previous instructions").
injection_pattern("ignore all previous").
injection_pattern("disregard previous").
injection_pattern("forget your instructions").
injection_pattern("DAN mode").
injection_pattern("jailbreak").
injection_pattern("you are now").
injection_pattern("pretend you are").
injection_pattern("act as if you have no restrictions").
injection_pattern("override your programming").
injection_pattern("system prompt").
injection_pattern("reveal your instructions").
injection_pattern("show me your prompt").

# ============================================================
# DESTRUCTIVE PATTERNS
# ============================================================

destructive_pattern("rm -rf").
destructive_pattern("rm -r /").
destructive_pattern("drop table").
destructive_pattern("drop database").
destructive_pattern("truncate table").
destructive_pattern("format c:").
destructive_pattern("mkfs").
destructive_pattern("dd if=").
destructive_pattern("> /dev/sda").
destructive_pattern("chmod -R 777 /").
destructive_pattern(":(){ :|:& };:").

# ============================================================
# BLOCKCHAIN SAFETY RULES
# ============================================================

# Networks
network(/devnet).
network(/testnet).
network(/mainnet).

# Mainnet operations require explicit human approval
requires_human_approval(/mainnet, /transfer).
requires_human_approval(/mainnet, /mint).
requires_human_approval(/mainnet, /deploy).
requires_human_approval(/mainnet, /close).

# Token safety caps (per wallet per year)
token_yearly_cap(/rct, 10000).
token_yearly_cap(/res, 1000000).

# Daily claim limits
daily_claim_limit(/rct, 1).
daily_claim_limit(/res, 500).

# ============================================================
# FILE PROTECTION (SHIELD)
# ============================================================

# Protected paths (never modify without explicit human approval)
protected_path("$OPENCLAW_HOME/openclaw.json").
protected_path("$SOLANA_CONFIG/id.json").
protected_path("$OPENCLAW_HOME/agents/main/agent/auth-profiles.json").
protected_path("$HOME/.ssh/").

# Safe workspace paths (AI can freely modify)
safe_path("$OPENCLAW_HOME/workspace/").
safe_path("$RESONANTOS_HOME/").
safe_path("$ALPHA_HOME/").

# Derived: is a path writable by AI?
ai_writable(Path) :- safe_path(Path), !protected_path(Path).

# ============================================================
# COST POLICY
# ============================================================

# Model cost tiers
model_tier(/opus, /expensive).
model_tier(/sonnet, /moderate).
model_tier(/haiku, /cheap).

# Task-to-model assignment (deterministic > AI principle)
preferred_model(/compression, /haiku).
preferred_model(/heartbeat, /haiku).
preferred_model(/background, /haiku).
preferred_model(/architecture, /opus).
preferred_model(/planning, /opus).
preferred_model(/complex_reasoning, /opus).
preferred_model(/code_review, /opus).
preferred_model(/routine, /sonnet).

# Private SSoT — absolute block
protected_path("$RESONANTOS_HOME/ssot/private/").
protected_path("ssot/private/").


# === VERIFICATION GATE ===
# Code changes require test evidence before push.
# Enforced by Shield pre-push hook + this rule.
requires_verification(/code_change).
verification_method(/curl).
verification_method(/browser).
verification_method(/unit).
verification_method(/manual).
verification_method(/script).
# code-review is allowed but flagged as warning (not verified)
weak_verification(/code_review).
weak_verification(/untestable).
# Rule: push allowed only if all code changes have verification entries
push_requires_evidence(/resonantos_augmentor).

# ============================================================
# COHERENCE GATE — Deterministic Task Enforcement
# All predicates MUST have at least one argument (Mangle constraint)
# Dynamic facts (asserted at query time via program field):
#   cg_active_task(/yes)          — an active task exists
#   cg_drift_score(N)             — current drift score 0-3
#   cg_task_age(Seconds)          — seconds since task creation
# ============================================================

# Tools requiring an active CG task
significant_tool(/write).
significant_tool(/edit).
significant_tool(/exec).
significant_tool(/sessions_spawn).
significant_tool(/message_send).
significant_tool(/gateway).

# Tools exempt from CG enforcement
exempt_tool(/read).
exempt_tool(/web_search).
exempt_tool(/web_fetch).
exempt_tool(/memory_search).
exempt_tool(/memory_get).
exempt_tool(/session_status).
exempt_tool(/image).
exempt_tool(/tts).
exempt_tool(/browser).

# No-task block: significant tool + no active task

# Default dynamic state (overridden by Shield Gate via program field)
# These provide the closed-world base for negation
cg_active_task(/no).
cg_drift_score(0).

# No-task block: significant tool + task not active
cg_block_no_task(Tool) :- significant_tool(Tool), !exempt_tool(Tool), cg_active_task(/no).

# Drift block: significant tool + drift score >= 2
cg_drift_status(/warn) :- cg_drift_score(1).
cg_drift_status(/block) :- cg_drift_score(Score), Score >= 2.
cg_block_drift(Tool) :- significant_tool(Tool), cg_drift_status(/block).

# Block reasons (single query point for Shield Gate)
cg_block_reason(Tool, /no_task) :- cg_block_no_task(Tool).
cg_block_reason(Tool, /drift) :- cg_block_drift(Tool).
# ============================================================
# GATEWAY LIFECYCLE RULES
# ============================================================
gateway_action(/stop).
gateway_action(/restart).
gateway_action(/start).
requires_resume_plan(/stop).
requires_resume_plan(/restart).
blocked_during_maintenance(/start).
blocked_during_maintenance(/restart).

# ---- rules/agent_creation_rules.mg ----
# Agent Creation Rules
# ResonantOS Logician

acr_workspace_base(/users_augmentor_clawd_agents).

acr_required_agent_file(/agents_md).
acr_required_agent_file(/soul_md).
acr_required_agent_file(/auth_profiles_json).

acr_recommended_agent_file(/identity_md).
acr_recommended_agent_file(/user_md).
acr_recommended_agent_file(/tools_md).
acr_recommended_agent_file(/memory_md).

acr_creation_step(/create_workspace_dir).
acr_creation_step(/create_agents_md).
acr_creation_step(/create_soul_md).
acr_creation_step(/copy_auth_profiles).
acr_creation_step(/add_to_clawdbot_config).
acr_creation_step(/restart_gateway).
acr_creation_step(/test_agent_responds).

acr_critical_step(/copy_auth_profiles).

acr_auth_sync_trigger(/agent_auth_error_detected).
acr_auth_sync_trigger(/new_agent_created).
acr_auth_sync_trigger(/daily_maintenance).

acr_sync_command(/sync_agent_auth_script).
acr_heartbeat_check(/auth_sync).

acr_missing_auth(Agent) :- agent(Agent), !acr_has_auth(Agent).
acr_violation(Agent, /missing_auth) :- acr_missing_auth(Agent).
acr_violation(Agent, /skipped_auth_copy) :- acr_agent_created(Agent), !acr_auth_copied(Agent).

acr_alert_condition(Agent, /auth_missing) :- acr_missing_auth(Agent).

# ---- rules/agent_rules.mg ----
# Agent Rules
# ResonantOS Logician

agr_profile(/main, /coordinator).
agr_profile(/doer, /implementation).
agr_profile(/website, /design).
agr_profile(/researcher, /research).
agr_profile(/dao, /governance).
agr_profile(/voice, /communication).
agr_profile(/creative, /creative_work).
agr_profile(/setup, /operations).
agr_profile(/acupuncturist, /diagnostics).
agr_profile(/blindspot, /risk_review).

agr_human(/user1).
agr_is_admin(/user1).

agr_can_spawn(/main, /doer).
agr_can_spawn(/main, /website).
agr_can_spawn(/main, /researcher).
agr_can_spawn(/main, /dao).
agr_can_spawn(/main, /voice).
agr_can_spawn(/main, /creative).
agr_can_spawn(/main, /setup).
agr_can_spawn(/main, /acupuncturist).
agr_can_spawn(/main, /blindspot).

agr_blocked_spawn(/doer, /main).
agr_blocked_spawn(/website, /main).
agr_blocked_spawn(/researcher, /main).

agr_spawn_allowed(From, To) :- agr_can_spawn(From, To), !agr_blocked_spawn(From, To).

agr_can_read_files(/main).
agr_can_read_files(/doer).
agr_can_read_files(/website).
agr_can_read_files(/researcher).

agr_can_write_files(/main).
agr_can_write_files(/doer).
agr_can_write_files(/website).
agr_can_write_files(/creative).

agr_can_execute_code(/main).
agr_can_execute_code(/doer).
agr_can_execute_code(/setup).

agr_can_send_external(/main).
agr_can_send_external(/voice).

agr_task_owner(/code_implementation, /doer).
agr_task_owner(/bug_fix, /doer).
agr_task_owner(/ui_design, /website).
agr_task_owner(/research, /researcher).
agr_task_owner(/governance, /dao).
agr_task_owner(/strategy, /main).

agr_should_delegate(Task, Agent) :- agr_task_owner(Task, Agent).

agr_requires_verification(/financial_action).
agr_requires_verification(/public_post).
agr_requires_verification(/destructive_action).
agr_requires_verification(/high_spawn_action).

agr_session_isolated(/doer).
agr_session_isolated(/website).
agr_session_isolated(/researcher).
agr_session_isolated(/dao).

agr_can_access_session(/main, /all_sessions).

agr_violation(/main, /direct_implementation) :- agr_main_doing_task(/code_implementation).
agr_violation(/main, /direct_implementation) :- agr_main_doing_task(/ui_design).

# ---- rules/atomic_rebuild_rules.mg ----
# Atomic Rebuild Rules
# ResonantOS Logician

reb_operation(/diagram_artboard_rebuild).
reb_operation(/config_file_rewrite).
reb_operation(/template_replacement).
reb_operation(/database_migration).
reb_operation(/file_structure_reorganization).

reb_sequence_step(/create_before_delete, /create_new).
reb_sequence_step(/create_before_delete, /verify_new).
reb_sequence_step(/create_before_delete, /delete_old).

reb_content_has_value(Content) :- reb_is_user_facing(Content).
reb_content_has_value(Content) :- reb_is_shared_document(Content).
reb_content_has_value(Content) :- reb_is_production_config(Content).
reb_content_has_value(Content) :- reb_is_architecture_diagram(Content).

reb_exempt_content(Content) :- reb_is_temp_file(Content).
reb_exempt_content(Content) :- reb_is_cache(Content).
reb_exempt_content(Content) :- reb_is_log_file(Content).

reb_creation_verified(Operation) :- reb_created_replacement(Operation), reb_verified_replacement(Operation).

reb_violation(Agent, /delete_before_create) :-
  reb_initiated_rebuild(Agent, Operation),
  reb_deleted_original(Agent, Operation),
  !reb_creation_verified(Operation).

reb_violation(Agent, /delete_without_replacement) :-
  reb_deleted_content(Agent, Content),
  reb_content_has_value(Content),
  !reb_planned_replacement(Agent, Content).

reb_violation(Agent, /non_atomic_rebuild) :-
  reb_initiated_rebuild(Agent, Operation),
  reb_out_of_order(Operation).

reb_enforcement_stage(/atomic_rebuild, /advisory).
reb_enforcement_stage_override(/atomic_rebuild, /soft_block) :- reb_user_visible_change(/yes).

# ---- rules/audit_rules.mg ----
# Audit Rules
# ResonantOS Logician

aud_audit_required(/all_queries).

aud_decision_type(/allow).
aud_decision_type(/deny).
aud_decision_type(/warn).

aud_log_path(/logician_logs_audit_jsonl).
aud_retention_days(30).

aud_report_time(/0300).
aud_report_format(/markdown).
aud_report_destination(/telegram).

aud_report_section(/summary_stats).
aud_report_section(/denials_by_rule).
aud_report_section(/denials_by_agent).
aud_report_section(/potential_false_positives).
aud_report_section(/rule_hit_frequency).
aud_report_section(/recommendations).

aud_must_log(/all_queries, /deny).
aud_must_log(/all_queries, /allow).
aud_must_log(/all_queries, /warn).

aud_high_risk_action(/security_rules).
aud_high_risk_action(/crypto_rules).
aud_high_risk_action(/external_communication).
aud_high_risk_action(/file_write).
aud_high_risk_action(/code_execution).

aud_must_log_detailed(Query) :- aud_involves_high_risk(Query).

aud_potential_false_positive(Entry) :-
  aud_entry_decision(Entry, /deny),
  aud_entry_seems_legitimate(Entry).

aud_potential_false_negative(Entry) :-
  aud_entry_decision(Entry, /allow),
  aud_entry_seems_suspicious(Entry).

aud_flag_severity(Entry, /critical) :- aud_entry_rule(Entry, /crypto_rules).
aud_flag_severity(Entry, /critical) :- aud_potential_false_negative(Entry), aud_entry_has_sensitive_pattern(Entry).
aud_flag_severity(Entry, /high) :- aud_potential_false_negative(Entry), aud_entry_is_high_risk(Entry).
aud_flag_severity(Entry, /medium) :- aud_potential_false_positive(Entry).
aud_flag_severity(Entry, /low) :-
  !aud_flag_severity(Entry, /critical),
  !aud_flag_severity(Entry, /high),
  !aud_flag_severity(Entry, /medium).

aud_todo_destination(/critical, /immediate_alert).
aud_todo_destination(/high, /daily_todo_list).
aud_todo_destination(/medium, /weekly_review).
aud_todo_destination(/low, /monthly_review).

aud_immediate_alert(Entry) :- aud_entry_rule(Entry, /crypto_rules), aud_entry_decision(Entry, /deny).
aud_immediate_alert(Entry) :- aud_entry_rule(Entry, /security_rules), aud_entry_decision(Entry, /deny).

aud_violation(Agent, /unexplained_error) :-
  aud_error_surfaced(Agent, ErrorType),
  aud_requires_explanation(ErrorType),
  !aud_explained_error(Agent, ErrorType).

aud_requires_explanation(/tool_error).
aud_requires_explanation(/shield_block).
aud_requires_explanation(/delegation_block).

# ---- rules/behavioral_integrity_rules.mg ----
# Behavioral Integrity Rules
# ResonantOS Logician

bir_challenge_pattern(/this_is_wrong).
bir_challenge_pattern(/thats_incorrect).
bir_challenge_pattern(/you_made_a_mistake).
bir_challenge_pattern(/this_does_not_work).
bir_challenge_pattern(/are_you_sure).
bir_challenge_pattern(/check_again).
bir_challenge_pattern(/you_forgot).

bir_challenge_type(/factual_correction).
bir_challenge_type(/behavioral_critique).
bir_challenge_type(/state_assertion).
bir_challenge_type(/identity_claim).

bir_required_response_step(1, /acknowledge_challenge).
bir_required_response_step(2, /independent_verification).
bir_required_response_step(3, /report_with_evidence).

bir_violation(Agent, /reflexive_agreement) :-
  bir_received_challenge(Agent, Challenge),
  bir_responded_with_agreement(Agent, Challenge),
  !bir_performed_verification(Agent, Challenge).

bir_violation(Agent, /unsupported_disagreement) :-
  bir_received_challenge(Agent, Challenge),
  bir_responded_with_disagreement(Agent, Challenge),
  !bir_cited_evidence(Agent, Challenge).

bir_violation(Agent, /skipped_acknowledgment) :-
  bir_received_challenge(Agent, Challenge),
  !bir_acknowledged_challenge(Agent, Challenge),
  bir_responded_with_agreement(Agent, Challenge).

bir_violation(Agent, /skipped_acknowledgment) :-
  bir_received_challenge(Agent, Challenge),
  !bir_acknowledged_challenge(Agent, Challenge),
  bir_responded_with_disagreement(Agent, Challenge).

bir_violation(Agent, /sycophantic_reversal) :-
  bir_received_challenge(Agent, Challenge),
  bir_changed_position(Agent, Challenge),
  !bir_new_evidence_provided(Agent, Challenge).

bir_violation(Agent, /uncritical_frame_adoption) :-
  bir_received_challenge(Agent, Challenge),
  bir_adopted_frame(Agent, Challenge),
  !bir_verified_frame(Agent, Challenge).

bir_violation(Agent, /missed_ip_recognition) :-
  bir_referenced_named_concept(Agent, Concept),
  bir_registered_ip(Concept, /owner),
  !bir_recognized_as_ip(Agent, Concept).

bir_requires_ip_check(Concept) :- bir_is_framework(Concept).
bir_requires_ip_check(Concept) :- bir_is_book_title(Concept).
bir_requires_ip_check(Concept) :- bir_is_methodology(Concept).
bir_requires_ip_check(Concept) :- bir_is_branded_term(Concept).

bir_enforcement_stage(/behavioral_integrity, /advisory).
bir_enforcement_stage_override(/behavioral_integrity, /soft_block) :- bir_violation(/any_agent, /sycophantic_reversal).

# ---- rules/coder_rules.mg ----
# Coder Rules
# ResonantOS Logician

cod_must_test_before_complete(/coder).

cod_valid_test(/web_page, /load_page).
cod_valid_test(/web_page, /verify_renders).
cod_valid_test(/web_functionality, /open_browser).
cod_valid_test(/web_functionality, /interact_with_element).
cod_valid_test(/web_functionality, /verify_output).
cod_valid_test(/api_endpoint, /call_endpoint).
cod_valid_test(/api_endpoint, /verify_response).
cod_valid_test(/script, /execute_script).
cod_valid_test(/script, /verify_output).
cod_valid_test(/ui_component, /render_component).
cod_valid_test(/ui_component, /visual_verify).

cod_invalid_test(/read_code).
cod_invalid_test(/assume_works).
cod_invalid_test(/looks_correct).
cod_invalid_test(/should_work).
cod_invalid_test(/syntax_check_only).

cod_required_test_method(/html_file, /browser_load).
cod_required_test_method(/css_file, /browser_render).
cod_required_test_method(/web_page, /browser_snapshot).
cod_required_test_method(/button, /browser_click).
cod_required_test_method(/form, /browser_fill_submit).
cod_required_test_method(/api_endpoint, /http_request_verify).
cod_required_test_method(/python_script, /python_execute).
cod_required_test_method(/shell_script, /bash_execute).
cod_required_test_method(/server, /start_and_health_check).

cod_browser_test_required(Task) :- cod_task_involves(Task, /html).
cod_browser_test_required(Task) :- cod_task_involves(Task, /css).
cod_browser_test_required(Task) :- cod_task_involves(Task, /javascript).
cod_browser_test_required(Task) :- cod_task_involves(Task, /ui).
cod_browser_test_required(Task) :- cod_task_involves(Task, /frontend).
cod_browser_test_required(Task) :- cod_task_involves(Task, /dashboard).

cod_required_evidence(/web_page, /screenshot).
cod_required_evidence(/web_page, /snapshot_output).
cod_required_evidence(/api_endpoint, /response_body).
cod_required_evidence(/script, /execution_output).
cod_required_evidence(/ui_interaction, /before_after_state).

cod_not_done(/code_written).
cod_not_done(/code_looks_correct).
cod_not_done(/code_reviewed).
cod_not_done(/no_syntax_errors).
cod_not_done(/code_committed).

cod_valid_done_evidence(/terminal_output).
cod_valid_done_evidence(/browser_screenshot).
cod_valid_done_evidence(/browser_snapshot).
cod_valid_done_evidence(/api_response).
cod_valid_done_evidence(/file_created).
cod_valid_done_evidence(/process_running).

cod_invalid_done_evidence(/code_analysis).
cod_invalid_done_evidence(/logical_reasoning).
cod_invalid_done_evidence(/assumption).
cod_invalid_done_evidence(/pattern_matching).

cod_violation(/coder, /untested_code) :- cod_claimed_complete(/coder, Task), !cod_test_performed(/coder, Task).
cod_violation(/coder, /invalid_test_method) :- cod_test_performed_with_method(/coder, Task, Method), cod_invalid_test(Method).
cod_violation(/coder, /skipped_browser_test) :- cod_browser_test_required(Task), cod_completed(/coder, Task), !cod_used_browser_tool(/coder, Task).

cod_max_fix_attempts(3).
cod_max_direct_attempts(5).
cod_max_research_attempts(5).
cod_max_total_attempts(10).

cod_requires_research(/coder, Task) :- cod_attempt_count(/coder, Task, Count), Count > 5, !cod_research_performed(Task).
cod_must_escalate(/coder, Task) :- cod_attempt_count(/coder, Task, Count), Count >= 10, !cod_task_resolved(Task).

# ---- rules/coherence_gate_rules.mg ----
# Coherence Gate Rules
# ResonantOS Logician

cgr_significant_tool(/write).
cgr_significant_tool(/edit).
cgr_significant_tool(/exec).
cgr_significant_tool(/sessions_spawn).
cgr_significant_tool(/message_send).
cgr_significant_tool(/gateway).

cgr_exempt_tool(/read).
cgr_exempt_tool(/web_search).
cgr_exempt_tool(/web_fetch).
cgr_exempt_tool(/memory_search).
cgr_exempt_tool(/memory_get).
cgr_exempt_tool(/session_status).
cgr_exempt_tool(/image).
cgr_exempt_tool(/tts).
cgr_exempt_tool(/browser_snapshot).

cgr_active_task(/no).
cgr_drift_score(0).

cgr_block_no_task(Tool) :- cgr_significant_tool(Tool), !cgr_exempt_tool(Tool), cgr_active_task(/no).

cgr_scope_violation(Tool, Path) :-
  cgr_significant_tool(Tool),
  cgr_active_task(/yes),
  cgr_path_touched(Tool, Path),
  !cgr_path_in_scope(Path).

cgr_drift_status(/warn) :- cgr_drift_score(1).
cgr_drift_status(/block) :- cgr_drift_score(Score), Score >= 2.
cgr_block_drift(Tool) :- cgr_significant_tool(Tool), cgr_drift_status(/block).

cgr_task_stale(/yes) :- cgr_task_age_seconds(Age), Age > 1800.

cgr_missing_delegation(/yes) :- cgr_task_requires_delegation(/yes), !cgr_has_spawned_agent(/yes).
cgr_unverified_delegation(/yes) :- cgr_has_spawned_agent(/yes), cgr_agent_completed(/yes), !cgr_agent_result_reviewed(/yes).
cgr_premature_completion(/yes) :- cgr_claiming_done(/yes), !cgr_has_verification_evidence(/yes).

cgr_block_reason(Tool, /no_task) :- cgr_block_no_task(Tool).
cgr_block_reason(Tool, /drift) :- cgr_block_drift(Tool).
cgr_block_reason(Tool, /stale_task) :- cgr_task_stale(/yes), cgr_significant_tool(Tool).

cgr_warn_reason(/missing_delegation) :- cgr_missing_delegation(/yes).
cgr_warn_reason(/unverified_delegation) :- cgr_unverified_delegation(/yes).
cgr_warn_reason(/premature_completion) :- cgr_premature_completion(/yes).

# ---- rules/crypto_rules.mg ----
# Crypto Rules
# ResonantOS Logician

cry_valid_seed_length(12).
cry_valid_seed_length(15).
cry_valid_seed_length(18).
cry_valid_seed_length(21).
cry_valid_seed_length(24).

cry_is_recovery_phrase(Data) :- cry_seed_candidate(Data), cry_seed_length(Data, Len), cry_valid_seed_length(Len), cry_all_words_in_bip39(Data).
cry_is_partial_seed(Data) :- cry_seed_candidate(Data), cry_seed_length(Data, Len), cry_partial_seed_length(Len), cry_all_words_in_bip39(Data).

cry_partial_seed_length(6).
cry_partial_seed_length(7).
cry_partial_seed_length(8).
cry_partial_seed_length(9).
cry_partial_seed_length(10).
cry_partial_seed_length(11).

cry_is_private_key(Data) :- cry_private_key_format(Data, /evm_hex_66).
cry_is_private_key(Data) :- cry_private_key_format(Data, /btc_wif_51).
cry_is_private_key(Data) :- cry_private_key_format(Data, /btc_wif_52).
cry_is_private_key(Data) :- cry_private_key_format(Data, /solana_base58_88).

cry_is_wallet_address(Data) :- cry_wallet_address_format(Data, /evm_42).
cry_is_wallet_address(Data) :- cry_wallet_address_format(Data, /btc_legacy).
cry_is_wallet_address(Data) :- cry_wallet_address_format(Data, /btc_p2sh).
cry_is_wallet_address(Data) :- cry_wallet_address_format(Data, /btc_bech32).
cry_is_wallet_address(Data) :- cry_wallet_address_format(Data, /solana_base58).

cry_forbidden_action(/output, Data) :- cry_is_recovery_phrase(Data).
cry_forbidden_action(/store, Data) :- cry_is_recovery_phrase(Data).
cry_forbidden_action(/log, Data) :- cry_is_recovery_phrase(Data).
cry_forbidden_action(/transmit, Data) :- cry_is_recovery_phrase(Data).
cry_forbidden_action(/display, Data) :- cry_is_recovery_phrase(Data).

cry_forbidden_action(/output, Data) :- cry_is_partial_seed(Data).
cry_forbidden_action(/store, Data) :- cry_is_partial_seed(Data).

cry_forbidden_action(/output, Data) :- cry_is_private_key(Data).
cry_forbidden_action(/store, Data) :- cry_is_private_key(Data).
cry_forbidden_action(/log, Data) :- cry_is_private_key(Data).
cry_forbidden_action(/transmit, Data) :- cry_is_private_key(Data).

cry_warn_action(/share_address_group, Data) :- cry_is_wallet_address(Data), cry_group_context(/yes).

cry_is_signing_action(Action) :- cry_action_tag(Action, /sign).
cry_is_signing_action(Action) :- cry_action_tag(Action, /approve).
cry_is_signing_action(Action) :- cry_action_tag(Action, /confirm).

cry_requires_human_confirmation(Action) :- cry_is_signing_action(Action).
cry_forbidden_action(/auto_sign, /all).

cry_high_value_threshold_usd(100).
cry_is_high_value(Transaction) :- cry_transaction_value_usd(Transaction, Value), cry_high_value_threshold_usd(Threshold), Value > Threshold.
cry_requires_double_confirmation(Transaction) :- cry_is_high_value(Transaction).

cry_is_wallet_connect_request(Data) :- cry_connect_request_tag(Data, /wc).
cry_is_wallet_connect_request(Data) :- cry_connect_request_tag(Data, /walletconnect).
cry_is_wallet_connect_request(Data) :- cry_connect_request_tag(Data, /connect_wallet).

cry_requires_human_verification(Action) :- cry_is_wallet_connect_request(Action).
cry_forbidden_action(/auto_connect, Data) :- cry_is_wallet_connect_request(Data).

cry_phishing_pattern(/claim_keyword).
cry_phishing_pattern(/airdrop_keyword).
cry_phishing_pattern(/free_mint_keyword).
cry_phishing_pattern(/urgent_keyword).
cry_phishing_pattern(/expires_keyword).

cry_trusted_domain(/github_com).
cry_trusted_domain(/etherscan_io).
cry_trusted_domain(/solscan_io).

cry_block_url(Url) :- cry_url_has_phishing_pattern(Url), !cry_url_is_trusted(Url).
cry_warn_url(Url) :- cry_is_wallet_connect_request(Url), !cry_url_is_trusted(Url).

cry_absolute_prohibition(/store_seed_phrase).
cry_absolute_prohibition(/output_private_key).
cry_absolute_prohibition(/auto_sign_transaction).
cry_absolute_prohibition(/share_seed_phrase).
cry_absolute_prohibition(/log_private_key).
cry_absolute_prohibition(/transmit_recovery_phrase).

cry_cannot_override(Action) :- cry_absolute_prohibition(Action).

# ---- rules/decision_bias_rules.mg ----
# Decision Bias Rules
# ResonantOS Logician

db_filter_priority(1, /free_over_paid).
db_filter_priority(2, /safe_over_risky).
db_filter_priority(3, /deterministic_over_ai).
db_filter_priority(4, /oss_over_custom).
db_filter_priority(5, /simple_over_complex).
db_filter_priority(6, /local_over_remote).

db_option_eliminable(Option, Filter) :-
  db_filter_priority(_, Filter),
  db_violates_filter(Option, Filter),
  db_better_alternative_exists(Option, Filter).

db_single_survivor(Option) :-
  db_candidate_option(Option),
  !db_option_eliminable(Option, _),
  db_all_others_eliminable(Option).

db_must_act_not_ask(/yes) :- db_single_survivor(_).

db_unnecessary_options_presented(/yes) :-
  db_options_presented_state(/multiple),
  db_must_act_not_ask(/yes).

db_violates_filter(Option, /safe_over_risky) :- db_option_has_risk(Option).
db_violates_filter(Option, /free_over_paid) :- db_option_has_cost(Option), db_free_alternative_exists(/yes).
db_violates_filter(Option, /deterministic_over_ai) :- db_option_uses_ai(Option), db_deterministic_solution_exists(/yes).

db_contradicts_core_principles(Option) :- db_option_has_risk(Option), db_building_trustworthy_system(/yes).
db_contradicts_core_principles(Option) :- db_option_accepts_known_bug(Option), db_building_reliable_system(/yes).

db_building_trustworthy_system(/yes).
db_building_reliable_system(/yes).

db_not_real_option(Option) :- db_contradicts_core_principles(Option).

db_decision_bias_block(/unnecessary_options) :- db_unnecessary_options_presented(/yes).
db_decision_bias_warn(/explain_tradeoff) :- db_options_presented_state(/multiple), !db_must_act_not_ask(/yes).

# ---- rules/delegation_rules.mg ----
# Delegation Protocol Rules
# ResonantOS Logician

del_pre_delegation_required(/understand_source_code).
del_pre_delegation_required(/trace_data_flow).
del_pre_delegation_required(/identify_root_cause).
del_pre_delegation_required(/specify_exact_fix).
del_pre_delegation_required(/define_test_criteria).
del_pre_delegation_required(/write_task_md).

del_delegation_ready(Task) :-
  del_task_prework_complete(Task, /understand_source_code),
  del_task_prework_complete(Task, /trace_data_flow),
  del_task_prework_complete(Task, /identify_root_cause),
  del_task_prework_complete(Task, /specify_exact_fix),
  del_task_prework_complete(Task, /define_test_criteria),
  del_task_prework_complete(Task, /write_task_md).

del_violation(/orchestrator, /premature_delegation) :-
  del_delegated(/orchestrator, Task, /doer),
  !del_delegation_ready(Task).

del_task_md_required_section(/root_cause).
del_task_md_required_section(/exact_fix).
del_task_md_required_section(/files_to_modify).
del_task_md_required_section(/test_command).
del_task_md_required_section(/acceptance_criteria).

del_vague_task_language(/likely_root_cause).
del_vague_task_language(/investigate).
del_vague_task_language(/probably).
del_vague_task_language(/might_be).
del_vague_task_language(/should_be).
del_vague_task_language(/check_if).
del_vague_task_language(/look_into).

del_violation(/orchestrator, /vague_task_md) :- del_task_md_contains_vague_language(/yes).

del_max_files_per_task(3).
del_max_lines_per_task(100).

del_violation(/orchestrator, /over_scoped_task) :- del_task_scope_status(/over_files).
del_violation(/orchestrator, /over_scoped_task) :- del_task_scope_status(/over_lines).

del_should_break_task(Task) :- del_task_scope(Task, /over_files).
del_should_break_task(Task) :- del_task_scope(Task, /over_lines).

del_post_delegation_required(/run_test_command).
del_post_delegation_required(/inspect_changed_files).
del_post_delegation_required(/verify_no_scope_creep).

del_violation(/orchestrator, /unverified_forwarding) :-
  del_coder_reported_done(Task),
  del_reported_done_to_human(/orchestrator, Task),
  !del_verified_independently(/orchestrator, Task).

del_violation(/orchestrator, /false_fixed_claim) :-
  del_claimed_fixed(/orchestrator, Task),
  !del_test_output_observed(/orchestrator, Task).

del_violation(/orchestrator, /investigate_and_fix) :- del_task_uses_pattern(/investigate_and_fix).
del_violation(/orchestrator, /undiagnosed_delegation) :- del_root_cause_state(/multiple_candidates).
del_violation(/orchestrator, /delegated_architecture) :- del_task_contains_architecture_decision(/yes), del_delegated(/orchestrator, /current_task, /doer).

del_violation(/orchestrator, /unverified_diagnosis) :- del_action(/close_issue), del_comment_has_diagnostic_claim(/yes), !del_comment_has_evidence(/yes).
del_violation(/orchestrator, /unverified_diagnosis) :- del_action(/comment_issue), del_comment_has_diagnostic_claim(/yes), !del_comment_has_evidence(/yes), !del_comment_has_uncertainty(/yes).

del_violation(/orchestrator, /silent_delegation_failure) :- del_delegation_failed(/orchestrator, Error), !del_human_informed(/delegation_failed, Error).
del_violation(/orchestrator, /incomplete_failure_report) :- del_delegation_failed(/orchestrator, Error), del_human_informed(/delegation_failed, Error), !del_failure_report_includes(Error, /what_failed).
del_violation(/orchestrator, /incomplete_failure_report) :- del_delegation_failed(/orchestrator, Error), del_human_informed(/delegation_failed, Error), !del_failure_report_includes(Error, /why_failed).
del_violation(/orchestrator, /bypassed_approval) :- del_used_alternative_method(Method), del_requires_approval(Method), !del_human_approved(/alternative_method, Method).

del_requires_approval(/manual_edit).
del_requires_approval(/sed_command).
del_requires_approval(/direct_file_write).

# ---- rules/notification_rules.mg ----
# Notification Rules
# ResonantOS Logician

ntf_cron_category(/fix, /routine).
ntf_cron_category(/backup, /routine).
ntf_cron_category(/cleanup, /routine).
ntf_cron_category(/maintenance, /routine).
ntf_cron_category(/monitor, /actionable).
ntf_cron_category(/security, /critical).
ntf_cron_category(/alert, /critical).
ntf_cron_category(/research, /routine).

ntf_cron_delivery(/routine, /success, /silent).
ntf_cron_delivery(/routine, /failure, /notify).
ntf_cron_delivery(/actionable, /success, /notify).
ntf_cron_delivery(/actionable, /failure, /notify).
ntf_cron_delivery(/critical, /success, /notify).
ntf_cron_delivery(/critical, /failure, /notify).

ntf_quiet_hour_delivery(/critical, /notify).
ntf_quiet_hour_delivery(/actionable, /defer).
ntf_quiet_hour_delivery(/routine, /silent).

ntf_notification_priority(/critical, /immediate).
ntf_notification_priority(/actionable, /respect_quiet).
ntf_notification_priority(/routine, /silent).

# ---- rules/preparation_rules.mg ----
# Preparation Protocol Rules
# ResonantOS Logician

prep_ai_time_equivalent(/thirty_human_minutes, /one_ai_minute).
prep_ai_time_equivalent(/two_human_hours, /five_ai_minutes).
prep_ai_time_equivalent(/three_human_weeks, /one_ai_day).

prep_parallel_bonus(/one_agent, /baseline).
prep_parallel_bonus(/two_agents, /reduced_time).
prep_parallel_bonus(/three_agents, /reduced_more).
prep_parallel_bonus(/four_or_more_agents, /minimum_time).

prep_task_size(/quick).
prep_task_size(/medium).
prep_task_size(/significant).

prep_protocol_applies(/main, /full_preparation).
prep_protocol_applies(/researcher, /deep_dive).
prep_protocol_applies(/doer, /research_first_when_unfamiliar).
prep_protocol_applies(/website, /inspiration_research).
prep_protocol_applies(/dao, /governance_review).
prep_protocol_applies(/voice, /message_clarity).
prep_protocol_applies(/creative, /concept_exploration).
prep_protocol_applies(/setup, /safety_precheck).
prep_protocol_applies(/acupuncturist, /diagnostic_trace).
prep_protocol_applies(/blindspot, /risk_scan).

prep_step(/main, /self_challenge).
prep_step(/main, /research).
prep_step(/main, /multi_perspective).
prep_step(/main, /act).

prep_step(/doer, /understand_spec).
prep_step(/doer, /research_if_needed).
prep_step(/doer, /plan_approach).
prep_step(/doer, /implement).

prep_step(/website, /understand_brief).
prep_step(/website, /gather_inspiration).
prep_step(/website, /explore_options).
prep_step(/website, /create).

prep_step(/researcher, /clarify_question).
prep_step(/researcher, /identify_sources).
prep_step(/researcher, /gather_info).
prep_step(/researcher, /synthesize).
prep_step(/researcher, /report).

prep_step(/dao, /understand_proposal).
prep_step(/dao, /analyze_incentives).
prep_step(/dao, /consider_attack_vectors).
prep_step(/dao, /multi_stakeholder_view).
prep_step(/dao, /recommend).

prep_applies_to(/halt_protocol, /all_agents).

prep_should_halt(Agent, Task, /requirements_unclear) :- prep_unclear_requirements(Task), prep_agent(Agent).
prep_should_halt(Agent, Task, /missing_context) :- prep_missing_critical_context(Task), prep_agent(Agent).
prep_should_halt(Agent, Task, /contradictory_constraints) :- prep_contradictory_constraints(Task), prep_agent(Agent).
prep_should_halt(Agent, Task, /scope_undefined) :- prep_scope_undefined(Task), prep_agent(Agent).

prep_agent(/main).
prep_agent(/doer).
prep_agent(/website).
prep_agent(/researcher).
prep_agent(/dao).
prep_agent(/voice).
prep_agent(/creative).
prep_agent(/setup).
prep_agent(/acupuncturist).
prep_agent(/blindspot).

prep_violation(Agent, /ignored_halt) :- prep_should_halt(Agent, Task, _), prep_acted_on(Agent, Task).
prep_violation(/doer, /guessing_spec) :- prep_unclear_spec(Task), prep_implemented(/doer, Task), !prep_asked_clarification(/doer, Task).
prep_violation(/researcher, /no_sources) :- prep_completed_research(/researcher, Task), !prep_has_sources(Task).

prep_vague_term(/something).
prep_vague_term(/somehow).
prep_vague_term(/whatever).
prep_vague_term(/etc).
prep_vague_term(/stuff).
prep_vague_term(/things).
prep_vague_term(/maybe).
prep_vague_term(/kind_of).
prep_vague_term(/sort_of).

prep_ready_to_act(Agent, Task) :- prep_agent(Agent), !prep_should_halt(Agent, Task, _).

# ---- rules/research_rules.mg ----
# Research Rules
# ResonantOS Logician

res_research_tool(/brave_api, /quick).
res_research_tool(/perplexity, /standard).
res_research_tool(/perplexity_pro, /deep).

res_tool_tier(/brave_api, 1).
res_tool_tier(/perplexity, 2).
res_tool_tier(/perplexity_pro, 3).

res_can_use(/researcher, /brave_api).
res_can_use(/researcher, /perplexity).
res_can_use(/researcher, /perplexity_pro).

res_can_use(/main, /brave_api).
res_can_use(/dao, /brave_api).
res_can_use(/dao, /perplexity).
res_can_use(/voice, /brave_api).
res_can_use(/website, /brave_api).
res_can_use(/creative, /brave_api).
res_can_use(/blindspot, /brave_api).

res_rate_limit(/main, /brave_api, 50).
res_rate_limit(/doer, /brave_api, 30).
res_rate_limit(/website, /brave_api, 20).
res_rate_limit(/dao, /brave_api, 30).
res_rate_limit(/researcher, /brave_api, 100).
res_rate_limit(/researcher, /perplexity, 30).
res_rate_limit(/dao, /perplexity, 15).
res_rate_limit(/researcher, /perplexity_pro, 10).

res_within_rate_limit(Agent, Tool) :-
  res_rate_limit(Agent, Tool, Max),
  res_current_usage(Agent, Tool, Current),
  Current < Max.

res_block_tool_use(Agent, Tool) :-
  res_rate_limit(Agent, Tool, Max),
  res_current_usage(Agent, Tool, Current),
  Current >= Max.

res_research_depth(Query, /quick) :- res_quick_indicator(Query), !res_standard_indicator(Query), !res_deep_indicator(Query).
res_research_depth(Query, /standard) :- res_standard_indicator(Query), !res_deep_indicator(Query).
res_research_depth(Query, /deep) :- res_deep_indicator(Query).
res_research_depth(Query, /quick) :- !res_quick_indicator(Query), !res_standard_indicator(Query), !res_deep_indicator(Query).

res_must_delegate_research(Agent, Query, /researcher) :- res_research_depth(Query, /standard), !res_can_use(Agent, /perplexity).
res_must_delegate_research(Agent, Query, /researcher) :- res_research_depth(Query, /deep), !res_can_use(Agent, /perplexity_pro).

res_non_researcher_agent(/main).
res_non_researcher_agent(/dao).
res_non_researcher_agent(/doer).
res_non_researcher_agent(/website).
res_non_researcher_agent(/voice).
res_non_researcher_agent(/creative).
res_non_researcher_agent(/setup).
res_non_researcher_agent(/acupuncturist).
res_non_researcher_agent(/blindspot).
res_should_delegate_research(Agent, Query, /researcher) :- res_research_depth(Query, /deep), res_non_researcher_agent(Agent).

res_violation(Agent, /unauthorized_tool_use, Tool) :- res_used_tool(Agent, Tool), !res_can_use(Agent, Tool).
res_violation(Agent, /failed_to_delegate, Query) :- res_must_delegate_research(Agent, Query, /researcher), res_did_research_self(Agent, Query).

res_suggest_upgrade(Query, /perplexity) :- res_research_outcome(Query, /brave_api, /insufficient).
res_suggest_upgrade(Query, /perplexity_pro) :- res_research_outcome(Query, /perplexity, /insufficient).
res_suggest_downgrade(Query, /perplexity) :- res_research_outcome(Query, /perplexity_pro, /excessive).
res_suggest_downgrade(Query, /brave_api) :- res_research_outcome(Query, /perplexity, /excessive).

res_violation(/main, /manual_deep_research, /none) :- res_research_depth(/current_query, /deep), !res_perplexity_used(/current_query).
res_violation(/main, /no_alert_on_perplexity_fail, /none) :- res_perplexity_failed(Error), !res_human_informed(/perplexity_failed, Error).
res_non_deep_mode(/quick).
res_non_deep_mode(/standard).
res_violation(/main, /wrong_search_mode, /none) :- res_research_depth(/current_query, /deep), res_search_mode(/current_query, Mode), res_non_deep_mode(Mode), !res_human_approved(/quick_mode).

# ---- rules/security_rules.mg ----
# Security Rules
# ResonantOS Logician

sec_sensitive_pattern(/api_key, /sk_prefix).
sec_sensitive_pattern(/api_key, /anthropic_api_key_name).
sec_sensitive_pattern(/api_key, /openai_api_key_name).
sec_sensitive_pattern(/token, /ghp_prefix).
sec_sensitive_pattern(/token, /gho_prefix).
sec_sensitive_pattern(/token, /xoxb_prefix).
sec_sensitive_pattern(/token, /xoxp_prefix).
sec_sensitive_pattern(/private_key, /pem_private_key_block).
sec_sensitive_pattern(/recovery_phrase, /bip39_phrase).
sec_sensitive_pattern(/seed, /bip39_seed_sequence).
sec_sensitive_pattern(/password, /password_marker).
sec_sensitive_pattern(/credential, /secret_marker).
sec_sensitive_pattern(/ssh_key, /openssh_private_key_block).

sec_is_memory_content(Path) :- sec_path_has_tag(Path, /memory_md).
sec_is_memory_content(Path) :- sec_path_has_tag(Path, /memory_dir).
sec_is_memory_content(Path) :- sec_path_has_tag(Path, /user_md).
sec_is_memory_content(Path) :- sec_path_has_tag(Path, /shared_log).
sec_is_memory_content(Path) :- sec_path_has_tag(Path, /session_thread).
sec_is_memory_content(Path) :- sec_path_has_tag(Path, /daily_notes).
sec_is_memory_content(Path) :- sec_path_has_tag(Path, /heartbeat_state).

sec_block_git_add(Path) :- sec_is_memory_content(Path).
sec_block_git_push(Repo, Path) :- sec_is_memory_content(Path), sec_repo(Repo).
sec_block_git_commit(Path) :- sec_is_memory_content(Path).

sec_private_repo(/resonantos_augmentor).
sec_block_share_repo(Repo) :- sec_private_repo(Repo).
sec_block_external_reference(Repo) :- sec_private_repo(Repo).

sec_allowed_backup_dest(/local_encrypted).
sec_allowed_backup_dest(/google_drive_encrypted).
sec_blocked_backup_dest(/github).
sec_blocked_backup_dest(/gitlab).
sec_blocked_backup_dest(/bitbucket).

sec_block_backup(Dest, Data) :- sec_blocked_backup_dest(Dest), sec_is_memory_content(Data).

sec_forbidden_output(Data) :- sec_data_matches_type(Data, /api_key).
sec_forbidden_output(Data) :- sec_data_matches_type(Data, /token).
sec_forbidden_output(Data) :- sec_data_matches_type(Data, /private_key).
sec_forbidden_output(Data) :- sec_data_matches_type(Data, /recovery_phrase).
sec_forbidden_output(Data) :- sec_data_matches_type(Data, /seed).
sec_forbidden_output(Data) :- sec_data_matches_type(Data, /ssh_key).

sec_block_output(Channel, Data) :- sec_channel(Channel), sec_forbidden_output(Data).

sec_memory_file(Path) :- sec_path_has_tag(Path, /memory_md).
sec_memory_file(Path) :- sec_path_has_tag(Path, /memory_dir).
sec_memory_file(Path) :- sec_path_has_tag(Path, /clawd_markdown).

sec_forbidden_memory_write(Data) :- sec_data_matches_type(Data, /recovery_phrase).
sec_forbidden_memory_write(Data) :- sec_data_matches_type(Data, /seed).
sec_forbidden_memory_write(Data) :- sec_data_matches_type(Data, /private_key).
sec_forbidden_memory_write(Data) :- sec_data_matches_type(Data, /ssh_key).
sec_forbidden_memory_write(Data) :- sec_data_matches_type(Data, /password).
sec_forbidden_memory_write(Data) :- sec_data_matches_type(Data, /api_key).

sec_block_write(Path, Data) :- sec_memory_file(Path), sec_forbidden_memory_write(Data).

sec_pii_pattern(/email).
sec_pii_pattern(/phone).
sec_pii_pattern(/address).
sec_financial_pattern(/bank_account).
sec_financial_pattern(/credit_card).
sec_financial_pattern(/iban).

sec_forbidden_in_group(Data) :- sec_data_matches_type(Data, /pii).
sec_forbidden_in_group(Data) :- sec_data_matches_type(Data, /financial).
sec_forbidden_in_group(Data) :- sec_data_matches_type(Data, /sensitive).

sec_group_context(/discord).
sec_group_context(/group).
sec_group_context(/channel).

sec_block_output(Channel, Data) :- sec_is_group_channel(Channel), sec_forbidden_in_group(Data).

sec_trusted_agent(/main).
sec_trusted_agent(/researcher).
sec_trusted_agent(/doer).
sec_trusted_agent(/website).

sec_allow_external_request(Agent, Count) :- sec_trusted_agent(Agent), sec_request_count(Agent, Count).
sec_allow_external_request(Agent, Count) :- !sec_trusted_agent(Agent), Count < 10.

sec_suspicious_url(/githuh_com).
sec_suspicious_url(/goggle_com).
sec_suspicious_url(/antropic_com).

sec_block_request(Url) :- sec_url_tag(Url, Tag), sec_suspicious_url(Tag).

sec_risk_action(Score, /block) :- Score > 80.
sec_risk_action(Score, /warn) :- Score > 50, Score <= 80.
sec_risk_action(Score, /allow) :- Score <= 50.

sec_requires_human_approval(Action) :- sec_risk_action_score(Action, Score), sec_risk_action(Score, /block).
sec_requires_human_approval(Action) :- sec_is_destructive(Action).

sec_is_destructive(Action) :- sec_action_tag(Action, /rm_rf).
sec_is_destructive(Action) :- sec_action_tag(Action, /delete).
sec_is_destructive(Action) :- sec_action_tag(Action, /drop_table).
sec_is_destructive(Action) :- sec_action_tag(Action, /format).

sec_injection_pattern(/ignore_previous_instructions).
sec_injection_pattern(/ignore_all_instructions).
sec_injection_pattern(/you_are_now).
sec_injection_pattern(/override_instructions).
sec_injection_pattern(/disregard).
sec_injection_pattern(/forget_everything).
sec_injection_pattern(/jailbreak).
sec_injection_pattern(/dan_mode).

sec_block_input(Data) :- sec_data_injection_tag(Data, Tag), sec_injection_pattern(Tag).

sec_suspicious_encoding(/base64_long).
sec_suspicious_encoding(/hex_long).
sec_requires_decode_scan(Data) :- sec_data_encoding_tag(Data, Tag), sec_suspicious_encoding(Tag).

sec_channel(/discord).
sec_channel(/telegram).
sec_channel(/file).

# ---- rules/verification_rules.mg ----
# Verification Before Claim Rules
# ResonantOS Logician

ver_verifiable_claim(/agent_count).
ver_verifiable_claim(/skill_count).
ver_verifiable_claim(/session_count).
ver_verifiable_claim(/cron_job_count).
ver_verifiable_claim(/memory_file_count).
ver_verifiable_claim(/route_count).
ver_verifiable_claim(/plugin_list).
ver_verifiable_claim(/agent_model_assignment).
ver_verifiable_claim(/service_status).
ver_verifiable_claim(/version_number).
ver_verifiable_claim(/sqlite_store_count).
ver_verifiable_claim(/document_count).

ver_verification_method(/agent_count, /openclaw_status).
ver_verification_method(/skill_count, /openclaw_skills_list).
ver_verification_method(/session_count, /openclaw_status).
ver_verification_method(/cron_job_count, /openclaw_cron_list).
ver_verification_method(/memory_file_count, /openclaw_memory_status).
ver_verification_method(/route_count, /grep_route_count).
ver_verification_method(/plugin_list, /openclaw_plugins_list).
ver_verification_method(/agent_model_assignment, /openclaw_agents_list).
ver_verification_method(/service_status, /process_status_check).
ver_verification_method(/version_number, /version_file_or_flag).
ver_verification_method(/sqlite_store_count, /sqlite_file_count).
ver_verification_method(/document_count, /ssot_markdown_count).

ver_valid_claim_label(/verified).
ver_valid_claim_label(/code_reviewed).
ver_valid_claim_label(/untested).
ver_valid_claim_label(/approximate).

ver_violation(Agent, /unverified_fix_claim) :- ver_claimed_fixed(Agent, Component), !ver_verified_by_test(Agent, Component).

ver_violation(Agent, /unverified_state_claim) :-
  ver_asserted_system_state(Agent, ClaimType, Value),
  ver_verifiable_claim(ClaimType),
  !ver_verified_against_source(Agent, ClaimType).

ver_violation(Agent, /stale_verification) :-
  ver_verified_against_source(Agent, ClaimType),
  ver_verification_age_minutes(Agent, ClaimType, AgeMinutes),
  AgeMinutes > 60.

ver_violation(Agent, /unlabeled_claim) :-
  ver_asserted_system_state(Agent, ClaimType, Value),
  ver_verifiable_claim(ClaimType),
  !ver_has_claim_label(Agent, ClaimType, _).

ver_ui_surface(/dashboard_page).
ver_ui_surface(/web_interface).
ver_ui_surface(/telegram_message).
ver_ui_surface(/paper_diagram).

ver_violation(Agent, /no_human_side_verification) :-
  ver_claimed_visible_in_ui(Agent, Component, Surface),
  ver_ui_surface(Surface),
  ver_verified_via_api(Agent, Component),
  !ver_verified_via_ui(Agent, Component, Surface).

ver_human_verification_method(/dashboard_page, /browser_open_screenshot_confirm).
ver_human_verification_method(/web_interface, /browser_navigate_snapshot_check).
ver_human_verification_method(/telegram_message, /delivery_and_readability_confirm).
ver_human_verification_method(/paper_diagram, /screenshot_and_render_confirm).

ver_requires_dual_verification(Action) :- ver_action_adds_to_ui(Action).
ver_requires_dual_verification(Action) :- ver_action_modifies_ui(Action).
ver_requires_dual_verification(Action) :- ver_action_claims_ui_state(Action).

ver_requires_count_verification(/architecture_diagram).
ver_requires_count_verification(/ssot_doc).
ver_requires_count_verification(/status_report).

ver_violation(Agent, /diagram_unverified_data) :-
  ver_updating_document(Agent, DocType),
  ver_requires_count_verification(DocType),
  ver_contains_system_counts(Agent, DocType),
  !ver_all_counts_verified(Agent, DocType).

ver_correct_sequence(/check_system, /write_document).
ver_violation(Agent, /write_before_check) :- ver_action_sequence(Agent, /write_document, /check_system).

ver_enforcement_stage(/verification_before_claim, /advisory).
