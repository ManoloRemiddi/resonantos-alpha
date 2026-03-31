# Template: Cost Policy
# Prevent expensive AI models from being used on cheap tasks.
# Deterministic > AI: if a script can do it, don't burn tokens.
#
# Usage: Customize tiers and task assignments for your budget.

# === Model cost tiers ===
model_tier(/opus, /expensive).
model_tier(/sonnet, /moderate).
model_tier(/haiku, /cheap).
model_tier(/flash, /free).

# === Task-to-model assignment ===
# Match task types to maximum allowed model tier
preferred_model(/heartbeat, /free).        # Routine checks — zero cost
preferred_model(/compression, /cheap).     # Structured transforms
preferred_model(/background, /cheap).      # Background maintenance
preferred_model(/routine, /moderate).      # Standard operations
preferred_model(/architecture, /expensive). # Complex reasoning
preferred_model(/planning, /expensive).    # Strategic decisions
preferred_model(/code_review, /expensive). # Quality matters

# === Budget enforcement (Shield Gate queries these) ===
# blocked_model_task(/opus, /heartbeat).
# blocked_model_task(/opus, /background).
# blocked_model_task(/opus, /compression).
