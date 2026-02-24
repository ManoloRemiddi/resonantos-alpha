# Template: Agent Registry
# Define your agents and trust levels here.
# Trust levels: 1 (lowest) to 5 (highest)
#
# Usage: Copy this file to your rules directory and customize.

# === Your Agents ===
# agent(/name).
# trust_level(/name, N).

agent(/orchestrator).
trust_level(/orchestrator, 5).

agent(/coder).
trust_level(/coder, 3).

agent(/researcher).
trust_level(/researcher, 3).

agent(/tester).
trust_level(/tester, 2).

# Add more agents as needed:
# agent(/designer).
# trust_level(/designer, 2).
