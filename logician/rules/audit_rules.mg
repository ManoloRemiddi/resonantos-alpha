% ============================================================================
% AUDIT RULES - Logician Monitoring & Reporting
% ResonantOS Logician - Track all decisions for review
% ============================================================================

% ----------------------------------------------------------------------------
% AUDIT LOGGING - Every Decision Recorded
% ----------------------------------------------------------------------------

% All Logician queries must be logged
audit_required(all_queries).

% Log entry structure
audit_entry(
    timestamp,          % When
    session_id,         % Which session
    agent,              % Who asked
    action,             % What they wanted to do
    rules_checked,      % Which rules evaluated
    decision,           % allow / deny
    reason,             % Why
    context             % Additional context
).

% Decision types
decision_type(allow).
decision_type(deny).
decision_type(warn).      % Allowed but flagged

% ----------------------------------------------------------------------------
% LOG STORAGE
% ----------------------------------------------------------------------------

% Log file location
audit_log_path("~/.openclaw/projects/resonantos/logician/logs/audit.jsonl").

% Daily rotation
audit_log_daily_path(Date, Path) :-
    format_date(Date, DateStr),
    atom_concat("~/.openclaw/projects/resonantos/logician/logs/audit-", DateStr, P1),
    atom_concat(P1, ".jsonl", Path).

% Retention period (days)
audit_retention_days(30).

% ----------------------------------------------------------------------------
% WHAT TO LOG
% ----------------------------------------------------------------------------

% Log EVERYTHING - both approvals and denials
% Approvals can be wrong too (false negatives = security holes)

must_log(Query, deny).   % All denials
must_log(Query, allow).  % All approvals
must_log(Query, warn).   % All warnings

% In production, can sample approvals if volume too high
% sample_log(Query, allow, 0.3) :- low_risk_action(Query).

% High-risk actions: ALWAYS log in detail
high_risk_action(Query) :- involves_rule(Query, security_rules).
high_risk_action(Query) :- involves_rule(Query, crypto_rules).
high_risk_action(Query) :- involves_external_communication(Query).
high_risk_action(Query) :- involves_file_write(Query).
high_risk_action(Query) :- involves_code_execution(Query).

must_log_detailed(Query) :- high_risk_action(Query).

% ----------------------------------------------------------------------------
% NIGHTLY REPORT GENERATION
% ----------------------------------------------------------------------------

% Report schedule
nightly_report_time("03:00").

% Report contents
nightly_report_sections([
    summary_stats,
    denials_by_rule,
    denials_by_agent,
    potential_false_positives,
    rule_hit_frequency,
    recommendations
]).

% Summary statistics
report_summary([
    total_queries,
    total_allowed,
    total_denied,
    total_warned,
    allow_rate_percent,
    deny_rate_percent
]).

% Denial breakdown
report_denials_by_rule([
    rule_file,
    rule_name,
    denial_count,
    example_contexts
]).

report_denials_by_agent([
    agent_name,
    denial_count,
    most_common_denial_reason
]).

% ----------------------------------------------------------------------------
% FALSE POSITIVE DETECTION (Wrongly Denied)
% ----------------------------------------------------------------------------

% Flag potential false positives for human review
potential_false_positive(Entry) :-
    entry_decision(Entry, deny),
    entry_context(Entry, Context),
    seems_legitimate(Context).

% Heuristics for legitimate actions that got denied
seems_legitimate(Context) :-
    context_agent(Context, strategist),
    context_action(Context, Action),
    routine_action(Action).

seems_legitimate(Context) :-
    denial_count_today(Rule, Count),
    Count > 20,  % Sudden spike might indicate over-restriction
    entry_rule(Context, Rule).

% Routine actions that shouldn't be blocked
routine_action(read_file).
routine_action(web_search).
routine_action(spawn_agent).

% ----------------------------------------------------------------------------
% FALSE NEGATIVE DETECTION (Wrongly Approved)
% ----------------------------------------------------------------------------

% Flag suspicious approvals - things that got through but maybe shouldn't have
potential_false_negative(Entry) :-
    entry_decision(Entry, allow),
    entry_context(Entry, Context),
    seems_suspicious(Context).

% Heuristics for suspicious approvals
seems_suspicious(Context) :-
    context_contains_pattern(Context, sensitive_data_pattern).

seems_suspicious(Context) :-
    context_action(Context, Action),
    high_risk_action_type(Action),
    no_rule_matched(Context).  % Approved because no rule caught it

seems_suspicious(Context) :-
    context_agent(Context, Agent),
    agent_acting_unusual(Agent, Context).

% High-risk actions that should have rules
high_risk_action_type(send_external).
high_risk_action_type(write_memory).
high_risk_action_type(execute_code).
high_risk_action_type(access_wallet).
high_risk_action_type(spawn_agent).

% Unusual agent behavior
agent_acting_unusual(Agent, Context) :-
    context_action(Context, Action),
    \+ typical_action_for_agent(Agent, Action).

typical_action_for_agent(coder, write_code).
typical_action_for_agent(coder, execute_code).
typical_action_for_agent(coder, read_file).
typical_action_for_agent(designer, create_asset).
typical_action_for_agent(researcher, web_search).
typical_action_for_agent(strategist, spawn_agent).
typical_action_for_agent(strategist, delegate).

% Sensitive data patterns that should never be approved for output
sensitive_data_pattern("sk-").
sensitive_data_pattern("-----BEGIN").
sensitive_data_pattern("recovery phrase").
sensitive_data_pattern("seed phrase").
sensitive_data_pattern("private key").

% ----------------------------------------------------------------------------
% REVIEW QUEUE / TODO INTEGRATION  
% ----------------------------------------------------------------------------

% Flagged items go to TODO list, not just report
review_queue_path("~/.openclaw/projects/resonantos/logician/review_queue.json").

% Item structure for review queue
review_item(
    id,                 % Unique ID
    timestamp,          % When flagged
    type,               % false_positive | false_negative | alert
    severity,           % low | medium | high | critical
    entry,              % The audit entry
    reason,             % Why it was flagged
    status,             % pending | reviewed | resolved | dismissed
    resolution          % What was done about it
).

% Severity classification
flag_severity(Entry, critical) :-
    entry_rule(Entry, crypto_rules).

flag_severity(Entry, critical) :-
    potential_false_negative(Entry),
    entry_context(Entry, Context),
    context_contains_pattern(Context, sensitive_data_pattern).

flag_severity(Entry, high) :-
    potential_false_negative(Entry),
    high_risk_action(Entry).

flag_severity(Entry, medium) :-
    potential_false_positive(Entry).

flag_severity(Entry, low) :-
    \+ flag_severity(Entry, critical),
    \+ flag_severity(Entry, high),
    \+ flag_severity(Entry, medium).

% Auto-create TODO for flagged items
create_todo_for_flag(Entry, Todo) :-
    flag_severity(Entry, Severity),
    member(Severity, [critical, high]),
    entry_description(Entry, Desc),
    format_todo(Entry, Severity, Desc, Todo).

% TODO format
format_todo(Entry, Severity, Desc, Todo) :-
    Todo = todo{
        title: "Review Logician flag",
        description: Desc,
        priority: Severity,
        source: "logician_audit",
        entry_id: Entry.id,
        created: Entry.timestamp
    }.

% Where TODOs go
todo_destination(critical, immediate_alert).   % Alert Manolo now
todo_destination(high, daily_todo_list).       % Add to TODO.md
todo_destination(medium, weekly_review).       % Batch for weekly review
todo_destination(low, monthly_review).         % Low priority batch

% ----------------------------------------------------------------------------
% ALERTS
% ----------------------------------------------------------------------------

% Immediate alert conditions (don't wait for nightly report)
immediate_alert(Entry) :-
    entry_rule(Entry, crypto_rules),
    entry_decision(Entry, deny).

immediate_alert(Entry) :-
    entry_rule(Entry, security_rules),
    entry_context(Entry, Context),
    context_contains(Context, injection_attempt).

% Alert thresholds
alert_threshold(denials_per_hour, 50).      % Too many denials
alert_threshold(same_rule_denials, 20).     % Same rule blocking repeatedly
alert_threshold(agent_blocked_streak, 5).   % Agent blocked 5 times in a row

should_alert(high_denial_rate) :-
    denials_last_hour(Count),
    alert_threshold(denials_per_hour, Threshold),
    Count > Threshold.

should_alert(rule_over_triggering, Rule) :-
    denials_last_hour_by_rule(Rule, Count),
    alert_threshold(same_rule_denials, Threshold),
    Count > Threshold.

% ----------------------------------------------------------------------------
% REPORTING FORMAT
% ----------------------------------------------------------------------------

% Nightly report format
report_format(markdown).
report_destination(telegram).  % Send to Manolo

% Report template
report_template("
# 🔍 Logician Daily Report - {{date}}

## Summary
- **Total Queries:** {{total_queries}}
- **Allowed:** {{allowed}} ({{allow_rate}}%)
- **Denied:** {{denied}} ({{deny_rate}}%)

## ❌ Denials by Rule
{{#denials_by_rule}}
- `{{rule}}`: {{count}} denials
{{/denials_by_rule}}

## ✅ Approvals to Review (Suspicious)
{{#suspicious_approvals}}
- ⚠️ `{{action}}` by {{agent}} — {{reason}}
{{/suspicious_approvals}}

## 👥 Activity by Agent
{{#activity_by_agent}}
- **{{agent}}**: {{allowed}} allowed, {{denied}} denied
{{/activity_by_agent}}

## 🚨 Flagged for Review (Added to TODO)
### Critical/High (Immediate)
{{#critical_flags}}
- 🔴 {{description}} — added to TODO
{{/critical_flags}}

### Medium (This Week)  
{{#medium_flags}}
- 🟡 {{description}}
{{/medium_flags}}

## 📈 Recommendations
{{#recommendations}}
- {{text}}
{{/recommendations}}

---
*Review queue: {{pending_reviews}} items pending*
").

% ----------------------------------------------------------------------------
% LEARNING FROM AUDIT
% ----------------------------------------------------------------------------

% Track rules that might need adjustment
rule_needs_review(Rule) :-
    false_positive_rate(Rule, Rate),
    Rate > 0.1.  % >10% false positives

rule_needs_review(Rule) :-
    denial_rate(Rule, Rate),
    Rate > 0.5.  % >50% of queries denied

% Suggest rule relaxation
suggest_relaxation(Rule) :-
    rule_needs_review(Rule),
    \+ is_locked_rule(Rule).

% Never suggest relaxing locked rules
is_locked_rule(crypto_rules).
is_locked_rule(security_rules/injection_pattern).
is_locked_rule(security_rules/forbidden_output).
