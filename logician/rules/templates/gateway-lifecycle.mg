# Gateway Lifecycle Rules — Template
# Enforces safe gateway stop/start via Logician policy.
# Used by gateway-lifecycle.js extension.

# Actions the extension recognizes
gateway_action(/stop).
gateway_action(/restart).
gateway_action(/start).

# Stop/restart requires a resume plan (TASK-STATE.json) or maintenance mode
requires_resume_plan(/stop).
requires_resume_plan(/restart).

# Start is blocked during active maintenance
blocked_during_maintenance(/start).
blocked_during_maintenance(/restart).
