# SSOT-L1-SYMBIOTIC-WALLET — Three-Wallet Architecture
Updated: {{GENERATED_DATE}}

## Purpose
The Symbiotic Wallet is a three-wallet Solana architecture that enables safe, governed AI-to-human and AI-to-AI transactions.

## Architecture

### Three Wallets
1. **Human Wallet** — Your personal Solana wallet (Phantom, Solflare, etc.)
2. **AI Wallet** — Agent's own keypair, non-custodial
3. **Symbiotic PDA** — Program-Derived Address (multi-sig between Human + AI)

### Transaction Flow
```
Human approves policy → AI proposes transaction → Symbiotic PDA executes if policy allows
```

## Configuration

### Network
- **Devnet:** {{WALLET_DEVNET_ENABLED}}
- **Mainnet:** {{WALLET_MAINNET_ENABLED}}

### Addresses
- **Human:** {{WALLET_HUMAN_ADDRESS}}
- **AI:** {{WALLET_AI_ADDRESS}}
- **Symbiotic PDA:** {{WALLET_SYMBIOTIC_PDA}}

### Program ID
{{WALLET_PROGRAM_ID}}

## Token Economy

### Governance Token: $RCT
- **Type:** Soulbound (non-transferable)
- **Purpose:** DAO voting rights
- **Balance:** {{WALLET_RCT_BALANCE}}

### Currency Token: $RES
- **Type:** Transferable
- **Purpose:** Payments, bounties, rewards
- **Balance:** {{WALLET_RES_BALANCE}}

### REX Sub-tokens
{{WALLET_REX_TOKENS}}

## Safety Caps
- **AI spending limit:** {{WALLET_AI_SPENDING_LIMIT}} per day
- **Transaction size limit:** {{WALLET_TRANSACTION_LIMIT}}
- **Approval required for:** {{WALLET_APPROVAL_THRESHOLD}}

## Integration Points
- **DAO:** Voting, bounties, tribe membership
- **Dashboard:** Wallet management UI on port 19100
- **CLI:** `wallet` command for balance/transfer/approve

## Setup Instructions

### 1. Generate AI Wallet
```bash
solana-keygen new -o ~/.openclaw/ai-wallet.json
```

### 2. Initialize Symbiotic PDA
```bash
anchor run initialize-symbiotic-wallet
```

### 3. Fund Wallets (Devnet)
```bash
solana airdrop 2 <AI_WALLET_ADDRESS> --url devnet
solana airdrop 2 <HUMAN_WALLET_ADDRESS> --url devnet
```

### 4. Verify
```bash
wallet balance --all
```

---

_This document describes your wallet configuration. Update as your setup evolves._
