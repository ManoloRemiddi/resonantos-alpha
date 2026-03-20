# Template: Spawn Control
# Define which agents can create (spawn) other agents.
# Prevents privilege escalation and unauthorized agent creation.
#
# Usage: Copy and customize. Add your own spawn rules.

# === Direct permissions ===
can_spawn(/orchestrator, /coder).
can_spawn(/orchestrator, /researcher).
can_spawn(/orchestrator, /tester).
can_spawn(/coder, /tester).

# === Explicit blocks (override permissions) ===
blocked_spawn(/coder, /orchestrator).    # Coder can't create orchestrator
blocked_spawn(/tester, /coder).          # Tester can't create coder
blocked_spawn(/researcher, /coder).      # Researcher can't create coder

# === Derived rule: spawn allowed if permitted AND not blocked ===
spawn_allowed(From, To) :- can_spawn(From, To), !blocked_spawn(From, To).
