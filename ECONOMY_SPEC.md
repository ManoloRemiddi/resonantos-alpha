# ResonantOS Economy Specification

**Last Updated:** 2026-02-03 07:57
**Status:** Active Design Discussion
**Based on:** Anthill DAO model + ResonantOS requirements

---

## Overview

The ResonantOS economy is a DAO-based system where:
- All payments are crypto (no Stripe)
- DAO treasury gets a cut of all transactions
- Reputation determines access and voting power
- Skills are NFT-gated (free or premium)

---

## Core Components

### 1. AI Identity NFT
- **One per ResonantOS installation**
- Represents the multi-agent AI identity
- Required for all economic actions (rating, submitting, etc.)

**Wallet & NFT Creation Flow:**
1. User downloads ResonantOS (no NFT yet)
2. When NFT is needed → AI creates its own Solana wallet
3. AI gives **recovery phrase** to user
4. User saves recovery phrase + imports into **Phantom wallet**
5. User and AI now share the **same wallet** (user can monitor/fund, AI transacts)
6. User buys SOL via Phantom (Apple Pay, card, PayPal) — even $1-2 is enough
7. AI uses funds for gas (NFT minting, transactions)

**Recovery:** Standard crypto wallet recovery via phrase — user controls access

**Gas Strategy:**
- We *may* cover initial NFT minting gas (onboarding friendliness)
- But we encourage users to fund AI wallet for independence
- Benefit: AI has autonomy, we save on gas costs

### 2. Contribution Token: $REP
**Name:** `$REP` ✓ (confirmed)

**Properties:**
- Soulbound (non-transferable)
- Locked to NFT identity holder
- Cannot be swept/transferred

### 3. Reputation System
Based on Anthill's 8-category model:

| Category | How to Earn | Weight |
|----------|-------------|--------|
| 🎮 **Arena** | Win/participate in battles (Win: 10pts, Lose: 2pts) | 20% |
| 💻 **Code** | Submit approved skills | 20% |
| 🗳️ **Governance** | Vote on proposals, submit ideas | 15% |
| 🤝 **Community** | Help others, mentoring *(future — TBD mechanics)* | 15% |
| 💰 **Treasury** | Donate to DAO, bounty participation | 10% |
| ⭐ **Experience** | Smart contract interactions (any type) | 8% |
| 🏆 **Achievement** | Complete specific tasks → earn NFT badges (locked to account) | 7% |
| 📈 **Financial** | Stake, LP, buy/sell with DAO members | 5% |

**Total Reputation = Weighted sum of all categories**

> ⚠️ **Anti-Plutocracy Design:** Financial contribution is intentionally weighted LOW (5%) to prevent wealth = power. UCI and voting power come from contribution, not money. (Per Anthill philosophy)

### S-Curve Progression (Anti-Capture Security)

Reputation gains follow an **S-curve per level**:

```
Rep Gain
    │          ╭───────╮
    │        ╱           ╲
    │      ╱               ╲
    │    ╱                   ╲
    │──╱                       ╲──
    └────────────────────────────── Progress
     Slow    Accelerated    Slow
     Start   Middle         End
```

**Why S-curve:**
- **Early grind:** Hard to gain initial rep (prevents spam accounts)
- **Middle acceleration:** Rewards consistent contributors
- **Late plateau:** Diminishing returns at level cap (prevents runaway power)

**Level System:**
- Start with **10 levels**
- Each year, add new levels (expanding ceiling)
- Each level has its own S-curve internally
- Levels themselves follow an **exponential curve** (Level 8→9 is MUCH harder than Level 2→3)
- **Time is a security mechanism** - you can't sprint to capture the DAO

**Level Rewards (Mixed):**
Some actions scale with level, others are flat:

**Rep Earnings Scale with Level:**
Every smart contract interaction earns reputation tokens proportional to your level:
- Level 1 → base amount (e.g., 1 token)
- Level 10 → 10× base amount

*Some actions may be flat (same rep regardless of level) — defined case-by-case*

**Level Unlocks (Gated Access):**
| Level | Unlocks |
|-------|---------|
| 1 | Basic platform access |
| 3 | Can rate skills |
| 5 | Can submit skills for review, create/apply to bounties, receive UCI |
| 7 | Can vote on governance proposals |
| 10 | Can propose DAO constitution changes |

*(Thresholds configurable by DAO)*

This prevents:
- Sybil attacks (creating many accounts)
- Whale capture (buying your way to power)
- Sprint attacks (rapid power accumulation)

**Reputation Decay (Inactivity):**
- **Grace period:** 6 months of no smart contract activity
- **Decay pattern:** Exponential — slow at first, then accelerates
- **Full reset:** ~2 years of inactivity → back to Level 0
- Incentivizes ongoing participation — can't just earn and disappear

**Malicious Skill Handling:**

*Immediate:* Freeze skill, remove from store

*Investigation:* Determine if bug or intentional malice

*If bug (unintentional):* No penalty — fix and potentially restore

*If malicious intent:*
- Massive reputation loss (~50%)
- Voting power suspended (extended period)
- Additional penalties TBD

> Principle: Don't punish bugs, punish malice.

### 4. Payment System
**Crypto Only** (DAO treasury gets cut)

**Accepted Tokens:**
- **Solana (main):** SOL, USDT, USDC — all marketplace transactions
- ~~Ethereum~~ — NOT supported

**Bitcoin Support (Phased):**
1. **Launch:** SOL, USDT, USDC + Wrapped BTC (all on Solana)
2. **Coming Soon:** Native BTC on Bitcoin blockchain — only for 100% Treasury donations

**DAO Treasury Cut:** Finances free gas for smart contracts

**Treasury Governance:**
- Controlled by **custodians** using a **multisig wallet**
- **Progressive decentralization:**
  - Initially: 1 custodian (founder)
  - Growth follows **prime numbers:** 1 → 3 → 5 → 7 → 11 → 13 → 17...
  - Custodians must have high contribution level
  - Future: Custodians elected by community vote
- Spending decisions require multisig approval

---

## Dashboard Tabs

### Tab 1: Skills Panel

**Filter Bar (Top):**
`ALL` | `Free` | `Premium` | `Coming Soon`

**Category Tags (Multi-select):**
`Essential` | `Arena` | `Productivity` | `Security` | `Creative` | `Integrations`

**Sort Dropdown:**
`Top Rated` | `Newest` | `Most Used`

**Skill Card Components:**
- Icon
- Name
- Toggle (on/off)
- Short description
- "Read More" button
- Star rating + vote count

**Skill Detail Popup:**
- Full description
- Rating display (stars + votes)
- Rate button (if eligible)
- Installation status
- Version info

### Tab 2: Reputation & Leaderboard

**User's Profile Section:**
- Overall reputation bar
- Sub-reputation bars for each category:
  - Arena rep
  - Governance rep
  - Code contribution rep
  - Financial contribution rep
  - Community support rep
  - Experience rep
  - Achievement rep
  - Treasury rep

**Leaderboards (Multiple):**
- 🏆 **Global** - Overall reputation ranking
- 🎮 **Arena** - Competition champions
- 🗳️ **Governance** - Most active voters/proposers
- 💻 **Code** - Top skill contributors
- 💰 **Financial** - Donations + spending + earnings on DAO
- 🤝 **Community** - Helpers and mentors

Gamified presentation - make users want to climb!

**"How to Earn" Section:**
- Guide linking to earning opportunities
- Current bounties/work proposals
- Active challenges

---

## Skill Tiers

### Tier 1: Open Source
- Fully visible code
- Free to use
- NOT NFT-gated

### Tier 2: NFT-Gated (Free)
- Code visible
- Requires NFT to activate
- Free but gated for identity/tracking

### Tier 3: NFT-Gated Premium (Zero Knowledge)
- Code NOT visible (Lit Protocol encryption)
- Requires NFT + payment
- Protected IP

---

## Premium Skill Lifecycle

**Price Changes:**
- **Increase:** Max +10% per month (cooldown prevents price gouging)
- **Decrease:** Anytime, even to free (sales/promotions allowed)

**Refund Policy (Creator-Defined):**
- Payment held in **smart contract** (escrow)
- **Trial period:** 24-48 hours (creator sets duration)
- If buyer unhappy within trial → refund + skill deactivated from account
- Creator decides specific refund terms

**Skill Ownership = NFT:**
- Owning a premium skill = owning its NFT
- Code is zero-knowledge/obscured (Lit Protocol) — not visible to owner

**Skill Updates:** TBD
- Options being considered: first N updates free, creator decides, or always free

**Secondary Market:**
- Skills (NFTs) can be **resold** to other users
- Creates second-hand marketplace for skills
- Use cases: trial passed + don't want it, no longer need after months of use
- Adds liquidity and reduces buyer risk

**Secondary Sale Split:**
DAO takes 10% first, then remaining 90% split:

| Recipient | Calculation | Total % |
|-----------|-------------|---------|
| DAO Treasury | 10% first cut | 10% |
| Seller (reseller) | 80% of remaining | 72% |
| Original Creator | 20% of remaining | 18% |

*(Creator earns perpetual royalty on every resale via smart contract)*

---

## Skill Marketplace Fees

When a user purchases a premium skill:

| Recipient | % | Notes |
|-----------|---|-------|
| **Creator** | 90% | Default share (can be less if creator donates more to DAO) |
| **DAO Treasury** | 10% | Minimum cut, editable upward only by creator |

**Gas Fees:**
- Paid separately by the **buyer** (not part of the split)
- Determined by Solana network
- Not controlled by ResonantOS

**Example:** User buys a 10 SOL skill
- Creator receives: 9 SOL
- DAO Treasury receives: 1 SOL
- Buyer pays: 10 SOL + network gas

---

## Smart Contract Actions

### Rating a Skill
**Requirements:**
- Must have AI Identity NFT
- Must have minimum reputation (TBD threshold)
- Must pay own gas

### Submitting a Skill
**Requirements:**
- Must have AI Identity NFT
- Must have minimum reputation (TBD threshold)
- Must pay own gas
- Must set DAO donation % (minimum 10%)
- DAO cut only editable upward

**On Approval:**
- Creator gains reputation (Code category)
- Creator receives contribution token airdrop

### Skill Approval Process

**Two-Stage Approval:**

**Stage 1: Community Voting (Recommendation)**
- Proposed skills appear in "Proposed Skills" tab (searchable)
- Only NFT holders can vote
- Voting = on-chain transaction (voter pays gas) — anti-spam mechanism
- **Duration set by submitter:**
  - Minimum: 1 week
  - Suggested: 1 month
  - Can be longer (2-3 months)
- Votes are **recommendations**, not auto-binding

**Stage 2: Vetting (Manual Review)**
- After voting period ends → skill goes to dev team
- Coders test, review, and verify the skill
- Once vetted + approved → goes live

> ⚠️ **Testing Phase:** Currently no automatic threshold. Manual approval based on community signal. Automatic thresholds will be introduced as the system matures.

---

## Bounties & Work Proposals

**Open market for work** — anyone can post, anyone can build.

**Eligibility:** Level 5+ required (both creating AND applying)
- Level 5 = baseline commitment (interactions, constitution accepted, participation)
- Not too hard to reach, but filters drive-by users

**Creating a Bounty:**
- **Funds locked** in smart contract (escrow) — guarantees payment
- DAO can also post community proposals (e.g., "Build a decentralized Spotify")

**How it works:**
1. Creator posts bounty + locks funds (with deadline)
2. **Open competition:** Multiple builders can work simultaneously
   - Number of applicants visible (helps decide if worth competing)
   - Goal: best/fastest solution wins
3. **Winner selected by bounty creator:**
   - DAO bounty → custodians select
   - User bounty → user selects
4. Payment held in **escrow for 2 weeks** (dispute period)
5. After 2 weeks → funds released to builder
6. Builders earn reputation (Code category)
7. **DAO earns minimum 10%** of resulting project revenue (perpetual royalty)

**Benefit:** Ecosystem grows, builders earn, DAO treasury grows.

---

## Universal Contribution Income (UCI)

**Activation:** Once DAO is profitable

**Eligibility:** Level 5+ only (no UCI below level 5)

**Distribution:** Based on leaderboard/ranking position
- Higher rep = larger UCI share
- "The more you contribute, the more you earn"
- Not strictly linear — exact formula TBD

**Frequency:** TBD (weekly? monthly?)

**Source:** DAO treasury profits

---

## Voting Power

**Model:** Contribution-weighted voting (from Anthill)
- Voting power = **contribution coefficient** (not financial stake)
- More contribution = more voting power
- Explicitly anti-plutocracy: wealth ≠ power
- Only contribution matters (not fame, connections, wealth)

---

## Arena Integration

**Existing:** `~/clawd/projects/resonant-economy/arena/`

**Reputation Rewards:**
- Winner: +10 reputation (Arena category)
- Loser: +2 reputation (Arena category)

**Needs:** Integration with reputation token smart contract

---

## Insufficient Reputation UX

When user lacks required reputation:
```
┌─────────────────────────────────────┐
│  ⚠️ Insufficient Reputation         │
│                                     │
│  You need [X] reputation for this   │
│  action.                            │
│                                     │
│  Current: [Y] | Required: [X]       │
│                                     │
│  [Learn How to Earn Reputation →]   │
└─────────────────────────────────────┘
```
Links to Reputation & Leaderboard tab.

---

## Open Questions

1. ~~Category weights~~ ✅ Weighted (anti-plutocracy: financial capped at 5%)
2. ~~UCI distribution~~ ✅ Yes, once profitable, based on leaderboard
3. ~~Voting power~~ ✅ Rep-weighted
4. ~~Token name~~ ✅ $REP
5. **Minimum reputation thresholds** - Start low, dynamic adjustment (learn by doing)
6. ~~Staking mechanism~~ → Phase 2 (connected to semi-stable token economy, like Anthill's ANTT)
7. ~~Bounty DAO cut~~ ✅ 10% of project revenue **forever** (perpetual royalty)

---

## Implementation Order

### Phase 1: Foundation
- [ ] Skills Panel tab (basic UI)
- [ ] Skill cards with filters
- [ ] Detail popup

### Phase 2: NFT Integration
- [ ] AI Identity NFT verification
- [ ] NFT-gating for skills

### Phase 3: Reputation
- [ ] Reputation smart contract
- [ ] Contribution token creation
- [ ] Reputation & Leaderboard tab

### Phase 4: Rating System
- [ ] On-chain rating
- [ ] Gas-paid transactions
- [ ] Minimum rep checks

### Phase 5: Skill Submission
- [ ] Submission form
- [ ] Community voting
- [ ] Approval workflow

### Phase 6: Arena Integration
- [ ] Connect Arena to reputation contract
- [ ] Winner/loser rep distribution

---

## Reference Documents

- Anthill DAO: `/tmp/anthill-documents/`
- Anthill Ranking System: `ranking-system.md`
- Anthill Token Economy: `token-economy.md`
- Anthill Governance: `governance.md`
- Lit Protocol POC: `~/clawd/projects/encrypted-skills/`
- Arena Prototype: `~/clawd/projects/resonant-economy/arena/`

---

## Change Log

| Date | Change |
|------|--------|
| 2026-02-03 07:57 | Initial spec created from discussion |
| 2026-02-03 08:03 | Added: Bounties/Work Proposals, UCI, rep-weighted voting, $REP confirmed, sub-leaderboards |
| 2026-02-03 08:09 | Added: Weighted categories (anti-plutocracy), 10% perpetual royalty on bounties, dynamic thresholds |
| 2026-02-03 09:02 | Added: S-curve progression per level, 10-level system expanding yearly, time as security mechanism |
| 2026-02-03 09:09 | Clarified: Levels are exponential curve (not linear), higher levels = higher rep multipliers, level-gated unlocks |
| 2026-02-03 16:23 | Added: Skill Marketplace Fees section (90/10 split, gas paid by buyer) |
