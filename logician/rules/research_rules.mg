% ============================================================================
% RESEARCH RULES - Tool Access & Delegation
% ResonantOS Logician - Research resource management
% ============================================================================

% ----------------------------------------------------------------------------
% RESEARCH TOOLS REGISTRY
% ----------------------------------------------------------------------------

research_tool(brave_api, quick, "Web search, facts, quick lookups").
research_tool(perplexity, standard, "Multi-source summaries, comparisons").
research_tool(perplexity_pro, deep, "Deep research, strategy, analysis").

% Tool tiers
tool_tier(brave_api, 1).
tool_tier(perplexity, 2).
tool_tier(perplexity_pro, 3).

% ----------------------------------------------------------------------------
% TOOL ACCESS PERMISSIONS
% ----------------------------------------------------------------------------

% Researcher has full access
can_use(researcher, brave_api).
can_use(researcher, perplexity).
can_use(researcher, perplexity_pro).

% Strategist: quick + can delegate
can_use(strategist, brave_api).
\+ can_use(strategist, perplexity).
\+ can_use(strategist, perplexity_pro).

% Coder: quick only
can_use(coder, brave_api).
\+ can_use(coder, perplexity).
\+ can_use(coder, perplexity_pro).

% Designer: quick only
can_use(designer, brave_api).
\+ can_use(designer, perplexity).
\+ can_use(designer, perplexity_pro).

% YouTube: quick + standard (needs research for content)
can_use(youtube, brave_api).
can_use(youtube, perplexity).
\+ can_use(youtube, perplexity_pro).

% DAO: quick + standard (governance research)
can_use(dao, brave_api).
can_use(dao, perplexity).
\+ can_use(dao, perplexity_pro).

% ----------------------------------------------------------------------------
% RATE LIMITS (per hour)
% ----------------------------------------------------------------------------

rate_limit(strategist, brave_api, 50).
rate_limit(coder, brave_api, 30).
rate_limit(designer, brave_api, 15).
rate_limit(youtube, brave_api, 40).
rate_limit(dao, brave_api, 30).
rate_limit(researcher, brave_api, 100).

rate_limit(researcher, perplexity, 30).
rate_limit(youtube, perplexity, 15).
rate_limit(dao, perplexity, 15).

rate_limit(researcher, perplexity_pro, 10).  % Expensive, limited

% Check rate limit
within_rate_limit(Agent, Tool) :-
    rate_limit(Agent, Tool, Max),
    current_usage(Agent, Tool, Current),
    Current < Max.

% Block if over limit
block_tool_use(Agent, Tool) :-
    rate_limit(Agent, Tool, Max),
    current_usage(Agent, Tool, Current),
    Current >= Max.

% ----------------------------------------------------------------------------
% RESEARCH DEPTH CLASSIFICATION
% ----------------------------------------------------------------------------

% Quick research indicators
quick_research_indicator(Query) :- contains(Query, "what is").
quick_research_indicator(Query) :- contains(Query, "definition").
quick_research_indicator(Query) :- contains(Query, "when did").
quick_research_indicator(Query) :- contains(Query, "who is").
quick_research_indicator(Query) :- word_count(Query, N), N < 10.

% Standard research indicators
standard_research_indicator(Query) :- contains(Query, "compare").
standard_research_indicator(Query) :- contains(Query, "difference between").
standard_research_indicator(Query) :- contains(Query, "pros and cons").
standard_research_indicator(Query) :- contains(Query, "how to").
standard_research_indicator(Query) :- contains(Query, "best practices").

% Deep research indicators
deep_research_indicator(Query) :- contains(Query, "strategy").
deep_research_indicator(Query) :- contains(Query, "market analysis").
deep_research_indicator(Query) :- contains(Query, "competitive").
deep_research_indicator(Query) :- contains(Query, "comprehensive").
deep_research_indicator(Query) :- contains(Query, "in-depth").
deep_research_indicator(Query) :- contains(Query, "research").
deep_research_indicator(Query) :- word_count(Query, N), N > 30.

% Classify research depth needed
research_depth(Query, quick) :- 
    quick_research_indicator(Query),
    \+ standard_research_indicator(Query),
    \+ deep_research_indicator(Query).

research_depth(Query, standard) :-
    standard_research_indicator(Query),
    \+ deep_research_indicator(Query).

research_depth(Query, deep) :-
    deep_research_indicator(Query).

% Default to quick if unclear
research_depth(Query, quick) :-
    \+ quick_research_indicator(Query),
    \+ standard_research_indicator(Query),
    \+ deep_research_indicator(Query).

% ----------------------------------------------------------------------------
% DELEGATION RULES
% ----------------------------------------------------------------------------

% Must delegate if can't use required tool
must_delegate_research(Agent, Query, researcher) :-
    research_depth(Query, standard),
    \+ can_use(Agent, perplexity).

must_delegate_research(Agent, Query, researcher) :-
    research_depth(Query, deep),
    \+ can_use(Agent, perplexity_pro).

% Should delegate for efficiency (even if could do it)
should_delegate_research(Agent, Query, researcher) :-
    research_depth(Query, deep),
    Agent \= researcher.

% Violation: Using tool without permission
violation(Agent, unauthorized_tool_use, Tool) :-
    used_tool(Agent, Tool),
    \+ can_use(Agent, Tool).

% Violation: Not delegating when required
violation(Agent, failed_to_delegate, Query) :-
    must_delegate_research(Agent, Query, _),
    did_research_self(Agent, Query).

% ----------------------------------------------------------------------------
% RESEARCH QUALITY TRACKING
% ----------------------------------------------------------------------------

% Track research outcomes for learning
research_outcome(Query, Tool, Result, useful).
research_outcome(Query, Tool, Result, insufficient).
research_outcome(Query, Tool, Result, excessive).

% Suggest tool upgrade if research was insufficient
suggest_upgrade(Query, perplexity) :-
    research_outcome(Query, brave_api, _, insufficient).

suggest_upgrade(Query, perplexity_pro) :-
    research_outcome(Query, perplexity, _, insufficient).

% Suggest downgrade if excessive
suggest_downgrade(Query, perplexity) :-
    research_outcome(Query, perplexity_pro, _, excessive).

suggest_downgrade(Query, brave_api) :-
    research_outcome(Query, perplexity, _, excessive).

% ----------------------------------------------------------------------------
% RESEARCH ENFORCEMENT RULE
% Added 2026-03-07
% ----------------------------------------------------------------------------

% Rule: Deep research must use Perplexity - never do it yourself
violation(orchestrator, manual_deep_research) :-
    research_type(Deep),
    \+ perplexity_used(Deep).

% Rule: Perplexity fails → MUST alert human immediately
violation(orchestrator, no_alert_on_perplexity_fail) :-
    perplexity_failed(Error),
    \+ human_informed(perplexity_failed, Error).

% Rule: Must use Deep Search mode unless explicitly told "quick"
research_mode(default, deep).
violation(orchestrator, wrong_search_mode) :-
    research_type(Research),
    \+ search_mode(Research, Mode),
    Mode \= deep,
    \+ human_approved(quick_mode).

% What to say when Perplexity fails
perplexity_fail_message("Perplexity unavailable: [error]. Should I try again, or can you fix the access?").
