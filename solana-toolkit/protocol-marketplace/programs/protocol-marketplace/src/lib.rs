use anchor_lang::prelude::*;
use anchor_spl::token_2022::{self, Token2022, TransferChecked};
use anchor_spl::associated_token::AssociatedToken;

declare_id!("5wpGj4EG6J5uEqozLqUyHzEQbU26yjaL5aUE5FwBiYe5");

/// Protocol NFT Marketplace — on-chain escrow for transferable protocol NFTs.
///
/// Flow:
/// 1. Seller calls `list_protocol` → NFT transferred to escrow PDA, Listing account created
/// 2. Buyer calls `buy_protocol` → $RES transferred to seller, NFT released to buyer
/// 3. Seller calls `delist_protocol` → NFT returned, Listing account closed
///
/// All state on-chain. No server required.

#[program]
pub mod protocol_marketplace {
    use super::*;

    /// List a protocol NFT for sale. Transfers NFT to escrow PDA.
    pub fn list_protocol(ctx: Context<ListProtocol>, price_res: u64) -> Result<()> {
        require!(price_res >= 1, MarketplaceError::PriceTooLow);

        // Transfer NFT from seller to escrow
        let cpi_accounts = TransferChecked {
            from: ctx.accounts.seller_nft_ata.to_account_info(),
            mint: ctx.accounts.nft_mint.to_account_info(),
            to: ctx.accounts.escrow_nft_ata.to_account_info(),
            authority: ctx.accounts.seller.to_account_info(),
        };
        let cpi_program = ctx.accounts.token_program.to_account_info();
        token_2022::transfer_checked(
            CpiContext::new(cpi_program, cpi_accounts),
            1,   // 1 NFT
            0,   // 0 decimals
        )?;

        // Initialize listing
        let listing = &mut ctx.accounts.listing;
        listing.seller = ctx.accounts.seller.key();
        listing.nft_mint = ctx.accounts.nft_mint.key();
        listing.price_res = price_res;
        listing.created_at = Clock::get()?.unix_timestamp;
        listing.bump = ctx.bumps.escrow_authority;

        Ok(())
    }

    /// Buy a listed protocol NFT. Sends $RES to seller, NFT to buyer.
    pub fn buy_protocol(ctx: Context<BuyProtocol>) -> Result<()> {
        let listing = &ctx.accounts.listing;
        let price = listing.price_res;
        let nft_mint_key = listing.nft_mint;
        let bump = listing.bump;

        // Transfer $RES from buyer to seller
        let res_accounts = TransferChecked {
            from: ctx.accounts.buyer_res_ata.to_account_info(),
            mint: ctx.accounts.res_mint.to_account_info(),
            to: ctx.accounts.seller_res_ata.to_account_info(),
            authority: ctx.accounts.buyer.to_account_info(),
        };
        // $RES is standard SPL (use token_2022 interface — works for both)
        token_2022::transfer_checked(
            CpiContext::new(ctx.accounts.res_token_program.to_account_info(), res_accounts),
            price,
            6, // $RES decimals
        )?;

        // Transfer NFT from escrow to buyer (PDA signs)
        let seeds = &[
            b"escrow",
            nft_mint_key.as_ref(),
            &[bump],
        ];
        let signer_seeds = &[&seeds[..]];

        let nft_accounts = TransferChecked {
            from: ctx.accounts.escrow_nft_ata.to_account_info(),
            mint: ctx.accounts.nft_mint.to_account_info(),
            to: ctx.accounts.buyer_nft_ata.to_account_info(),
            authority: ctx.accounts.escrow_authority.to_account_info(),
        };
        token_2022::transfer_checked(
            CpiContext::new_with_signer(
                ctx.accounts.nft_token_program.to_account_info(),
                nft_accounts,
                signer_seeds,
            ),
            1,
            0,
        )?;

        Ok(())
    }

    /// Delist: return NFT to seller, close listing.
    pub fn delist_protocol(ctx: Context<DelistProtocol>) -> Result<()> {
        let listing = &ctx.accounts.listing;
        let nft_mint_key = listing.nft_mint;
        let bump = listing.bump;

        let seeds = &[
            b"escrow",
            nft_mint_key.as_ref(),
            &[bump],
        ];
        let signer_seeds = &[&seeds[..]];

        let nft_accounts = TransferChecked {
            from: ctx.accounts.escrow_nft_ata.to_account_info(),
            mint: ctx.accounts.nft_mint.to_account_info(),
            to: ctx.accounts.seller_nft_ata.to_account_info(),
            authority: ctx.accounts.escrow_authority.to_account_info(),
        };
        token_2022::transfer_checked(
            CpiContext::new_with_signer(
                ctx.accounts.token_program.to_account_info(),
                nft_accounts,
                signer_seeds,
            ),
            1,
            0,
        )?;

        Ok(())
    }
}

// ── Accounts ──────────────────────────────────────────────────────

#[derive(Accounts)]
pub struct ListProtocol<'info> {
    #[account(mut)]
    pub seller: Signer<'info>,

    /// The protocol NFT mint (Token-2022, transferable, 0 decimals)
    pub nft_mint: AccountInfo<'info>,

    /// Seller's ATA for the NFT
    #[account(mut)]
    pub seller_nft_ata: AccountInfo<'info>,

    /// Escrow PDA authority (seeds: ["escrow", nft_mint])
    /// CHECK: PDA derived from seeds
    #[account(
        seeds = [b"escrow", nft_mint.key().as_ref()],
        bump,
    )]
    pub escrow_authority: AccountInfo<'info>,

    /// Escrow ATA for the NFT (owned by escrow_authority)
    #[account(mut)]
    pub escrow_nft_ata: AccountInfo<'info>,

    /// Listing PDA (seeds: ["listing", nft_mint])
    #[account(
        init,
        payer = seller,
        space = 8 + Listing::INIT_SPACE,
        seeds = [b"listing", nft_mint.key().as_ref()],
        bump,
    )]
    pub listing: Account<'info, Listing>,

    pub token_program: Program<'info, Token2022>,
    pub associated_token_program: Program<'info, AssociatedToken>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct BuyProtocol<'info> {
    #[account(mut)]
    pub buyer: Signer<'info>,

    /// Listing to purchase
    #[account(
        mut,
        close = seller,
        seeds = [b"listing", nft_mint.key().as_ref()],
        bump,
        has_one = seller,
        has_one = nft_mint,
    )]
    pub listing: Account<'info, Listing>,

    /// CHECK: validated by listing.seller
    #[account(mut)]
    pub seller: AccountInfo<'info>,

    pub nft_mint: AccountInfo<'info>,
    pub res_mint: AccountInfo<'info>,

    /// Buyer's $RES ATA
    #[account(mut)]
    pub buyer_res_ata: AccountInfo<'info>,
    /// Seller's $RES ATA
    #[account(mut)]
    pub seller_res_ata: AccountInfo<'info>,

    /// Buyer's NFT ATA
    #[account(mut)]
    pub buyer_nft_ata: AccountInfo<'info>,

    /// Escrow PDA
    /// CHECK: PDA
    #[account(
        seeds = [b"escrow", nft_mint.key().as_ref()],
        bump,
    )]
    pub escrow_authority: AccountInfo<'info>,

    /// Escrow NFT ATA
    #[account(mut)]
    pub escrow_nft_ata: AccountInfo<'info>,

    pub nft_token_program: Program<'info, Token2022>,
    /// $RES might be standard SPL — pass appropriate program
    pub res_token_program: AccountInfo<'info>,
    pub associated_token_program: Program<'info, AssociatedToken>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct DelistProtocol<'info> {
    #[account(mut)]
    pub seller: Signer<'info>,

    #[account(
        mut,
        close = seller,
        seeds = [b"listing", nft_mint.key().as_ref()],
        bump,
        has_one = seller,
        has_one = nft_mint,
    )]
    pub listing: Account<'info, Listing>,

    pub nft_mint: AccountInfo<'info>,

    #[account(mut)]
    pub seller_nft_ata: AccountInfo<'info>,

    /// CHECK: PDA
    #[account(
        seeds = [b"escrow", nft_mint.key().as_ref()],
        bump,
    )]
    pub escrow_authority: AccountInfo<'info>,

    #[account(mut)]
    pub escrow_nft_ata: AccountInfo<'info>,

    pub token_program: Program<'info, Token2022>,
    pub system_program: Program<'info, System>,
}

// ── State ─────────────────────────────────────────────────────────

#[account]
#[derive(InitSpace)]
pub struct Listing {
    pub seller: Pubkey,     // 32
    pub nft_mint: Pubkey,   // 32
    pub price_res: u64,     // 8
    pub created_at: i64,    // 8
    pub bump: u8,           // 1
}

// ── Errors ────────────────────────────────────────────────────────

#[error_code]
pub enum MarketplaceError {
    #[msg("Price must be at least 1 $RES")]
    PriceTooLow,
}
