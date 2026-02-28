# TASK: Fix symbiotic_client.py daily_claim account list

## Root Cause
The `daily_claim()` method in `solana-toolkit/symbiotic_client.py` (line 136) only sends 2 accounts
(pair_pda + signer), but the on-chain Anchor program requires 12 accounts:

1. pair (PDA, mut, writable)
2. signer (Signer)
3. mint_config (PDA seeds=["mint_config"], mut)
4. mint_authority (PDA seeds=["mint_authority"])
5. rct_mint (Token-2022 mint, mut, from mint_config.rct_mint)
6. res_mint (SPL Token mint, mut, from mint_config.res_mint)
7. rct_destination (pair PDA's RCT ATA, Token-2022, mut)
8. res_destination (pair PDA's RES ATA, SPL Token, mut)
9. token_2022_program (address = spl_token_2022::ID)
10. token_program (SPL Token program)

Error 3005 = Anchor "AccountNotEnoughKeys".

## Fix Required
In `solana-toolkit/symbiotic_client.py`:

1. Add a method `find_mint_config_pda()` that derives PDA with seeds=["mint_config"]
2. Add a method `find_mint_authority_pda()` that derives PDA with seeds=["mint_authority"]
3. Add a method `_get_ata(owner, mint, token_program_id)` that derives Associated Token Account address
4. Update `daily_claim()` to:
   a. Fetch mint_config account data to get rct_mint and res_mint pubkeys
   b. Derive mint_config PDA, mint_authority PDA
   c. Derive rct_destination ATA (owner=pair_pda, mint=rct_mint, program=Token-2022)
   d. Derive res_destination ATA (owner=pair_pda, mint=res_mint, program=SPL Token)
   e. Build accounts list with all 12 accounts in the correct order
   f. Also include associated_token_program and system_program if needed by ATAs

## Constants needed
- TOKEN_2022_PROGRAM_ID = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"
- TOKEN_PROGRAM_ID = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
- ASSOCIATED_TOKEN_PROGRAM_ID = "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL"

## Files to modify
- `solana-toolkit/symbiotic_client.py` ONLY

## Test command
```
cd solana-toolkit && python3 -c "import ast; ast.parse(open('symbiotic_client.py').read()); print('OK')"
```

## Acceptance criteria
- daily_claim() builds the full 12-account instruction
- All PDAs derived correctly using Pubkey.find_program_address
- ATAs derived using standard SPL formula
- mint_config data parsed to extract rct_mint and res_mint pubkeys
- File parses without errors
