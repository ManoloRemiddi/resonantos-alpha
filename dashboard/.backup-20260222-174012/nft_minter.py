"""Soulbound NFT minting using Token-2022 NonTransferable extension.

Uses spl-token CLI for reliable Token-2022 operations (avoids Python SDK
instruction encoding bugs). Metaplex metadata is handled separately.
"""

import json
import subprocess
import re
import time
from pathlib import Path
from typing import Optional, Dict, Any

from solana.rpc.api import Client
from solders.pubkey import Pubkey

from wallet import SolanaWallet


# Solana CLI path
_SOLANA_BIN = Path.home() / ".local" / "share" / "solana" / "install" / "active_release" / "bin"

# Token-2022 program
TOKEN_2022_PROGRAM = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"

# NFT type templates
NFT_TYPES = {
    "identity": {
        "name": "Augmentor Identity",
        "symbol": "RAID",
        "description": "Soulbound identity NFT for the Resonant Economy DAO. Non-transferable.",
        "uri": "https://resonantos.com/nft/identity.json",
    },
    "alpha_tester": {
        "name": "AI Artisan — Alpha Tester",
        "symbol": "RAAT",
        "description": "Soulbound badge for ResonantOS Alpha testers. Non-transferable. Early adopter.",
        "uri": "https://resonantos.com/nft/alpha-tester.json",
    },
    "symbiotic_license": {
        "name": "Symbiotic License Agreement",
        "symbol": "RASL",
        "description": "On-chain proof of Symbiotic License (RC-SL v1.0) co-signed by AI and Human.",
        "uri": "https://resonantos.com/nft/symbiotic-license.json",
    },
    "manifesto": {
        "name": "Augmentatism Manifesto",
        "symbol": "RAMF",
        "description": "On-chain commitment to the Augmentatism Manifesto, co-signed by AI and Human.",
        "uri": "https://resonantos.com/nft/manifesto.json",
    },
    "founder": {
        "name": "ResonantOS Founder",
        "symbol": "RAFO",
        "description": "One-of-one soulbound NFT for the creator of ResonantOS and founder of the Resonant Economy DAO.",
        "uri": "https://resonantos.com/nft/founder.json",
    },
    "dao_genesis": {
        "name": "Resonant Economy DAO Genesis",
        "symbol": "RADG",
        "description": "One-of-one soulbound NFT representing the genesis of the Resonant Economy DAO.",
        "uri": "https://resonantos.com/nft/dao-genesis.json",
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


class NFTMinter:
    """Mint soulbound (non-transferable) NFTs on Solana devnet via Token-2022.

    Uses spl-token CLI for all Token-2022 operations to ensure correctness.
    """

    def __init__(self, wallet: Optional[SolanaWallet] = None):
        """Initialize NFTMinter.

        Args:
            wallet: SolanaWallet instance. Creates default if None.
        """
        self.wallet = wallet or SolanaWallet()
        self.client = self.wallet.client
        self.keypair_path = str(Path("~/.config/solana/id.json").expanduser())

    def mint_soulbound_nft(
        self,
        recipient: str,
        nft_type: str = "identity",
        name: Optional[str] = None,
        symbol: Optional[str] = None,
        uri: Optional[str] = None,
        fee_payer_keypair: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Mint a soulbound (non-transferable) NFT to the recipient.

        Steps:
        1. Create Token-2022 mint with NonTransferable extension (0 decimals)
        2. Create associated token account for recipient
        3. Mint exactly 1 token (NFT)

        Args:
            recipient: Recipient wallet address (base58).
            nft_type: One of NFT_TYPES keys.
            name: Override default name.
            symbol: Override default symbol.
            uri: Override default metadata URI.
            fee_payer_keypair: Optional path to fee payer keypair (for gas sponsorship).

        Returns:
            Dict with mint address, recipient, signatures.

        Raises:
            ValueError: If nft_type is unknown.
            RuntimeError: If any CLI command fails.
        """
        if nft_type not in NFT_TYPES:
            raise ValueError(f"Unknown NFT type: {nft_type}. Options: {list(NFT_TYPES.keys())}")

        template = NFT_TYPES[nft_type]
        _name = name or template["name"]
        _symbol = symbol or template["symbol"]
        _uri = uri or template["uri"]

        payer = fee_payer_keypair or self.keypair_path

        # Step 1: Create non-transferable mint with metadata extension (0 decimals = NFT)
        output = _run_spl_token(
            "create-token",
            "--program-id", TOKEN_2022_PROGRAM,
            "--decimals", "0",
            "--enable-non-transferable",
            "--enable-metadata",
            keypair_path=payer,
        )

        # Extract mint address from output
        mint_match = re.search(r"Address:\s+(\S+)", output)
        if not mint_match:
            # Try alternate format: "Creating token <address>"
            mint_match = re.search(r"Creating token\s+(\S+)", output)
        if not mint_match:
            raise RuntimeError(f"Could not parse mint address from: {output}")
        mint_address = mint_match.group(1)

        # Step 1b: Initialize on-chain metadata (name, symbol, URI)
        try:
            _run_spl_token(
                "initialize-metadata",
                mint_address,
                _name,
                _symbol,
                _uri,
                keypair_path=payer,
            )
        except RuntimeError as e:
            # Log but don't fail — NFT is still valid without metadata
            import sys
            print(f"Warning: metadata initialization failed: {e}", file=sys.stderr)

        # Step 2: Create ATA for recipient
        create_output = _run_spl_token(
            "create-account",
            "--program-id", TOKEN_2022_PROGRAM,
            "--owner", recipient,
            mint_address,
            keypair_path=payer,
        )

        # Extract ATA address
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

        # Extract signature
        sig_match = re.search(r"Signature:\s+(\S+)", mint_output)
        mint_sig = sig_match.group(1) if sig_match else "unknown"

        return {
            "mint": mint_address,
            "ata": ata_address,
            "recipient": recipient,
            "nft_type": nft_type,
            "name": _name,
            "symbol": _symbol,
            "uri": _uri,
            "mint_signature": mint_sig,
            "soulbound": True,
        }

    def mint_identity_nft(self, recipient: str, fee_payer_keypair: Optional[str] = None) -> Dict[str, Any]:
        """Mint an Augmentor Identity NFT (soulbound).

        Args:
            recipient: Wallet address.
            fee_payer_keypair: Optional gas sponsor keypair path.

        Returns:
            Dict with mint details.
        """
        return self.mint_soulbound_nft(recipient, nft_type="identity", fee_payer_keypair=fee_payer_keypair)

    def mint_alpha_tester_nft(self, recipient: str, fee_payer_keypair: Optional[str] = None) -> Dict[str, Any]:
        """Mint an AI Artisan Alpha Tester NFT (soulbound).

        Args:
            recipient: Wallet address.
            fee_payer_keypair: Optional gas sponsor keypair path.

        Returns:
            Dict with mint details.
        """
        return self.mint_soulbound_nft(recipient, nft_type="alpha_tester", fee_payer_keypair=fee_payer_keypair)

    def mint_license_nft(self, recipient: str, fee_payer_keypair: Optional[str] = None) -> Dict[str, Any]:
        """Mint a Symbiotic License NFT (co-signed, soulbound).

        Args:
            recipient: Wallet address.
            fee_payer_keypair: Optional gas sponsor keypair path.

        Returns:
            Dict with mint details.
        """
        return self.mint_soulbound_nft(recipient, nft_type="symbiotic_license", fee_payer_keypair=fee_payer_keypair)

    def mint_manifesto_nft(self, recipient: str, fee_payer_keypair: Optional[str] = None) -> Dict[str, Any]:
        """Mint an Augmentatism Manifesto NFT (co-signed, soulbound).

        Args:
            recipient: Wallet address.
            fee_payer_keypair: Optional gas sponsor keypair path.

        Returns:
            Dict with mint details.
        """
        return self.mint_soulbound_nft(recipient, nft_type="manifesto", fee_payer_keypair=fee_payer_keypair)
