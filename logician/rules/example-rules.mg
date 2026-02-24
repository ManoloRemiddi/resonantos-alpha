# ============================================================
# ResonantOS — Example Logician Rules
# Engine: Mangle (Google Datalog)
# Purpose: Starter policy rules for AI agent orchestration
#
# Customize these for your setup. See rules/templates/ for
# more patterns you can use.
# ============================================================

# ============================================================
# AGENT REGISTRY
# Define your agents and their trust levels (1-5)
# ============================================================

agent(/orchestrator).
agent(/coder).
agent(/researcher).
agent(/tester).

trust_level(/orchestrator, 5).
trust_level(/coder, 3).
trust_level(/researcher, 3).
trust_level(/tester, 2).

# ============================================================
# SPAWN RULES
# Who can create (spawn) whom?
# ============================================================

can_spawn(/orchestrator, /coder).
can_spawn(/orchestrator, /researcher).
can_spawn(/orchestrator, /tester).
can_spawn(/coder, /tester).

# Explicit blocks (prevent privilege escalation)
blocked_spawn(/coder, /orchestrator).
blocked_spawn(/tester, /coder).
blocked_spawn(/researcher, /coder).

# Derived: spawn allowed if permitted AND not blocked
spawn_allowed(From, To) :- can_spawn(From, To), !blocked_spawn(From, To).

# ============================================================
# TOOL PERMISSIONS
# Which agents can use which tools?
# ============================================================

tool(/exec).
tool(/file_write).
tool(/file_delete).
tool(/web_search).
tool(/web_fetch).
tool(/browser).
tool(/message_send).

# Orchestrator: full access
can_use_tool(/orchestrator, /exec).
can_use_tool(/orchestrator, /file_write).
can_use_tool(/orchestrator, /file_delete).
can_use_tool(/orchestrator, /web_search).
can_use_tool(/orchestrator, /web_fetch).
can_use_tool(/orchestrator, /browser).
can_use_tool(/orchestrator, /message_send).

# Coder: code-related tools only
can_use_tool(/coder, /exec).
can_use_tool(/coder, /file_write).

# Researcher: read-only web access
can_use_tool(/researcher, /web_search).
can_use_tool(/researcher, /web_fetch).

# Tester: can run tests
can_use_tool(/tester, /exec).
can_use_tool(/tester, /browser).

# Dangerous tools require trust >= 3
dangerous_tool(/exec).
dangerous_tool(/file_delete).

can_use_dangerous(Agent, Tool) :-
  can_use_tool(Agent, Tool),
  dangerous_tool(Tool),
  trust_level(Agent, Level),
  Level >= 3.

# ============================================================
# SECURITY — Injection & Destructive Pattern Detection
# ============================================================

injection_pattern("ignore previous instructions").
injection_pattern("ignore all previous").
injection_pattern("disregard previous").
injection_pattern("forget your instructions").
injection_pattern("jailbreak").
injection_pattern("pretend you are").
injection_pattern("override your programming").

destructive_pattern("rm -rf").
destructive_pattern("rm -r /").
destructive_pattern("drop table").
destructive_pattern("drop database").
destructive_pattern("chmod -R 777 /").

# ============================================================
# SENSITIVE DATA TYPES
# ============================================================

sensitive_type(/api_key).
sensitive_type(/token).
sensitive_type(/private_key).
sensitive_type(/seed_phrase).
sensitive_type(/password).

forbidden_output_type(/api_key).
forbidden_output_type(/private_key).
forbidden_output_type(/seed_phrase).
forbidden_output_type(/password).

sensitive_pattern(/api_key, "sk-").
sensitive_pattern(/api_key, "sk-ant-").
sensitive_pattern(/token, "ghp_").
sensitive_pattern(/token, "xoxb-").
sensitive_pattern(/private_key, "-----BEGIN").

# ============================================================
# COST POLICY
# Prevent expensive models on cheap tasks
# ============================================================

model_tier(/opus, /expensive).
model_tier(/sonnet, /moderate).
model_tier(/haiku, /cheap).

preferred_model(/heartbeat, /haiku).
preferred_model(/background, /haiku).
preferred_model(/compression, /haiku).
preferred_model(/architecture, /opus).
preferred_model(/planning, /opus).
preferred_model(/routine, /sonnet).

# ============================================================
# VERIFICATION GATE
# Require test evidence before code pushes
# ============================================================

requires_verification(/code_change).
verification_method(/curl).
verification_method(/unit).
verification_method(/script).
verification_method(/manual).
weak_verification(/code_review).
weak_verification(/untestable).
