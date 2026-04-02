# Bidirectional Contract Trust — Architecture
Updated: 2026-03-15

| Field | Value |
|-------|-------|
| ID | SSOT-L1-BIDIRECTIONAL-CONTRACT-TRUST-V1 |
| Level | L1 (Architecture — Truth) |
| Created | 2026-02-22 |
| Status | Active |
| Stale After | Never (core security architecture) |
| Related | SSOT-L1-SYMBIOTIC-WALLET.md, SSOT-L2-WALLET-DAO.md, SSOT-L2-TOKEN-ECONOMY-PHASE1.md |

---

## The Problem

Current model: the DAO smart contract checks whether the **user** is legitimate (Identity NFT + membership stack). But nothing checks whether the **contract** is legitimate.

**Attack vector:** A scammer deploys a contract that checks the same Identity NFT collection. It looks like a DAO operation. The user's wallet can't distinguish between the real DAO contract and a copycat. Funds, approvals, or signatures go to the wrong place.

**Analogy:** Checking only the user's ID is like a bank that verifies your identity but lets anyone set up a teller window. You need both: you prove who you are, and the bank proves it's the real bank.

## The Solution: Mutual Authentication

Both parties prove identity before any interaction:

| Direction | What's Checked | How |
|-----------|---------------|-----|
| **Inbound** (contract checks user) | User holds Identity NFT + membership stack | Existing `verify_dao_member()` — already implemented |
| **Outbound** (user/client checks contract) | Contract's PDA holds a Program Identity NFT | New: client verifies before signing |

### Program Identity NFT

A new soulbound NFT collection. Minted to a program's PDA (not a human wallet). Proves a smart contract is DAO-approved.

| Property | Value |
|----------|-------|
| Type | Token-2022, non-transferable |
| Minted to | Program's PDA (derived from program ID) |
| Collection | Dedicated "DAO Verified Programs" collection |
| Mint authority | Governance-controlled (see Graduation Path) |
| Metadata | Program name, version, audit status, approval date |

### Root of Trust

**The collection mint address is the root of trust.** Not the NFT name, not the metadata, not the symbol — the address.

- Client hardcodes the canonical collection mint address
- Verification: check the NFT's collection field matches the hardcoded address
- Metadata (name, symbol, image) can be spoofed by copycat collections
- The mint authority address **cannot** be spoofed

```
ROOT_OF_TRUST = "DAO_VERIFIED_PROGRAMS_COLLECTION_MINT_ADDRESS"

fn is_verified_program(program_id) -> bool:
    pda = derive_pda(program_id)
    nft = find_nft_on_account(pda)
    return nft.collection == ROOT_OF_TRUST && nft.exists
```

## Architecture

### Trust Model

```
┌─────────────────┐          ┌─────────────────────┐
│   User Wallet   │          │   DAO Smart Contract │
│                 │          │                      │
│ Holds:          │◄────────►│ PDA Holds:           │
│ - Identity NFT  │  Mutual  │ - Program Identity   │
│ - License NFT   │  Trust   │   NFT                │
│ - Manifesto NFT │          │                      │
│ - $RCT > 0      │          │ Verified by:         │
│                 │          │ - Collection address  │
│ Verified by:    │          │   (hardcoded in       │
│ - Contract's    │          │    client)            │
│   verify_dao_   │          │                      │
│   member()      │          │                      │
└─────────────────┘          └─────────────────────┘
```

### Verification Flow

```
1. User opens client → selects DAO operation
2. Client resolves target program's PDA
3. Client checks: does PDA hold NFT from ROOT_OF_TRUST collection?
   ├─ YES → Green badge: "Verified DAO Contract" → proceed
   └─ NO  → Warning: "Unverified contract — not part of the DAO.
             Possible scam. Proceed at your own risk?"
             └─ User decides (not blocked)
4. If user proceeds → transaction built
5. Contract executes verify_dao_member() on user's wallet
6. Both sides verified → operation executes
```

### Critical Design Decision: Advisory, Not Blocking

The system **warns** the user about unverified contracts. It does **not prevent** interaction.

**Rationale:**
- The Identity NFT belongs to the user, not the ecosystem
- Users must remain free to interact with any Solana program
- Blocking creates a walled garden — contradicts Augmentatism
- Advisory model mirrors HTTPS: browsers warn about self-signed certs but don't block access
- User sovereignty is non-negotiable

**What each trust level means:**

| Trust Level | Badge | Meaning |
|-------------|-------|---------|
| ✅ Verified | Green shield | Contract holds Program Identity NFT from canonical collection |
| ⚠️ Unverified | Yellow warning | No Program Identity NFT found — could be legitimate new contract or scam |
| 🚫 Revoked | Red alert | Program Identity NFT was burned (contract was compromised or deprecated) |

## Governance: Mint Authority Graduation

Who mints Program Identity NFTs evolves over time:

| Phase | Authority | When |
|-------|-----------|------|
| Phase 1 (Bootstrap) | Founder (Manolo) | Day 1 — first contracts deployed |
| Phase 2 (Multisig) | 3-of-5 core contributors | When 5+ active contributors exist |
| Phase 3 (DAO) | Governance proposal + vote | When DAO governance is operational |

**Key requirement:** The mint authority must be **transferable** from day 1. The smart contract supports transfer to a multisig PDA and later to a governance PDA. This is not optional — it's built into the initial deployment.

### Minting Process

1. Contract is deployed to Solana
2. Contract undergoes review (code audit, purpose validation)
3. Mint authority approves → Program Identity NFT minted to contract's PDA
4. Client registry updated (optional: can also be fully on-chain)

### Revocation

If a contract is compromised or deprecated:
1. Governance decision (multisig or vote)
2. Program Identity NFT is **burned** (not transferred)
3. Client shows 🚫 Revoked badge for that program
4. Existing transactions are unaffected (already settled on-chain)

## Implementation Architecture: Two Phases

### Phase 1: Client-Only Verification (Ship First)

- Client maintains a list of known program IDs + their PDA NFT status
- Checks are done client-side before building transactions
- Simpler, faster to ship, no on-chain changes needed beyond the NFT collection
- Weakness: if a user uses a different client, no protection

```
// Client-side (JavaScript)
async function verifyProgram(programId) {
    const pda = derivePda(programId);
    const nfts = await getNftsForAccount(pda);
    const verified = nfts.some(n =>
        n.collection?.address === DAO_VERIFIED_COLLECTION
    );
    return { verified, programId, pda };
}
```

### Phase 2: On-Chain Gateway (Optional, Future)

A router program that enforces verification on-chain:

- All DAO interactions go through the Gateway
- Gateway checks both user membership AND target program's NFT
- Then CPI (cross-program invoke) into the target
- Stronger guarantee: works regardless of client

| Tradeoff | Client-Only | On-Chain Gateway |
|----------|-------------|-----------------|
| Security | Client-dependent | Chain-enforced |
| Complexity | Low | Medium |
| CPI overhead | None | ~5,000-10,000 CU per tx |
| Composability | Full | Requires CPI through Gateway |
| Deployment | Immediate | Requires new Anchor program |
| Upgradability | N/A | Deploy immutable or with governance upgrade authority |

**Recommendation:** Ship Phase 1 now. Design Phase 2 in parallel. Deploy Gateway when the DAO has 10+ verified programs and the attack surface justifies the overhead.

## Relationship to Existing Architecture

### Symbiotic Wallet (L1)

The existing `verify_dao_member()` handles the **inbound** check (user → contract). This document adds the **outbound** check (contract → user). They are complementary:

```
EXISTING:  Contract checks user  → verify_dao_member(wallet)
NEW:       Client checks contract → verify_program(program_id)
TOGETHER:  Bidirectional trust    → mutual authentication
```

### Identity NFT

The user's Identity NFT is **not** modified. It remains soulbound, non-transferable, and proves DAO membership. It is never restricted or gated by this system — the user can still interact with any Solana program freely.

### Token Economy

Program Identity NFTs are a new collection, separate from user NFTs. They do not carry $RCT, $RES, or any token balance. They are pure identity credentials for programs.

## Open Questions

1. **Token-2022 on PDAs:** Can non-transferable Token-2022 tokens be minted to program-derived PDAs? Needs empirical testing on DevNet.
2. **Verified Creators field:** Solana's Metaplex standard has a `verified` flag on creators. Could this be used instead of a full NFT? Simpler but less flexible.
3. **Cross-DAO trust:** If another DAO adopts this pattern, how do we handle cross-DAO program verification? Shared registry? Federated trust?
4. **CPI compute cost:** Benchmark the actual CU overhead of Gateway verification with real Token-2022 account reads.

## Anti-Patterns (Do NOT Do)

| Anti-Pattern | Why |
|-------------|-----|
| Block users from unverified contracts | Violates user sovereignty. Advisory only. |
| Use metadata (name/symbol) for verification | Spoofable. Only the collection address is reliable. |
| Make Gateway upgradeable by a single key | Single point of compromise. Use multisig or immutable. |
| Skip graduation path | Day-1 centralization must have a clear path to decentralization. |
| Mint Program NFTs to human wallets | They belong on program PDAs. Different purpose, different collection. |

## Files

- This document: `ssot/L1/SSOT-L1-BIDIRECTIONAL-CONTRACT-TRUST.md`
- Related: `ssot/L1/SSOT-L1-SYMBIOTIC-WALLET.md`
- Implementation: TBD (Anchor program for NFT collection + client verification library)

## Change Log

| Date | Change |
|------|--------|
| 2026-02-22 | V1 created from self-debate analysis. Advisory model chosen over blocking. Two-phase implementation (client-first, gateway later). Graduation path defined. |
