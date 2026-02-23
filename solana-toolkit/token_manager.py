"""Token management for SPL and Token-2022 tokens on Solana."""

import struct
import time
from pathlib import Path
from typing import Dict, List, Optional, Any

from solana.rpc.api import Client
from solana.rpc.types import TokenAccountOpts, TxOpts
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.system_program import CreateAccountParams, create_account
from solders.instruction import Instruction, AccountMeta
from solders.transaction import Transaction
from solders.message import Message

from spl.token.constants import TOKEN_PROGRAM_ID, TOKEN_2022_PROGRAM_ID, ASSOCIATED_TOKEN_PROGRAM_ID
from spl.token.instructions import (
    initialize_mint, InitializeMintParams,
    mint_to, MintToParams,
    get_associated_token_address,
)

from wallet import SolanaWallet


# Token-2022 extension type IDs
_EXT_NON_TRANSFERABLE = 17  # NonTransferable extension


def _initialize_non_transferable_mint_ix(mint: Pubkey) -> Instruction:
    """Build the InitializeNonTransferableMint instruction for Token-2022.

    Instruction index 35 (0x23) with no additional data.
    Must be called BEFORE InitializeMint.
    """
    data = struct.pack("<B", 35)  # instruction discriminator
    accounts = [AccountMeta(pubkey=mint, is_signer=False, is_writable=True)]
    return Instruction(TOKEN_2022_PROGRAM_ID, data, accounts)


def _create_ata_ix(
    payer: Pubkey,
    owner: Pubkey,
    mint: Pubkey,
    token_program_id: Pubkey = TOKEN_PROGRAM_ID,
) -> Instruction:
    """Build a CreateAssociatedTokenAccount instruction (works for both SPL and Token-2022)."""
    ata = get_associated_token_address(owner, mint, token_program_id)
    keys = [
        AccountMeta(pubkey=payer, is_signer=True, is_writable=True),
        AccountMeta(pubkey=ata, is_signer=False, is_writable=True),
        AccountMeta(pubkey=owner, is_signer=False, is_writable=False),
        AccountMeta(pubkey=mint, is_signer=False, is_writable=False),
        AccountMeta(pubkey=Pubkey.from_string("11111111111111111111111111111111"), is_signer=False, is_writable=False),
        AccountMeta(pubkey=token_program_id, is_signer=False, is_writable=False),
    ]
    return Instruction(ASSOCIATED_TOKEN_PROGRAM_ID, bytes(), keys)


class TokenManager:
    """Manage SPL and Token-2022 token creation, minting, and balance queries."""

    def __init__(self, wallet: Optional[SolanaWallet] = None):
        """
        Initialize TokenManager.

        Args:
            wallet: SolanaWallet instance. Creates default if None.
        """
        self.wallet = wallet or SolanaWallet()
        self.client = self.wallet.client
        self.payer = self.wallet.keypair

    def _send_tx(self, ixs: List[Instruction], signers: List[Keypair]) -> str:
        """Build, sign and send a transaction. Returns signature string."""
        blockhash_resp = self.client.get_latest_blockhash()
        blockhash = blockhash_resp.value.blockhash
        msg = Message.new_with_blockhash(ixs, self.payer.pubkey(), blockhash)
        tx = Transaction.new_unsigned(msg)
        tx.sign(signers, blockhash)
        resp = self.client.send_transaction(tx, opts=TxOpts(skip_preflight=True, preflight_commitment="confirmed"))
        sig = resp.value
        if sig is None:
            raise Exception(f"Transaction failed: {resp}")
        # Wait for confirmation
        for _ in range(30):
            status = self.client.get_signature_statuses([sig])
            if status.value and status.value[0] is not None:
                if status.value[0].err:
                    raise Exception(f"Transaction error: {status.value[0].err}")
                return str(sig)
            time.sleep(1)
        return str(sig)

    def create_spl_token(self, decimals: int = 6) -> str:
        """
        Create a new standard SPL token mint.

        Args:
            decimals: Number of decimal places for the token.

        Returns:
            str: The mint public key as base58 string.
        """
        mint_keypair = Keypair()
        mint_pubkey = mint_keypair.pubkey()

        # Get minimum rent for Mint account (82 bytes)
        rent = self.client.get_minimum_balance_for_rent_exemption(82)
        lamports = rent.value

        create_ix = create_account(CreateAccountParams(
            from_pubkey=self.payer.pubkey(),
            to_pubkey=mint_pubkey,
            lamports=lamports,
            space=82,
            owner=TOKEN_PROGRAM_ID,
        ))

        init_ix = initialize_mint(InitializeMintParams(
            program_id=TOKEN_PROGRAM_ID,
            mint=mint_pubkey,
            decimals=decimals,
            mint_authority=self.payer.pubkey(),
            freeze_authority=self.payer.pubkey(),
        ))

        sig = self._send_tx([create_ix, init_ix], [self.payer, mint_keypair])
        print(f"Created SPL token mint: {mint_pubkey} (tx: {sig})")
        return str(mint_pubkey)

    def create_token2022_non_transferable(self, decimals: int = 9) -> str:
        """
        Create a Token-2022 mint with NonTransferable extension (soulbound).

        Uses the spl-token CLI for correctness — the canonical implementation
        for Token-2022 extension instructions. Security-first approach.

        Args:
            decimals: Number of decimal places.

        Returns:
            str: The mint public key as base58 string.

        Raises:
            Exception: If spl-token CLI is not available or creation fails.
        """
        import subprocess
        import re

        solana_bin = str(Path.home() / ".local/share/solana/install/active_release/bin/spl-token")
        result = subprocess.run(
            [
                solana_bin, "create-token",
                "--program-id", str(TOKEN_2022_PROGRAM_ID),
                "--decimals", str(decimals),
                "--enable-non-transferable",
            ],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            raise Exception(f"spl-token create-token failed: {result.stderr}")

        # Parse mint address from output: "Address:  <pubkey>"
        match = re.search(r"Address:\s+(\S+)", result.stdout)
        if not match:
            raise Exception(f"Could not parse mint address from: {result.stdout}")

        mint_address = match.group(1)
        print(f"Created Token-2022 NonTransferable mint: {mint_address}")
        return mint_address

    def mint_tokens(
        self,
        mint: str,
        destination_owner: str,
        amount: int,
        token_program: str = "spl",
    ) -> str:
        """
        Mint tokens to a destination wallet.

        Args:
            mint: Mint public key (base58).
            destination_owner: Owner wallet public key (base58).
            amount: Raw amount (with decimals factored in).
            token_program: 'spl' or 'token2022'.

        Returns:
            str: Transaction signature.
        """
        mint_pk = Pubkey.from_string(mint)
        owner_pk = Pubkey.from_string(destination_owner)
        program_id = TOKEN_2022_PROGRAM_ID if token_program == "token2022" else TOKEN_PROGRAM_ID

        ata = get_associated_token_address(owner_pk, mint_pk, program_id)

        # Check if ATA exists
        acct_info = self.client.get_account_info(ata)
        ixs: List[Instruction] = []
        if acct_info.value is None:
            ixs.append(_create_ata_ix(self.payer.pubkey(), owner_pk, mint_pk, program_id))

        ixs.append(mint_to(MintToParams(
            program_id=program_id,
            mint=mint_pk,
            dest=ata,
            mint_authority=self.payer.pubkey(),
            amount=amount,
            signers=[self.payer.pubkey()],
        )))

        sig = self._send_tx(ixs, [self.payer])
        print(f"Minted {amount} tokens to {ata} (tx: {sig})")
        return sig

    def get_token_balances(self, owner: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all token balances for a wallet (both SPL and Token-2022).

        Args:
            owner: Wallet public key (base58). Defaults to own wallet.

        Returns:
            List of dicts with mint, balance, decimals, program fields.
        """
        owner_pk = Pubkey.from_string(owner) if owner else self.payer.pubkey()
        balances: List[Dict[str, Any]] = []

        for program_id, program_name in [
            (TOKEN_PROGRAM_ID, "spl"),
            (TOKEN_2022_PROGRAM_ID, "token2022"),
        ]:
            try:
                resp = self.client.get_token_accounts_by_owner_json_parsed(
                    owner_pk,
                    TokenAccountOpts(program_id=program_id),
                )
                if resp.value:
                    for acct in resp.value:
                        parsed = acct.account.data.parsed
                        info = parsed["info"]
                        token_amount = info["tokenAmount"]
                        balances.append({
                            "mint": info["mint"],
                            "balance": float(token_amount["uiAmountString"]),
                            "raw_amount": int(token_amount["amount"]),
                            "decimals": token_amount["decimals"],
                            "program": program_name,
                            "account": str(acct.pubkey),
                        })
            except Exception as e:
                print(f"Warning: failed to query {program_name} accounts: {e}")

        return balances
