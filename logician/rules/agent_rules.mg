% ============================================================================
% AGENT RULES - Multi-Agent Orchestration
% ResonantOS Logician - Agent permissions and spawning
% ============================================================================

% ----------------------------------------------------------------------------
% AGENT REGISTRY
% ----------------------------------------------------------------------------

% Core agents
agent(strategist, "🤖", "Strategic coordinator, orchestrates other agents").
agent(coder, "🧮", "Code implementation and debugging").
agent(designer, "🎨", "UI/UX design and visual work").
agent(researcher, "🔬", "Deep research and analysis").
agent(youtube, "📺", "YouTube content and optimization").
agent(dao, "🏛️", "DAO and governance specialist").

% Human
human(manolo).
is_admin(manolo).

% ----------------------------------------------------------------------------
% SPAWNING PERMISSIONS - Who can spawn whom
% ----------------------------------------------------------------------------

% Strategist can spawn execution agents
can_spawn(strategist, coder).
can_spawn(strategist, designer).
can_spawn(strategist, researcher).
can_spawn(strategist, youtube).
can_spawn(strategist, dao).

% Coder can spawn helper agents for subtasks
can_spawn(coder, researcher).

% Designer can spawn researcher for reference
can_spawn(designer, researcher).

% BLOCKED: Execution agents cannot spawn strategist (prevents hierarchy bypass)
\+ can_spawn(coder, strategist).
\+ can_spawn(designer, strategist).
\+ can_spawn(researcher, strategist).

% BLOCKED: Agents cannot spawn themselves (prevents infinite loops)
\+ can_spawn(X, X).

% Admin override
can_spawn(_, Agent) :- is_admin_request.

% ----------------------------------------------------------------------------
% AGENT CAPABILITIES
% ----------------------------------------------------------------------------

% File system access
can_read_files(strategist).
can_read_files(coder).
can_read_files(designer).
can_read_files(researcher).

can_write_files(strategist).
can_write_files(coder).
can_write_files(designer).

% External communication
can_send_external(strategist).
can_send_external(youtube).   % Needs to interact with YouTube API

\+ can_send_external(coder).      % Coder works internally only
\+ can_send_external(designer).   % Designer works internally only
\+ can_send_external(researcher). % Researcher reads, doesn't send

% Code execution
can_execute_code(coder).
can_execute_code(strategist).  % For orchestration tasks

\+ can_execute_code(designer).
\+ can_execute_code(youtube).

% Memory access
can_read_memory(strategist).
can_write_memory(strategist).

can_read_memory(coder).        % Can read for context
\+ can_write_memory(coder).    % Cannot modify shared memory

can_read_memory(researcher).
\+ can_write_memory(researcher).

% ----------------------------------------------------------------------------
% CHANNEL PERMISSIONS
% ----------------------------------------------------------------------------

% Who can respond on which channels
can_respond(strategist, telegram, manolo).
can_respond(strategist, discord, _).      % Strategist handles Discord

\+ can_respond(coder, telegram, _).       % Coder doesn't talk to users directly
\+ can_respond(coder, discord, _).

\+ can_respond(designer, telegram, _).
\+ can_respond(designer, discord, _).

% Only strategist talks to Manolo directly
direct_channel(telegram, manolo).
can_respond(Agent, Channel, User) :- 
    direct_channel(Channel, User),
    Agent = strategist.

% ----------------------------------------------------------------------------
% TASK DELEGATION RULES
% ----------------------------------------------------------------------------

% Task types and appropriate agents
task_type(code_implementation, coder).
task_type(bug_fix, coder).
task_type(ui_design, designer).
task_type(visual_asset, designer).
task_type(research, researcher).
task_type(analysis, researcher).
task_type(youtube_optimization, youtube).
task_type(governance, dao).
task_type(strategy, strategist).

% Delegate to appropriate agent
should_delegate(Task, Agent) :- 
    task_type(TaskType, Agent),
    matches_task_type(Task, TaskType).

% Strategist should not implement directly
violation(strategist, direct_implementation) :-
    task_type(TaskType, coder),
    strategist_doing(TaskType).

% ----------------------------------------------------------------------------
% VERIFICATION REQUIREMENTS
% ----------------------------------------------------------------------------

% Actions requiring human verification
requires_verification(Action) :- is_financial(Action).
requires_verification(Action) :- is_public_post(Action).
requires_verification(Action) :- is_destructive(Action).
requires_verification(Action) :- spawns_more_than(Action, 3).

% Financial actions
is_financial(Action) :- contains(Action, "transfer").
is_financial(Action) :- contains(Action, "payment").
is_financial(Action) :- contains(Action, "wallet").

% Public posts
is_public_post(Action) :- contains(Action, "tweet").
is_public_post(Action) :- contains(Action, "post").
is_public_post(Action) :- contains(Action, "publish").

% Spawn limits
spawns_more_than(Action, N) :- 
    spawn_count(Action, Count), 
    Count > N.

% ----------------------------------------------------------------------------
% SESSION ISOLATION
% ----------------------------------------------------------------------------

% Agent sessions are isolated
session_isolated(coder).
session_isolated(designer).
session_isolated(researcher).

% Strategist can access other sessions
can_access_session(strategist, _).

% Agents cannot access each other's sessions
\+ can_access_session(coder, designer).
\+ can_access_session(designer, coder).

% Except through strategist relay
can_relay(strategist, From, To) :- 
    agent(From, _, _), 
    agent(To, _, _),
    From \= To.
