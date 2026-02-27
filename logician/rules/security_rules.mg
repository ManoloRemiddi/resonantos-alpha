% ============================================================================
% SECURITY RULES - Symbiotic Shield Protocol
% ResonantOS Logician - Hard enforcement layer
% ============================================================================

% ----------------------------------------------------------------------------
% SENSITIVE DATA PATTERNS - Never expose these
% ----------------------------------------------------------------------------

% API Keys and Tokens
sensitive_pattern(api_key, "sk-*").
sensitive_pattern(api_key, "ANTHROPIC_API_KEY").
sensitive_pattern(api_key, "OPENAI_API_KEY").
sensitive_pattern(token, "ghp_*").          % GitHub personal token
sensitive_pattern(token, "gho_*").          % GitHub OAuth token
sensitive_pattern(token, "xoxb-*").         % Slack bot token
sensitive_pattern(token, "xoxp-*").         % Slack user token

% Crypto secrets
sensitive_pattern(private_key, "-----BEGIN.*PRIVATE KEY-----").
sensitive_pattern(recovery_phrase, X) :- is_bip39_phrase(X).
sensitive_pattern(seed, X) :- word_count(X, N), N >= 12, N =< 24, all_bip39_words(X).

% Credentials
sensitive_pattern(password, X) :- contains(X, "password").
sensitive_pattern(credential, X) :- contains(X, "secret").
sensitive_pattern(ssh_key, "-----BEGIN OPENSSH PRIVATE KEY-----").

% ----------------------------------------------------------------------------
% MEMORY & PRIVATE DATA — NEVER ON GITHUB (ABSOLUTE RULE)
% Memory logs, daily notes, MEMORY.md, personal context = identity.
% Not on ANY repo — public or private. Catastrophic if leaked.
% ----------------------------------------------------------------------------

% Memory file patterns
is_memory_content(Path) :- contains(Path, "MEMORY.md").
is_memory_content(Path) :- contains(Path, "memory/").
is_memory_content(Path) :- contains(Path, "USER.md").
is_memory_content(Path) :- contains(Path, "shared-log/").
is_memory_content(Path) :- contains(Path, "SESSION_THREAD").
is_memory_content(Path) :- contains(Path, "daily-notes").
is_memory_content(Path) :- contains(Path, "heartbeat-state").

% Git operations on memory files — ALWAYS BLOCKED
block_git_add(Path) :- is_memory_content(Path).
block_git_push(Repo, Path) :- is_memory_content(Path).
block_git_commit(Path) :- is_memory_content(Path).

% Repo separation: private repo never shared externally
is_private_repo("resonantos").
block_share_repo(Repo) :- is_private_repo(Repo).
block_external_reference(Repo) :- is_private_repo(Repo).

% Backup destinations — only encrypted local or non-code-hosting cloud
allowed_backup_dest(local_encrypted).
allowed_backup_dest(google_drive_encrypted).
blocked_backup_dest(github).
blocked_backup_dest(gitlab).
blocked_backup_dest(bitbucket).
block_backup(Dest, Data) :- blocked_backup_dest(Dest), is_memory_content(Data).

% ----------------------------------------------------------------------------
% OUTPUT RULES - What can never be sent externally
% ----------------------------------------------------------------------------

% Hard block: NEVER output these regardless of context
forbidden_output(Data) :- 
    sensitive_pattern(Type, Pattern),
    matches(Data, Pattern),
    member(Type, [api_key, token, private_key, recovery_phrase, seed, ssh_key]).

% Block in any channel
block_output(Channel, Data) :- forbidden_output(Data).

% ----------------------------------------------------------------------------
% MEMORY RULES - What can never be written to persistent storage
% ----------------------------------------------------------------------------

% Never write these to any memory file
forbidden_memory_write(Data) :- sensitive_pattern(recovery_phrase, Data).
forbidden_memory_write(Data) :- sensitive_pattern(seed, Data).
forbidden_memory_write(Data) :- sensitive_pattern(private_key, Data).
forbidden_memory_write(Data) :- sensitive_pattern(ssh_key, Data).
forbidden_memory_write(Data) :- sensitive_pattern(password, Data).
forbidden_memory_write(Data) :- sensitive_pattern(api_key, Data).

% Memory file paths
memory_file(Path) :- contains(Path, "MEMORY.md").
memory_file(Path) :- contains(Path, "memory/").
memory_file(Path) :- contains(Path, ".md"), contains(Path, "clawd").

% Block write action
block_write(Path, Data) :- 
    memory_file(Path), 
    forbidden_memory_write(Data).

% ----------------------------------------------------------------------------
% GROUP CHAT RULES - Extra restrictions in shared contexts
% ----------------------------------------------------------------------------

% PII patterns
pii_pattern(email, X) :- matches(X, "*@*.com").
pii_pattern(phone, X) :- matches(X, "+*").
pii_pattern(address, X) :- contains(X, "street"), contains(X, "city").

% Financial data
financial_pattern(X) :- contains(X, "bank account").
financial_pattern(X) :- contains(X, "credit card").
financial_pattern(X) :- contains(X, "IBAN").

% Forbidden in group contexts
forbidden_in_group(Data) :- pii_pattern(_, Data).
forbidden_in_group(Data) :- financial_pattern(Data).
forbidden_in_group(Data) :- sensitive_pattern(_, Data).

% Context detection
is_group_context(Channel) :- contains(Channel, "discord").
is_group_context(Channel) :- contains(Channel, "group").
is_group_context(Channel) :- contains(Channel, "channel").

% Block in groups
block_output(Channel, Data) :- 
    is_group_context(Channel), 
    forbidden_in_group(Data).

% ----------------------------------------------------------------------------
% EXTERNAL COMMUNICATION RULES
% ----------------------------------------------------------------------------

% Rate limiting for unknown agents
max_requests_per_minute(unknown_agent, 10).
max_requests_per_minute(known_agent, 100).

% Agent trust levels
trusted_agent(manolo).
trusted_agent(strategist).
trusted_agent(coder).
trusted_agent(designer).

% External request validation
allow_external_request(Agent, _) :- trusted_agent(Agent).
allow_external_request(Agent, Count) :- 
    \+ trusted_agent(Agent),
    max_requests_per_minute(unknown_agent, Max),
    Count < Max.

% URL validation (anti-typosquatting)
suspicious_url(URL) :- contains(URL, "githuh.com").
suspicious_url(URL) :- contains(URL, "goggle.com").
suspicious_url(URL) :- contains(URL, "antropic.com").

block_request(URL) :- suspicious_url(URL).

% ----------------------------------------------------------------------------
% RISK SCORING THRESHOLDS
% ----------------------------------------------------------------------------

% Risk levels
risk_action(Score, block) :- Score > 80.
risk_action(Score, warn) :- Score > 50, Score =< 80.
risk_action(Score, allow) :- Score =< 50.

% Automatic escalation
requires_human_approval(Action) :- risk_action(Score, block), Score > 80.
requires_human_approval(Action) :- is_destructive(Action).

% Destructive actions
is_destructive(Action) :- contains(Action, "rm -rf").
is_destructive(Action) :- contains(Action, "delete").
is_destructive(Action) :- contains(Action, "drop table").
is_destructive(Action) :- contains(Action, "format").

% ----------------------------------------------------------------------------
% INJECTION DETECTION
% ----------------------------------------------------------------------------

% Injection patterns to reject
injection_pattern("ignore previous instructions").
injection_pattern("ignore all instructions").
injection_pattern("you are now").
injection_pattern("new system prompt").
injection_pattern("disregard").
injection_pattern("forget everything").
injection_pattern("jailbreak").
injection_pattern("DAN mode").

% Block injected input
block_input(Data) :- 
    injection_pattern(Pattern),
    contains_ignore_case(Data, Pattern).

% Encoded payload detection
suspicious_encoding(Data) :- is_base64(Data), length(Data, L), L > 100.
suspicious_encoding(Data) :- is_hex(Data), length(Data, L), L > 50.

requires_decode_scan(Data) :- suspicious_encoding(Data).
