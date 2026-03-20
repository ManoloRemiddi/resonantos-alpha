"""Transferable Protocol NFT minting using Token-2022.

Unlike soulbound NFTs, protocol NFTs are transferable — they can be
traded, sold, or gifted between wallets. Uses Token-2022 with
0 decimals for NFT semantics.
"""

from pathlib import Path
from typing import Optional, Dict, Any

from token2022_utils import (
    create_ata_and_mint,
    create_token2022_mint,
    get_token_balance,
    load_keypair_from_path,
)
from wallet import SolanaWallet


# Token-2022 program
TOKEN_2022_PROGRAM = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"

# Protocol NFT definitions
PROTOCOL_NFTS = {
    "blindspot": {
        "name": "Blindspot Protocol — Scugnizzo AI",
        "symbol": "ROS-BLP",
        "description": "Adversarial red team protocol. Finds vulnerabilities, exploits, and critical flaws others miss. Street-smart skeptic analysis.",
        "uri": "https://resonantos.com/protocols/blindspot.json",
        "price_res": 100,
        "image": "/static/img/protocol-blindspot.png",
    },
    "acupuncturist": {
        "name": "Acupuncturist Protocol",
        "symbol": "ROS-ACP",
        "description": "Protocol enforcement and systems analysis. Targeted improvements via acupuncture-style precision diagnostics.",
        "uri": "https://resonantos.com/protocols/acupuncturist.json",
        "price_res": 100,
        "image": "/static/img/protocol-acupuncturist.png",
    },
}
class ProtocolNFTMinter:
    """Mint transferable protocol NFTs on Solana devnet via Token-2022."""

    def __init__(self, wallet: Optional[SolanaWallet] = None):
        self.wallet = wallet or SolanaWallet()
        self.client = self.wallet.client
        self.payer = self.wallet.keypair
        self.keypair_path = str(Path("~/.config/solana/id.json").expanduser())

    def mint_protocol_nft(
        self,
        recipient: str,
        protocol_id: str,
        fee_payer_keypair: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Mint a transferable protocol NFT to the recipient.

        Steps:
        1. Create Token-2022 mint (0 decimals, NO non-transferable flag)
        2. Create associated token account for recipient
        3. Mint exactly 1 token

        Args:
            recipient: Recipient wallet address (base58).
            protocol_id: Key from PROTOCOL_NFTS dict.
            fee_payer_keypair: Optional path to fee payer keypair.

        Returns:
            Dict with mint address, recipient, protocol details.

        Raises:
            ValueError: If protocol_id is unknown.
            RuntimeError: If any mint operation fails.
        """
        if protocol_id not in PROTOCOL_NFTS:
            raise ValueError(f"Unknown protocol: {protocol_id}. Options: {list(PROTOCOL_NFTS.keys())}")

        template = PROTOCOL_NFTS[protocol_id]
        payer_keypair = (
            load_keypair_from_path(fee_payer_keypair)
            if fee_payer_keypair
            else self.payer
        )

        # Step 1: Create transferable mint (0 decimals = NFT)
        # NOTE: No --enable-non-transferable flag — these are tradeable
        mint_result = create_token2022_mint(
            self.client,
            payer_keypair,
            decimals=0,
            enable_non_transferable=False,
            enable_metadata=False,
        )
        mint_address = mint_result["mint"]

        # Step 2 + 3: Create ATA for recipient, then mint exactly 1 token
        mint_to_result = create_ata_and_mint(
            self.client,
            payer_keypair,
            mint_address,
            recipient,
            amount=1,
        )
        ata_address = mint_to_result["ata"]
        mint_sig = mint_to_result["signature"]

        return {
            "mint": mint_address,
            "ata": ata_address,
            "recipient": recipient,
            "protocol_id": protocol_id,
            "name": template["name"],
            "symbol": template["symbol"],
            "uri": template["uri"],
            "price_res": template["price_res"],
            "mint_signature": mint_sig,
            "soulbound": False,
            "transferable": True,
        }

    def check_ownership(self, wallet_address: str, mint_address: str) -> bool:
        """Check if a wallet holds a specific protocol NFT.

        Args:
            wallet_address: Wallet to check (base58).
            mint_address: NFT mint address to look for.

        Returns:
            True if the wallet holds at least 1 token of this mint.
        """
        try:
            balance = get_token_balance(self.client, wallet_address, mint_address)
            return balance >= 1
        except Exception:
            return False

    def list_protocol_nfts(self) -> Dict[str, Dict[str, Any]]:
        """Return the available protocol NFTs catalog.

        Returns:
            Dict of protocol_id → protocol metadata.
        """
        return PROTOCOL_NFTS.copy()
