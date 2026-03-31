[AI-OPTIMIZED] ~280 tokens | src: SSOT-L1-BIDIRECTIONAL-CONTRACT-TRUST.md | Updated: 2026-03-10

| Field | Value |
|-------|-------|
| ID | SSOT-L1-BIDIRECTIONAL-CONTRACT-TRUST-V1 |
| Level | L1 | Status | Active | Created | 2026-02-22 |
| Stale After | Never (core security) |
| Related | SSOT-L1-SYMBIOTIC-WALLET, SSOT-L2-WALLET-DAO, SSOT-L2-TOKEN-ECONOMY-PHASE1 |

## Problem
Existing `verify_dao_member()` checks user → contract. Nothing checks contract → user. Attack: scammer deploys contract checking same Identity NFT collection. User wallet can't distinguish real DAO contract from copycat.

## Solution: Mutual Authentication
| Direction | Check | How |
|-----------|-------|-----|
| Inbound (contract checks user) | Identity NFT + membership stack | Existing `verify_dao_member()` |
| Outbound (user/client checks contract) | Contract PDA holds Program Identity NFT | New: client verifies before signing |

## Program Identity NFT
- **Type:** Token-2022, non-transferable (soulbound)
- **Minted to:** Program's PDA (derived from program ID, not human wallet)
- **Collection:** "DAO Verified Programs" dedicated collection
- **Mint authority:** Governance-controlled (see graduation below)
- **Root of trust:** Collection mint address (hardcoded in client — name/symbol/image are spoofable, address is not)

```
ROOT_OF_TRUST = "DAO_VERIFIED_PROGRAMS_COLLECTION_MINT_ADDRESS"
fn is_verified_program(program_id) -> bool:
    pda = derive_pda(program_id)
    nft = find_nft_on_account(pda)
    return nft.collection == ROOT_OF_TRUST && nft.exists
```

## Verification Flow
1. Client resolves target program PDA → checks NFT from ROOT_OF_TRUST collection
2. ✅ Verified (green) → proceed | ⚠️ Unverified (yellow) → warn, not block | 🚫 Revoked (red) → burned NFT
3. User proceeds → transaction built → contract runs `verify_dao_member()` on user
4. Both verified → execute

**Advisory, not blocking** — mirrors HTTPS cert warnings. User sovereignty non-negotiable.

## Mint Authority Graduation
| Phase | Authority | When |
|-------|-----------|------|
| Phase 1 | Founder (Manolo) | Day 1 |
| Phase 2 | 3-of-5 multisig | 5+ active contributors |
| Phase 3 | DAO governance proposal | DAO operational |
Transfer path built-in from day 1. Revocation = burn NFT.

## Implementation
**Phase 1 (ship first):** Client-side verification only. JS: `getNftsForAccount(pda).some(n => n.collection?.address === DAO_VERIFIED_COLLECTION)`.
**Phase 2 (future):** On-chain Gateway router. CPI overhead ~5,000-10,000 CU/tx. Deploy when 10+ verified programs justify overhead.

## Open Questions
1. Token-2022 mintable to PDAs? (needs DevNet test)
2. Metaplex `verified` creators field as alternative?
3. Cross-DAO trust model?
4. CU benchmark for Gateway verification

## Anti-Patterns
Block unverified contracts | Use metadata for verification | Upgradeable gateway with single key | Skip graduation path | Mint to human wallets
