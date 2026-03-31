user(/user1).
user_role(/user1, /admin).

agent(/strategist).
agent(/coder).
agent(/designer).
agent(/researcher).

allowlist(/strategist, /coder).
allowlist(/strategist, /designer).
allowlist(/strategist, /researcher).

action_type(/send_email, /external).
action_type(/delete_file, /destructive).

dangerous(/delete_file).
dangerous(/transfer_funds).

can_spawn(Agent, Target) :-
    agent(Agent),
    agent(Target),
    allowlist(Agent, Target).

requires_verification(Action) :-
    action_type(Action, /external).

requires_verification(Action) :-
    action_type(Action, /destructive).

is_admin(User) :-
    user(User),
    user_role(User, /admin).
