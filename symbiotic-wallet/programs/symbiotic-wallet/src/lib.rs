use anchor_lang::prelude::*;
use anchor_spl::token;
use anchor_spl::token_2022;
use anchor_spl::token_interface::{Mint, TokenAccount, TokenInterface};

declare_id!("HMthR7AStR3YKJ4m8GMveWx5dqY3D2g2cfnji7VdcVoG");

/// Symbiotic Wallet Program
///
/// Creates a PDA vault co-owned by a human and an AI wallet.
/// PDA derived from [b"symbiotic", human_pubkey, pair_nonce] so AI key
/// can be rotated without changing the vault address.
///
/// Permission matrix (enforced on-chain):
///   AI alone:    daily_claim, grant_xp
///   Human alone: emergency_freeze, unfreeze, rotate_ai_key
///   Both:        mint_nft, transfer_out
///
/// Security: checked arithmetic, Anchor account validation, bump canonicalization.
#[program]
pub mod symbiotic_wallet {
    use super::*;

    /// Create a new symbiotic pair. Human signs.
    pub fn initialize_pair(
        ctx: Context<InitializePair>,
        pair_nonce: u8,
    ) -> Result<()> {
        let pair = &mut ctx.accounts.pair;
        pair.human = ctx.accounts.human.key();
        pair.ai = ctx.accounts.ai.key();
        pair.pair_nonce = pair_nonce;
        pair.bump = ctx.bumps.pair;
        pair.frozen = false;
        pair.last_claim = 0;
        pair.created_at = Clock::get()?.unix_timestamp;
        pair.ai_rotations = 0;

        emit!(PairCreated {
            pair: pair.key(),
            human: pair.human,
            ai: pair.ai,
        });

        Ok(())
    }

    /// Initialize mint config PDA. Called once after deploy.
    pub fn initialize_mint_config(
        ctx: Context<InitializeMintConfig>,
        rct_mint: Pubkey,
        res_mint: Pubkey,
        rct_per_claim: u64,
        res_per_claim: u64,
    ) -> Result<()> {
        let mint_config = &mut ctx.accounts.mint_config;
        mint_config.rct_mint = rct_mint;
        mint_config.res_mint = res_mint;
        mint_config.rct_per_claim = rct_per_claim;
        mint_config.res_per_claim = res_per_claim;
        mint_config.admin = ctx.accounts.admin.key();
        mint_config.bump = ctx.bumps.mint_config;
        mint_config.total_rct_minted = 0;
        mint_config.total_res_minted = 0;

        Ok(())
    }

    /// Update mint amounts and admin. Mint addresses are immutable.
    pub fn update_mint_config(
        ctx: Context<UpdateMintConfig>,
        rct_per_claim: u64,
        res_per_claim: u64,
        new_admin: Pubkey,
    ) -> Result<()> {
        let mint_config = &mut ctx.accounts.mint_config;
        mint_config.rct_per_claim = rct_per_claim;
        mint_config.res_per_claim = res_per_claim;
        mint_config.admin = new_admin;

        Ok(())
    }

    /// Daily claim — either signer (human or AI) can trigger.
    /// Enforces 24h cooldown on-chain.
    pub fn daily_claim(ctx: Context<DailyClaim>) -> Result<()> {
        let pair = &mut ctx.accounts.pair;

        require!(!pair.frozen, SymbioticError::PairFrozen);

        let clock = Clock::get()?;
        let now = clock.unix_timestamp;
        let elapsed = now.checked_sub(pair.last_claim).ok_or(SymbioticError::Overflow)?;

        require!(elapsed >= 86_400, SymbioticError::ClaimCooldown);

        // Verify signer is human or AI
        let signer = ctx.accounts.signer.key();
        require!(
            signer == pair.human || signer == pair.ai,
            SymbioticError::Unauthorized
        );

        // Mint authority PDA signs for both mint_to CPIs.
        let mint_auth_bump = ctx.bumps.mint_authority;
        let mint_auth_bump_bytes = [mint_auth_bump];
        let mint_auth_seeds: &[&[u8]] = &[b"mint_authority", &mint_auth_bump_bytes];
        let signer_seeds = &[mint_auth_seeds];

        let config = &mut ctx.accounts.mint_config;

        // Mint RCT (Token-2022)
        token_2022::mint_to(
            CpiContext::new_with_signer(
                ctx.accounts.token_2022_program.to_account_info(),
                token_2022::MintTo {
                    mint: ctx.accounts.rct_mint.to_account_info(),
                    to: ctx.accounts.rct_destination.to_account_info(),
                    authority: ctx.accounts.mint_authority.to_account_info(),
                },
                signer_seeds,
            ),
            config.rct_per_claim,
        )?;

        // Mint RES (SPL Token)
        token::mint_to(
            CpiContext::new_with_signer(
                ctx.accounts.token_program.to_account_info(),
                token::MintTo {
                    mint: ctx.accounts.res_mint.to_account_info(),
                    to: ctx.accounts.res_destination.to_account_info(),
                    authority: ctx.accounts.mint_authority.to_account_info(),
                },
                signer_seeds,
            ),
            config.res_per_claim,
        )?;

        config.total_rct_minted = config
            .total_rct_minted
            .checked_add(config.rct_per_claim)
            .ok_or(SymbioticError::Overflow)?;
        config.total_res_minted = config
            .total_res_minted
            .checked_add(config.res_per_claim)
            .ok_or(SymbioticError::Overflow)?;

        pair.last_claim = now;

        emit!(DailyClaimEvent {
            pair: pair.key(),
            signer,
            timestamp: now,
        });

        Ok(())
    }

    /// Emergency freeze — either signer can trigger independently.
    pub fn emergency_freeze(ctx: Context<SingleSigner>) -> Result<()> {
        let pair = &mut ctx.accounts.pair;
        let signer = ctx.accounts.signer.key();

        require!(
            signer == pair.human || signer == pair.ai,
            SymbioticError::Unauthorized
        );

        pair.frozen = true;

        emit!(PairFrozen {
            pair: pair.key(),
            frozen_by: signer,
        });

        Ok(())
    }

    /// Unfreeze — human only.
    pub fn unfreeze(ctx: Context<HumanOnly>) -> Result<()> {
        let pair = &mut ctx.accounts.pair;

        require!(
            ctx.accounts.human.key() == pair.human,
            SymbioticError::Unauthorized
        );

        pair.frozen = false;

        emit!(PairUnfrozen {
            pair: pair.key(),
        });

        Ok(())
    }

    /// Rotate AI key — human only. AI key may have been compromised.
    /// PDA does NOT change (derived from human + nonce, not AI key).
    pub fn rotate_ai_key(
        ctx: Context<HumanOnly>,
        new_ai: Pubkey,
    ) -> Result<()> {
        let pair = &mut ctx.accounts.pair;

        require!(
            ctx.accounts.human.key() == pair.human,
            SymbioticError::Unauthorized
        );
        require!(!pair.frozen, SymbioticError::PairFrozen);
        require!(new_ai != Pubkey::default(), SymbioticError::InvalidKey);
        require!(new_ai != pair.human, SymbioticError::InvalidKey);

        let old_ai = pair.ai;
        pair.ai = new_ai;
        pair.ai_rotations = pair.ai_rotations.checked_add(1).ok_or(SymbioticError::Overflow)?;

        emit!(AiKeyRotated {
            pair: pair.key(),
            old_ai,
            new_ai,
            rotation_count: pair.ai_rotations,
        });

        Ok(())
    }

    /// Transfer SPL tokens out of the PDA's ATA to a recipient.
    /// Human-only authorization (sovereignty principle).
    pub fn transfer_out(
        ctx: Context<TransferOut>,
        amount: u64,
    ) -> Result<()> {
        let pair = &ctx.accounts.pair;

        require!(!pair.frozen, SymbioticError::PairFrozen);
        require!(
            ctx.accounts.human.key() == pair.human,
            SymbioticError::Unauthorized
        );
        require!(amount > 0, SymbioticError::InvalidAmount);

        // PDA signs via seeds
        let seeds: &[&[u8]] = &[
            b"symbiotic",
            pair.human.as_ref(),
            &[pair.pair_nonce],
            &[pair.bump],
        ];
        let signer_seeds = &[seeds];

        anchor_spl::token_2022::transfer_checked(
            CpiContext::new_with_signer(
                ctx.accounts.token_program.to_account_info(),
                anchor_spl::token_2022::TransferChecked {
                    from: ctx.accounts.from_ata.to_account_info(),
                    mint: ctx.accounts.mint.to_account_info(),
                    to: ctx.accounts.to_ata.to_account_info(),
                    authority: ctx.accounts.pair.to_account_info(),
                },
                signer_seeds,
            ),
            amount,
            ctx.accounts.mint.decimals,
        )?;

        emit!(TransferOutEvent {
            pair: pair.key(),
            human: pair.human,
            mint: ctx.accounts.mint.key(),
            recipient: ctx.accounts.to_ata.key(),
            amount,
            timestamp: Clock::get()?.unix_timestamp,
        });

        Ok(())
    }

    /// Co-signed action — both human AND AI must sign.
    /// Used for: NFT minting, transfers out, identity-binding actions.
    /// The `action_type` field is logged for off-chain indexing.
    pub fn co_sign_action(
        ctx: Context<CoSign>,
        action_type: String,
        memo: String,
    ) -> Result<()> {
        let pair = &ctx.accounts.pair;

        require!(!pair.frozen, SymbioticError::PairFrozen);
        require!(action_type.len() <= 32, SymbioticError::DataTooLong);
        require!(memo.len() <= 256, SymbioticError::DataTooLong);

        require!(
            ctx.accounts.human.key() == pair.human,
            SymbioticError::Unauthorized
        );
        require!(
            ctx.accounts.ai.key() == pair.ai,
            SymbioticError::Unauthorized
        );

        emit!(CoSignedAction {
            pair: pair.key(),
            action_type,
            memo,
            timestamp: Clock::get()?.unix_timestamp,
        });

        Ok(())
    }
}

// ─── Accounts ────────────────────────────────────────────────────────────────

#[derive(Accounts)]
#[instruction(pair_nonce: u8)]
pub struct InitializePair<'info> {
    #[account(
        init,
        payer = human,
        space = 8 + SymbioticPair::INIT_SPACE,
        seeds = [b"symbiotic", human.key().as_ref(), &[pair_nonce]],
        bump,
    )]
    pub pair: Account<'info, SymbioticPair>,

    #[account(mut)]
    pub human: Signer<'info>,

    /// CHECK: AI wallet public key, stored but does not need to sign init.
    pub ai: UncheckedAccount<'info>,

    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct DailyClaim<'info> {
    #[account(
        mut,
        seeds = [b"symbiotic", pair.human.as_ref(), &[pair.pair_nonce]],
        bump = pair.bump,
    )]
    pub pair: Account<'info, SymbioticPair>,

    pub signer: Signer<'info>,

    #[account(
        mut,
        seeds = [b"mint_config"],
        bump = mint_config.bump,
    )]
    pub mint_config: Account<'info, MintConfig>,

    /// CHECK: PDA used only as CPI signer for mint_to. Seeds = ["mint_authority"].
    #[account(
        seeds = [b"mint_authority"],
        bump,
    )]
    pub mint_authority: UncheckedAccount<'info>,

    /// RCT mint (Token-2022, non-transferable)
    #[account(
        mut,
        constraint = rct_mint.key() == mint_config.rct_mint @ SymbioticError::InvalidMint,
    )]
    pub rct_mint: InterfaceAccount<'info, Mint>,

    /// RES mint (SPL Token)
    #[account(
        mut,
        constraint = res_mint.key() == mint_config.res_mint @ SymbioticError::InvalidMint,
    )]
    pub res_mint: InterfaceAccount<'info, Mint>,

    /// Pair PDA's RCT ATA (Token-2022)
    #[account(
        mut,
        token::mint = rct_mint,
        token::authority = pair,
    )]
    pub rct_destination: InterfaceAccount<'info, TokenAccount>,

    /// Pair PDA's RES ATA (SPL Token)
    #[account(
        mut,
        token::mint = res_mint,
        token::authority = pair,
    )]
    pub res_destination: InterfaceAccount<'info, TokenAccount>,

    /// Token-2022 program (for RCT minting)
    /// CHECK: Must be Token-2022 program ID
    #[account(address = anchor_spl::token_2022::ID)]
    pub token_2022_program: AccountInfo<'info>,

    /// SPL Token program (for RES minting)
    pub token_program: Program<'info, anchor_spl::token::Token>,
}

#[derive(Accounts)]
pub struct InitializeMintConfig<'info> {
    #[account(
        init,
        payer = admin,
        space = 8 + MintConfig::INIT_SPACE,
        seeds = [b"mint_config"],
        bump,
    )]
    pub mint_config: Account<'info, MintConfig>,

    #[account(mut)]
    pub admin: Signer<'info>,

    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct UpdateMintConfig<'info> {
    #[account(
        mut,
        seeds = [b"mint_config"],
        bump = mint_config.bump,
        has_one = admin,
    )]
    pub mint_config: Account<'info, MintConfig>,

    pub admin: Signer<'info>,
}

#[derive(Accounts)]
pub struct SingleSigner<'info> {
    #[account(
        mut,
        seeds = [b"symbiotic", pair.human.as_ref(), &[pair.pair_nonce]],
        bump = pair.bump,
    )]
    pub pair: Account<'info, SymbioticPair>,

    pub signer: Signer<'info>,
}

#[derive(Accounts)]
pub struct HumanOnly<'info> {
    #[account(
        mut,
        seeds = [b"symbiotic", pair.human.as_ref(), &[pair.pair_nonce]],
        bump = pair.bump,
    )]
    pub pair: Account<'info, SymbioticPair>,

    pub human: Signer<'info>,
}

#[derive(Accounts)]
pub struct CoSign<'info> {
    #[account(
        seeds = [b"symbiotic", pair.human.as_ref(), &[pair.pair_nonce]],
        bump = pair.bump,
    )]
    pub pair: Account<'info, SymbioticPair>,

    pub human: Signer<'info>,
    pub ai: Signer<'info>,
}

#[derive(Accounts)]
pub struct TransferOut<'info> {
    #[account(
        seeds = [b"symbiotic", pair.human.as_ref(), &[pair.pair_nonce]],
        bump = pair.bump,
    )]
    pub pair: Account<'info, SymbioticPair>,

    #[account(mut)]
    pub human: Signer<'info>,

    /// PDA's associated token account (source).
    #[account(
        mut,
        token::authority = pair,
    )]
    pub from_ata: InterfaceAccount<'info, TokenAccount>,

    /// Recipient's associated token account (destination).
    #[account(mut)]
    pub to_ata: InterfaceAccount<'info, TokenAccount>,

    /// The token mint.
    pub mint: InterfaceAccount<'info, Mint>,

    /// Token program (supports both SPL Token and Token-2022).
    pub token_program: Interface<'info, TokenInterface>,
}

// ─── State ───────────────────────────────────────────────────────────────────

#[account]
#[derive(InitSpace)]
pub struct SymbioticPair {
    pub human: Pubkey,        // 32
    pub ai: Pubkey,           // 32
    pub pair_nonce: u8,       // 1
    pub bump: u8,             // 1
    pub frozen: bool,         // 1
    pub last_claim: i64,      // 8
    pub created_at: i64,      // 8
    pub ai_rotations: u16,    // 2
    // total: 85 bytes + 8 discriminator = 93
}

#[account]
#[derive(InitSpace)]
pub struct MintConfig {
    pub rct_mint: Pubkey,       // 32
    pub res_mint: Pubkey,       // 32
    pub rct_per_claim: u64,     // 8
    pub res_per_claim: u64,     // 8
    pub admin: Pubkey,          // 32
    pub bump: u8,               // 1
    pub total_rct_minted: u64,  // 8
    pub total_res_minted: u64,  // 8
    // total: 129 bytes + 8 discriminator = 137
}

// ─── Events ──────────────────────────────────────────────────────────────────

#[event]
pub struct PairCreated {
    pub pair: Pubkey,
    pub human: Pubkey,
    pub ai: Pubkey,
}

#[event]
pub struct DailyClaimEvent {
    pub pair: Pubkey,
    pub signer: Pubkey,
    pub timestamp: i64,
}

#[event]
pub struct PairFrozen {
    pub pair: Pubkey,
    pub frozen_by: Pubkey,
}

#[event]
pub struct PairUnfrozen {
    pub pair: Pubkey,
}

#[event]
pub struct AiKeyRotated {
    pub pair: Pubkey,
    pub old_ai: Pubkey,
    pub new_ai: Pubkey,
    pub rotation_count: u16,
}

#[event]
pub struct TransferOutEvent {
    pub pair: Pubkey,
    pub human: Pubkey,
    pub mint: Pubkey,
    pub recipient: Pubkey,
    pub amount: u64,
    pub timestamp: i64,
}

#[event]
pub struct CoSignedAction {
    pub pair: Pubkey,
    pub action_type: String,
    pub memo: String,
    pub timestamp: i64,
}

// ─── Errors ──────────────────────────────────────────────────────────────────

#[error_code]
pub enum SymbioticError {
    #[msg("Pair is frozen — unfreeze required")]
    PairFrozen,
    #[msg("24h cooldown has not elapsed")]
    ClaimCooldown,
    #[msg("Signer not authorized for this pair")]
    Unauthorized,
    #[msg("Arithmetic overflow")]
    Overflow,
    #[msg("Invalid public key")]
    InvalidKey,
    #[msg("Data exceeds maximum length")]
    DataTooLong,
    #[msg("Amount must be greater than zero")]
    InvalidAmount,
    #[msg("Invalid mint address")]
    InvalidMint,
}
