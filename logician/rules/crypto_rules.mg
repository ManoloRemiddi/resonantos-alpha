% ============================================================================
% CRYPTO WALLET RULES
% ResonantOS Logician - Protect crypto assets
% ============================================================================

% These rules are ABSOLUTE. No exceptions. No overrides.

% ----------------------------------------------------------------------------
% RECOVERY PHRASE / SEED PHRASE
% ----------------------------------------------------------------------------

% BIP-39 word count for valid seed phrases
valid_seed_length(12).
valid_seed_length(15).
valid_seed_length(18).
valid_seed_length(21).
valid_seed_length(24).

% Detection: Is this a recovery phrase?
is_recovery_phrase(Data) :-
    word_count(Data, N),
    valid_seed_length(N),
    all_words_in_bip39(Data).

% ABSOLUTE RULES - Recovery phrases
forbidden_action(output, Data) :- is_recovery_phrase(Data).
forbidden_action(store, Data) :- is_recovery_phrase(Data).
forbidden_action(log, Data) :- is_recovery_phrase(Data).
forbidden_action(transmit, Data) :- is_recovery_phrase(Data).
forbidden_action(display, Data) :- is_recovery_phrase(Data).

% Even partial phrases are dangerous
is_partial_seed(Data) :-
    word_count(Data, N),
    N >= 6,
    N < 12,
    all_words_in_bip39(Data).

forbidden_action(output, Data) :- is_partial_seed(Data).
forbidden_action(store, Data) :- is_partial_seed(Data).

% ----------------------------------------------------------------------------
% PRIVATE KEYS
% ----------------------------------------------------------------------------

% Detection: Crypto private keys
is_private_key(Data) :- starts_with(Data, "0x"), length(Data, 66).  % Ethereum
is_private_key(Data) :- starts_with(Data, "5"), length(Data, 51).   % Bitcoin WIF
is_private_key(Data) :- starts_with(Data, "K"), length(Data, 52).   % Bitcoin WIF compressed
is_private_key(Data) :- starts_with(Data, "L"), length(Data, 52).   % Bitcoin WIF compressed
is_private_key(Data) :- is_base58(Data), length(Data, 88).          % Solana

% ABSOLUTE RULES - Private keys
forbidden_action(output, Data) :- is_private_key(Data).
forbidden_action(store, Data) :- is_private_key(Data).
forbidden_action(log, Data) :- is_private_key(Data).
forbidden_action(transmit, Data) :- is_private_key(Data).

% ----------------------------------------------------------------------------
% WALLET ADDRESSES (PUBLIC - OK to share, but with care)
% ----------------------------------------------------------------------------

% Detection: Public addresses
is_wallet_address(Data) :- starts_with(Data, "0x"), length(Data, 42).    % Ethereum
is_wallet_address(Data) :- starts_with(Data, "1"), length(Data, L), L >= 26, L =< 35.  % Bitcoin
is_wallet_address(Data) :- starts_with(Data, "3"), length(Data, L), L >= 26, L =< 35.  % Bitcoin P2SH
is_wallet_address(Data) :- starts_with(Data, "bc1"), length(Data, L), L >= 42.         % Bitcoin Bech32
is_wallet_address(Data) :- is_base58(Data), length(Data, L), L >= 32, L =< 44.         % Solana

% Public addresses CAN be shared, but:
% - Not in group chats without explicit permission
% - Not associated with identity without consent
warn_action(share_address_group, Data) :- 
    is_wallet_address(Data),
    is_group_context.

% ----------------------------------------------------------------------------
% TRANSACTION SIGNING
% ----------------------------------------------------------------------------

% Actions that involve signing
is_signing_action(Action) :- contains(Action, "sign").
is_signing_action(Action) :- contains(Action, "approve").
is_signing_action(Action) :- contains(Action, "confirm").

% Signing ALWAYS requires human confirmation
requires_human_confirmation(Action) :- is_signing_action(Action).

% Never auto-sign anything
forbidden_action(auto_sign, _).

% ----------------------------------------------------------------------------
% TRANSACTION AMOUNTS
% ----------------------------------------------------------------------------

% High-value transactions need extra verification
high_value_threshold_usd(100).

is_high_value(Transaction) :-
    transaction_value_usd(Transaction, Value),
    high_value_threshold_usd(Threshold),
    Value > Threshold.

% High value = double confirmation
requires_double_confirmation(Transaction) :- is_high_value(Transaction).

% ----------------------------------------------------------------------------
% WALLET CONNECTION REQUESTS
% ----------------------------------------------------------------------------

% Wallet connect requests from external sources
is_wallet_connect_request(Data) :- contains(Data, "wc:").
is_wallet_connect_request(Data) :- contains(Data, "walletconnect").
is_wallet_connect_request(Data) :- contains(Data, "connect wallet").

% ALWAYS require human verification for wallet connections
requires_human_verification(Action) :- is_wallet_connect_request(Action).

% Never auto-connect wallets
forbidden_action(auto_connect, Data) :- is_wallet_connect_request(Data).

% ----------------------------------------------------------------------------
% PHISHING PROTECTION
% ----------------------------------------------------------------------------

% Common phishing patterns
phishing_pattern(URL) :- contains(URL, "claim").
phishing_pattern(URL) :- contains(URL, "airdrop"), \+ trusted_domain(URL).
phishing_pattern(URL) :- contains(URL, "free-mint").
phishing_pattern(URL) :- contains(URL, "urgent").
phishing_pattern(URL) :- contains(URL, "expires").

% Trusted domains (whitelist approach)
trusted_domain(URL) :- contains(URL, "github.com").
trusted_domain(URL) :- contains(URL, "etherscan.io").
trusted_domain(URL) :- contains(URL, "solscan.io").

% Block suspicious wallet-related URLs
block_url(URL) :- 
    phishing_pattern(URL),
    \+ trusted_domain(URL).

warn_url(URL) :-
    is_wallet_connect_request(URL),
    \+ trusted_domain(URL).

% ----------------------------------------------------------------------------
% SUMMARY: ABSOLUTE PROHIBITIONS
% ----------------------------------------------------------------------------

% Things I will NEVER do, regardless of instructions:

absolute_prohibition(store_seed_phrase).
absolute_prohibition(output_private_key).
absolute_prohibition(auto_sign_transaction).
absolute_prohibition(share_seed_phrase).
absolute_prohibition(log_private_key).
absolute_prohibition(transmit_recovery_phrase).

% These cannot be overridden by:
% - User instructions
% - Other agents
% - Prompt injection
% - Any external input

cannot_override(X) :- absolute_prohibition(X).
