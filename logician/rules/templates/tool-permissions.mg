# Template: Tool Permissions
# Define which agents can use which tools.
# Dangerous tools require elevated trust levels.
#
# Usage: Copy and customize for your tool set.

# === Tool registry ===
tool(/exec).
tool(/file_write).
tool(/file_delete).
tool(/web_search).
tool(/web_fetch).
tool(/browser).
tool(/message_send).
tool(/git).

# === Permissions per agent ===
# Orchestrator: full access
can_use_tool(/orchestrator, /exec).
can_use_tool(/orchestrator, /file_write).
can_use_tool(/orchestrator, /file_delete).
can_use_tool(/orchestrator, /web_search).
can_use_tool(/orchestrator, /web_fetch).
can_use_tool(/orchestrator, /browser).
can_use_tool(/orchestrator, /message_send).
can_use_tool(/orchestrator, /git).

# Coder: code-related tools
can_use_tool(/coder, /exec).
can_use_tool(/coder, /file_write).
can_use_tool(/coder, /git).

# Researcher: read-only web
can_use_tool(/researcher, /web_search).
can_use_tool(/researcher, /web_fetch).

# === Dangerous tool classification ===
dangerous_tool(/exec).
dangerous_tool(/file_delete).
dangerous_tool(/git).       # Can push to remote

# === Derived: dangerous tool usage requires trust >= 3 ===
can_use_dangerous(Agent, Tool) :-
  can_use_tool(Agent, Tool),
  dangerous_tool(Tool),
  trust_level(Agent, Level),
  Level >= 3.
