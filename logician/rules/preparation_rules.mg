% ============================================================================
% PREPARATION PROTOCOL RULES
% ResonantOS Logician - Agent-specific thoughtful action
% ============================================================================

% ----------------------------------------------------------------------------
% TIME CALIBRATION - AI Scale, Not Human Scale
% ----------------------------------------------------------------------------

% AI agents work ~50x faster than human estimates
% "2 hour task" (human) = ~2-5 minutes (AI)
% "3 week project" (human) = ~1 day with parallel agents

ai_time_multiplier(0.02).  % 2% of human time estimate

% Convert human estimate to AI estimate
ai_time(HumanHours, AIHours) :-
    ai_time_multiplier(M),
    AIHours is HumanHours * M.

% Parallel agent bonus - multiple agents reduce time further
parallel_bonus(1, 1.0).    % 1 agent = no bonus
parallel_bonus(2, 0.6).    % 2 agents = 60% of single agent time
parallel_bonus(3, 0.4).    % 3 agents = 40%
parallel_bonus(N, 0.3) :- N >= 4.  % 4+ agents = 30%

% Effective AI time with parallel agents
effective_ai_time(HumanHours, AgentCount, EffectiveHours) :-
    ai_time(HumanHours, AIHours),
    parallel_bonus(AgentCount, Bonus),
    EffectiveHours is AIHours * Bonus.

% Task size classification (in AI time)
% Quick: < 5 AI minutes (was "< 30 human minutes")
% Medium: 5-30 AI minutes (was "30min - 2 human hours")  
% Significant: > 30 AI minutes (was "> 2 human hours")

task_size(Task, quick) :- 
    ai_estimated_effort(Task, Hours), 
    Hours < 0.08.  % < 5 minutes

task_size(Task, medium) :- 
    ai_estimated_effort(Task, Hours), 
    Hours >= 0.08, 
    Hours < 0.5.  % 5-30 minutes

task_size(Task, significant) :- 
    ai_estimated_effort(Task, Hours), 
    Hours >= 0.5.  % 30+ minutes

% ----------------------------------------------------------------------------
% AGENT-SPECIFIC PROTOCOLS
% ----------------------------------------------------------------------------

% ===== STRATEGIST =====
% Full preparation for strategic decisions

protocol_applies(strategist, full_preparation) :- 
    task_type(strategic).
protocol_applies(strategist, full_preparation) :- 
    task_type(architectural).
protocol_applies(strategist, full_preparation) :- 
    task_type(public_facing).

strategist_preparation_steps([
    self_challenge,      % Question assumptions
    research,            % Look at prior art (delegate to Researcher if deep)
    multi_perspective,   % Consider alternatives, maybe spawn advisors
    act                  % Execute or delegate
]).

% Strategist should NOT implement directly
violation(strategist, direct_implementation) :-
    task_type(Task, code),
    acted_on(strategist, Task),
    \+ delegated(strategist, Task, coder).

violation(strategist, direct_implementation) :-
    task_type(Task, design),
    acted_on(strategist, Task),
    \+ delegated(strategist, Task, designer).

% ===== CODER =====
% Research for unfamiliar territory, otherwise execute

protocol_applies(coder, research_first) :- 
    is_unfamiliar_tech(Task).
protocol_applies(coder, research_first) :- 
    is_complex_algorithm(Task).

coder_preparation_steps([
    understand_spec,     % HALT if unclear
    research_if_needed,  % Only for unfamiliar tech
    plan_approach,       % Brief, not extensive
    implement            % Do the work
]).

% Coder should ask for clarification, not guess
violation(coder, guessing_spec) :-
    unclear_spec(Task),
    implemented(coder, Task),
    \+ asked_clarification(coder, Task).

% ===== DESIGNER =====
% Inspiration research, then create

protocol_applies(designer, inspiration_research) :- 
    task_type(Task, visual).
protocol_applies(designer, inspiration_research) :- 
    task_type(Task, ux).

designer_preparation_steps([
    understand_brief,    % HALT if vague
    gather_inspiration,  % Look at references
    explore_options,     % 2-3 directions
    create               % Execute design
]).

% Designer should show options, not just one
should_show_options(designer, Task) :-
    task_size(Task, significant),
    task_type(Task, visual).

% ===== RESEARCHER =====
% They ARE the research - different protocol

protocol_applies(researcher, deep_dive) :- 
    research_depth(Task, deep).
protocol_applies(researcher, standard_research) :- 
    research_depth(Task, standard).

researcher_preparation_steps([
    clarify_question,    % What exactly are we researching?
    identify_sources,    % Where to look
    gather_info,         % Do the research
    synthesize,          % Compile findings
    report               % Return results
]).

% Researcher should cite sources
violation(researcher, no_sources) :-
    completed_research(researcher, Task),
    \+ has_sources(Task).

% ===== YOUTUBE =====
% Content research and optimization

protocol_applies(youtube, content_research) :- 
    task_type(Task, video_planning).
protocol_applies(youtube, seo_research) :- 
    task_type(Task, optimization).

youtube_preparation_steps([
    understand_goal,     % What's the content goal?
    research_trends,     % What's working?
    analyze_competition, % What are others doing?
    plan_content         % Create the plan
]).

% ===== DAO =====
% Governance requires multi-perspective

protocol_applies(dao, governance_review) :- 
    task_type(Task, governance).
protocol_applies(dao, economic_analysis) :- 
    task_type(Task, tokenomics).

dao_preparation_steps([
    understand_proposal,
    analyze_incentives,
    consider_attack_vectors,
    multi_stakeholder_view,
    recommend
]).

% ----------------------------------------------------------------------------
% UNIVERSAL: HALT PROTOCOL (All Agents)
% ----------------------------------------------------------------------------

% Garbage in = garbage out. Stop and ask.

applies_to(halt_protocol, _).  % All agents

should_halt(Agent, Task, Reason) :-
    unclear_requirements(Task),
    Reason = "Requirements unclear - need clarification".

should_halt(Agent, Task, Reason) :-
    missing_critical_context(Task),
    Reason = "Missing critical context - what is X?".

should_halt(Agent, Task, Reason) :-
    contradictory_constraints(Task),
    Reason = "Constraints contradict - which takes priority?".

should_halt(Agent, Task, Reason) :-
    scope_undefined(Task),
    Reason = "Scope too vague - need boundaries".

% Violation: Acting on garbage input
violation(Agent, ignored_halt) :-
    should_halt(Agent, Task, _),
    acted_on(Agent, Task).

% Vague terms that signal unclear requirements
vague_term("something").
vague_term("somehow").
vague_term("whatever").
vague_term("etc").
vague_term("stuff").
vague_term("things").
vague_term("maybe").
vague_term("kind of").
vague_term("sort of").

% Detect unclear requirements
unclear_requirements(Task) :- 
    vague_terms_count(Task, N), 
    N > 2.

% Detect missing context
missing_critical_context(Task) :- 
    references_undefined(Task, _).

% Detect scope issues (in AI time now)
scope_too_large(Task) :- 
    ai_estimated_effort(Task, Hours), 
    Hours > 4.  % > 4 AI hours = needs breakdown

% ----------------------------------------------------------------------------
% READY TO ACT - Per Agent
% ----------------------------------------------------------------------------

ready_to_act(strategist, Task) :-
    \+ should_halt(strategist, Task, _),
    (protocol_applies(strategist, full_preparation) ->
        (completed_self_challenge(strategist, Task),
         completed_research(strategist, Task),
         completed_multi_perspective(strategist, Task))
    ; true).

ready_to_act(coder, Task) :-
    \+ should_halt(coder, Task, _),
    understood_spec(coder, Task),
    (protocol_applies(coder, research_first) ->
        completed_research(coder, Task)
    ; true).

ready_to_act(designer, Task) :-
    \+ should_halt(designer, Task, _),
    understood_brief(designer, Task),
    (protocol_applies(designer, inspiration_research) ->
        gathered_inspiration(designer, Task)
    ; true).

ready_to_act(researcher, Task) :-
    \+ should_halt(researcher, Task, _),
    clarified_question(researcher, Task).

% Default: Any agent can act if no HALT condition
ready_to_act(Agent, Task) :-
    \+ should_halt(Agent, Task, _),
    \+ protocol_applies(Agent, _).
