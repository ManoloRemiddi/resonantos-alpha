"""Transferable Protocol NFT minting using Token-2022.

Unlike soulbound NFTs, protocol NFTs are transferable — they can be
traded, sold, or gifted between wallets. Still uses Token-2022 with
0 decimals for NFT semantics.
"""

import json
import subprocess
import re
from pathlib import Path
from typing import Optional, Dict, Any

from solana.rpc.api import Client
from solders.pubkey import Pubkey

from wallet import SolanaWallet


# Solana CLI path
_SOLANA_BIN = Path.home() / ".local" / "share" / "solana" / "install" / "active_release" / "bin"

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


def _run_spl_token(*args: str, keypair_path: str = "~/.config/solana/id.json") -> str:
    """Run an spl-token CLI command and return stdout.

    Args:
        *args: Arguments to pass to spl-token.
        keypair_path: Path to the signing keypair.

    Returns:
        str: Command stdout.

    Raises:
        RuntimeError: If the command fails.
    """
    expanded = str(Path(keypair_path).expanduser())
    cmd = [
        str(_SOLANA_BIN / "spl-token"),
        *args,
        "--url", "devnet",
        "--fee-payer", expanded,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        raise RuntimeError(f"spl-token failed: {result.stderr.strip()}")
    return result.stdout.strip()


class ProtocolNFTMinter:
    """Mint transferable protocol NFTs on Solana devnet via Token-2022."""

    def __init__(self, wallet: Optional[SolanaWallet] = None):
        self.wallet = wallet or SolanaWallet()
        self.client = self.wallet.client
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
            RuntimeError: If any CLI command fails.
        """
        if protocol_id not in PROTOCOL_NFTS:
            raise ValueError(f"Unknown protocol: {protocol_id}. Options: {list(PROTOCOL_NFTS.keys())}")

        template = PROTOCOL_NFTS[protocol_id]
        payer = fee_payer_keypair or self.keypair_path

        # Step 1: Create transferable mint (0 decimals = NFT)
        # NOTE: No --enable-non-transferable flag — these are tradeable
        output = _run_spl_token(
            "create-token",
            "--program-id", TOKEN_2022_PROGRAM,
            "--decimals", "0",
            keypair_path=payer,
        )

        # Extract mint address
        mint_match = re.search(r"Address:\s+(\S+)", output)
        if not mint_match:
            mint_match = re.search(r"Creating token\s+(\S+)", output)
        if not mint_match:
            raise RuntimeError(f"Could not parse mint address from: {output}")
        mint_address = mint_match.group(1)

        # Step 2: Create ATA for recipient
        create_output = _run_spl_token(
            "create-account",
            "--program-id", TOKEN_2022_PROGRAM,
            "--owner", recipient,
            mint_address,
            keypair_path=payer,
        )

        ata_match = re.search(r"Creating account\s+(\S+)", create_output)
        ata_address = ata_match.group(1) if ata_match else "unknown"

        # Step 3: Mint exactly 1 token
        mint_output = _run_spl_token(
            "mint",
            "--program-id", TOKEN_2022_PROGRAM,
            mint_address, "1",
            ata_address,
            keypair_path=payer,
        )

        sig_match = re.search(r"Signature:\s+(\S+)", mint_output)
        mint_sig = sig_match.group(1) if sig_match else "unknown"

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
            output = _run_spl_token(
                "balance",
                "--program-id", TOKEN_2022_PROGRAM,
                "--owner", wallet_address,
                mint_address,
                keypair_path=self.keypair_path,
            )
            # Output is just the balance number, e.g. "1"
            balance = float(output.strip())
            return balance >= 1
        except (RuntimeError, ValueError):
            return False

    def list_protocol_nfts(self) -> Dict[str, Dict[str, Any]]:
        """Return the available protocol NFTs catalog.

        Returns:
            Dict of protocol_id → protocol metadata.
        """
        return PROTOCOL_NFTS.copy()
