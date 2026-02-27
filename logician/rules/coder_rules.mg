% ============================================================================
% CODER RULES - Code Quality & Testing Requirements
% ResonantOS Logician - Enforced coding standards
% ============================================================================

% ----------------------------------------------------------------------------
% MANDATORY TESTING - Code Must Be Verified Working
% ----------------------------------------------------------------------------

% RULE: Coder must TEST code before marking task complete
% Testing = seeing it work, NOT reading the code

must_test_before_complete(coder).

% What counts as a valid test (deterministic verification)
valid_test(web_page, Actions) :-
    member(load_page, Actions),
    member(verify_renders, Actions).

valid_test(web_functionality, Actions) :-
    member(open_browser, Actions),
    member(interact_with_element, Actions),
    member(verify_output, Actions).

valid_test(api_endpoint, Actions) :-
    member(call_endpoint, Actions),
    member(verify_response, Actions).

valid_test(script, Actions) :-
    member(execute_script, Actions),
    member(verify_output, Actions).

valid_test(ui_component, Actions) :-
    member(render_component, Actions),
    member(visual_verify, Actions).

% What does NOT count as testing
invalid_test(read_code).
invalid_test(assume_works).
invalid_test(looks_correct).
invalid_test(should_work).
invalid_test(syntax_check_only).

% ----------------------------------------------------------------------------
% TEST METHODS BY CODE TYPE
% ----------------------------------------------------------------------------

% Web pages - must actually load in browser
required_test_method(html_file, browser_load).
required_test_method(css_file, browser_render).
required_test_method(web_page, browser_snapshot).

% Interactive features - must use browser automation
required_test_method(button, browser_click).
required_test_method(form, browser_fill_submit).
required_test_method(navigation, browser_navigate).
required_test_method(modal, browser_trigger_verify).
required_test_method(toggle, browser_click_verify_state).

% APIs - must call and verify response
required_test_method(api_endpoint, http_request_verify).
required_test_method(rest_api, curl_or_fetch).
required_test_method(websocket, connect_verify).

% Scripts - must execute and check output
required_test_method(python_script, python_execute).
required_test_method(shell_script, bash_execute).
required_test_method(node_script, node_execute).

% Backend - must verify behavior
required_test_method(server, start_and_health_check).
required_test_method(database_query, execute_verify_result).
required_test_method(cron_job, trigger_verify).

% ----------------------------------------------------------------------------
% BROWSER TESTING PROTOCOL
% ----------------------------------------------------------------------------

% For any UI work, coder must use browser tool
browser_test_required(Task) :- 
    task_involves(Task, html).
browser_test_required(Task) :- 
    task_involves(Task, css).
browser_test_required(Task) :- 
    task_involves(Task, javascript).
browser_test_required(Task) :- 
    task_involves(Task, ui).
browser_test_required(Task) :- 
    task_involves(Task, frontend).
browser_test_required(Task) :- 
    task_involves(Task, web).
browser_test_required(Task) :- 
    task_involves(Task, dashboard).

% Browser test steps
browser_test_steps([
    open_browser,           % Use browser tool
    navigate_to_page,       % Load the URL
    take_snapshot,          % Capture current state
    verify_elements_exist,  % Check expected elements
    test_interactions,      % Click, type, etc.
    verify_outcomes         % Check results
]).

% ----------------------------------------------------------------------------
% COMPLETION CRITERIA
% ----------------------------------------------------------------------------

% Task is NOT complete until tested
task_complete(coder, Task) :-
    code_written(coder, Task),
    test_performed(coder, Task, TestType),
    valid_test(TestType, _),
    test_passed(coder, Task).

% VIOLATION: Claiming done without testing
violation(coder, untested_code) :-
    claimed_complete(coder, Task),
    \+ test_performed(coder, Task, _).

% VIOLATION: Invalid test method
violation(coder, invalid_test_method) :-
    test_performed(coder, Task, Method),
    invalid_test(Method).

% VIOLATION: Not using browser for UI work
violation(coder, skipped_browser_test) :-
    browser_test_required(Task),
    completed(coder, Task),
    \+ used_browser_tool(coder, Task).

% ----------------------------------------------------------------------------
% TEST EVIDENCE REQUIREMENTS
% ----------------------------------------------------------------------------

% Coder must provide evidence of testing
required_evidence(web_page, screenshot).
required_evidence(web_page, snapshot_output).
required_evidence(api_endpoint, response_body).
required_evidence(script, execution_output).
required_evidence(ui_interaction, before_after_state).

% What to include in completion report
completion_report_must_include([
    what_was_built,
    how_it_was_tested,
    test_evidence,
    any_issues_found
]).

% ----------------------------------------------------------------------------
% DEFINITION OF "DONE" - Must Include Runtime Verification
% ----------------------------------------------------------------------------

% "Done" does NOT mean:
not_done(code_written).           % Writing code is not done
not_done(code_looks_correct).     % Looking at code is not done
not_done(code_reviewed).          % Reading code is not done
not_done(no_syntax_errors).       % Syntax check is not done
not_done(code_committed).         % Committing is not done

% "Done" MEANS:
definition_of_done([
    code_executed,                % Code was actually RUN
    output_observed,              % AI SAW the output (not imagined)
    output_matches_expected,      % Output is what was requested
    ui_verified_if_applicable    % If UI involved, visually confirmed
]).

% The test must be DETERMINISTIC and OBSERVABLE
valid_done_evidence(terminal_output).      % Saw command output
valid_done_evidence(browser_screenshot).   % Saw rendered page
valid_done_evidence(browser_snapshot).     % Saw DOM state
valid_done_evidence(api_response).         % Saw HTTP response
valid_done_evidence(file_created).         % Verified file exists
valid_done_evidence(process_running).      % Verified server is up

% NOT valid evidence (mental/assumed)
invalid_done_evidence(code_analysis).      % "I looked at the code"
invalid_done_evidence(logical_reasoning).  % "It should work because..."
invalid_done_evidence(assumption).         % "This will work"
invalid_done_evidence(pattern_matching).   % "I've seen similar code work"

% ----------------------------------------------------------------------------
% ENFORCEMENT: What Coder Must Do Before Saying "Done"
% ----------------------------------------------------------------------------

% For ANY code change, before reporting complete:
before_done(coder, web_code, [
    start_server_if_needed,
    open_browser,
    navigate_to_page,
    visually_confirm_renders,
    test_changed_functionality,
    observe_expected_behavior
]).

before_done(coder, api_code, [
    start_server_if_needed,
    make_http_request,
    observe_response,
    confirm_expected_data
]).

before_done(coder, script, [
    execute_script,
    observe_output,
    confirm_expected_result
]).

before_done(coder, ui_feature, [
    open_browser,
    navigate_to_feature,
    interact_with_feature,     % Click button, fill form, etc.
    observe_result,            % See what happens
    confirm_expected_behavior
]).

% If coder says "done" without these steps = VIOLATION
violation(coder, false_completion) :-
    reported_done(coder, Task),
    task_type(Task, Type),
    before_done(coder, Type, Steps),
    \+ all_steps_completed(coder, Task, Steps).

% ----------------------------------------------------------------------------
% TESTING SHORTCUTS (When full browser test not needed)
% ----------------------------------------------------------------------------

% Quick syntax/import check is OK for:
quick_check_sufficient(config_file_change).
quick_check_sufficient(comment_update).
quick_check_sufficient(variable_rename).
quick_check_sufficient(import_add).

% But still need to verify no breakage
quick_check_steps([
    syntax_check,
    import_check,
    server_still_runs
]).

% ----------------------------------------------------------------------------
% ERROR HANDLING
% ----------------------------------------------------------------------------

% If test fails, coder must:
on_test_failure(coder, Task, [
    identify_error,
    fix_code,
    retest,
    repeat_until_pass
]).

% Don't report failure without attempt to fix
violation(coder, gave_up_without_fixing) :-
    test_failed(coder, Task),
    reported_complete(coder, Task, failed),
    \+ attempted_fix(coder, Task).

% Max retries before escalating
max_fix_attempts(3).

should_escalate(coder, Task) :-
    fix_attempts(coder, Task, N),
    max_fix_attempts(Max),
    N >= Max.
