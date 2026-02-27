% ============================================================================
% AGENT CREATION RULES
% ResonantOS Logician - Ensure proper agent setup
% ============================================================================

% ----------------------------------------------------------------------------
% AGENT DIRECTORY ARCHITECTURE
% ----------------------------------------------------------------------------

% Standard: All agents use ~/clawd/agents/<agent>/ as workspace
agent_workspace_base("~/.openclaw/agents").

% Required files for every agent
required_agent_file("AGENTS.md").
required_agent_file("SOUL.md").
required_agent_file("auth-profiles.json").  % CRITICAL - must be copied

% Optional but recommended
recommended_agent_file("IDENTITY.md").
recommended_agent_file("USER.md").
recommended_agent_file("TOOLS.md").
recommended_agent_file("MEMORY.md").

% ----------------------------------------------------------------------------
% AUTH FILE SYNC RULES
% ----------------------------------------------------------------------------

% Auth source (Clawdbot default location)
auth_source_path(Agent, Path) :-
    atom_concat("~/.openclaw/agents/", Agent, P1),
    atom_concat(P1, "/agent/auth-profiles.json", Path).

% Auth destination (workspace)
auth_dest_path(Agent, Path) :-
    agent_workspace_base(Base),
    atom_concat(Base, "/", P1),
    atom_concat(P1, Agent, P2),
    atom_concat(P2, "/auth-profiles.json", Path).

% Auth must exist in workspace
must_have_auth(Agent) :-
    auth_dest_path(Agent, Path),
    file_exists(Path).

% Violation: Agent without auth in workspace
violation(Agent, missing_auth) :-
    agent(Agent),
    \+ must_have_auth(Agent).

% ----------------------------------------------------------------------------
% AGENT CREATION CHECKLIST
% ----------------------------------------------------------------------------

% Before agent is ready:
agent_creation_checklist([
    create_workspace_dir,           % mkdir ~/clawd/agents/<agent>
    create_agents_md,               % AGENTS.md with agent config
    create_soul_md,                 % SOUL.md with persona
    copy_auth_profiles,             % CRITICAL: Copy auth from ~/.clawdbot
    add_to_clawdbot_config,         % Add agent to clawdbot.json
    restart_gateway,                % Restart to load new agent
    test_agent_responds             % Verify it works
]).

% Most critical step
critical_step(copy_auth_profiles).

% Violation: Skipping critical step
violation(creation, skipped_auth_copy) :-
    agent_created(Agent),
    \+ auth_copied(Agent).

% ----------------------------------------------------------------------------
% SYNC PROTOCOL
% ----------------------------------------------------------------------------

% When to run sync
should_sync_auth :-
    agent_auth_error_detected.

should_sync_auth :-
    new_agent_created.

should_sync_auth :-
    daily_maintenance.

% Sync command
sync_command("~/clawd/scripts/sync-agent-auth.sh").

% ----------------------------------------------------------------------------
% PREVENTION
% ----------------------------------------------------------------------------

% Add to heartbeat checks
heartbeat_check(auth_sync) :-
    for_each_agent(Agent, must_have_auth(Agent)).

% Alert if auth missing
alert_condition(Agent, auth_missing) :-
    agent(Agent),
    \+ must_have_auth(Agent).
