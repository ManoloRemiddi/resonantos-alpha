"""Soulbound NFT minting using Token-2022 NonTransferable extension.

Uses spl-token CLI for reliable Token-2022 operations (avoids Python SDK
instruction encoding bugs). Metaplex metadata is handled separately.
"""

import json
import subprocess
import re
import time
import urllib.request
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

    def _rpc_url(self) -> str:
        provider = getattr(self.client, "_provider", None)
        endpoint_uri = getattr(provider, "endpoint_uri", None)
        return endpoint_uri or "https://api.devnet.solana.com"

    def _rpc_call(self, method: str, params: Optional[list] = None) -> Dict[str, Any]:
        body = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params or [],
        }).encode()
        req = urllib.request.Request(
            self._rpc_url(),
            data=body,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())

    @staticmethod
    def _normalize_nft_type(nft_type: str) -> str:
        mapping = {
            "alpha": "alpha_tester",
            "alpha_tester": "alpha_tester",
            "identity": "identity",
            "license": "symbiotic_license",
            "symbiotic_license": "symbiotic_license",
            "manifesto": "manifesto",
        }
        key = (nft_type or "").strip().lower()
        return mapping.get(key, key)

    @staticmethod
    def _extract_onchain_name(account_info: Dict[str, Any]) -> Optional[str]:
        try:
            mint_data = account_info.get("result", {}).get("value", {}).get("data", {})
            parsed_info = mint_data.get("parsed", {}).get("info", {}) if isinstance(mint_data, dict) else {}
            extensions = parsed_info.get("extensions", [])
            for ext in extensions:
                if ext.get("extension") == "tokenMetadata":
                    state = ext.get("state", {})
                    name = (state.get("name") or "").strip().rstrip("\x00")
                    if name:
                        return name
        except Exception:
            return None
        return None

    @staticmethod
    def _name_to_nft_type(name: str) -> Optional[str]:
        normalized = (name or "").strip().lower()
        if not normalized:
            return None

        name_map = {
            "identity": [
                "augmentor identity",
                "resonantos identity",
            ],
            "alpha_tester": [
                "ai artisan — alpha tester",
                "ai artisan - alpha tester",
                "ai artisan — alpha",
                "resonantos alpha tester",
                "alpha tester",
            ],
            "symbiotic_license": [
                "symbiotic license agreement",
                "resonant commons license signatory",
                "symbiotic license",
            ],
            "manifesto": [
                "augmentatism manifesto signatory",
                "augmentatism manifesto",
            ],
        }
        for nft_type, candidates in name_map.items():
            for candidate in candidates:
                if candidate in normalized:
                    return nft_type
        return None

    @staticmethod
    def _registry_path_candidates() -> list[Path]:
        base = Path(__file__).resolve().parent
        return [
            base / "data" / "nft_registry.json",
            base.parent / "data" / "nft_registry.json",
            base.parent.parent / "dashboard-audit" / "data" / "nft_registry.json",
            Path.cwd() / "data" / "nft_registry.json",
            Path.home() / "resonantos-augmentor" / "data" / "nft_registry.json",
        ]

    def _load_nft_registry(self) -> Dict[str, str]:
        for reg_path in self._registry_path_candidates():
            try:
                if reg_path.exists():
                    data = json.loads(reg_path.read_text())
                    if isinstance(data, dict):
                        return {k: self._normalize_nft_type(v) for k, v in data.items()}
            except Exception:
                continue
        return {}

    def check_wallet_has_nft(self, address: str, nft_type: str) -> Dict[str, Any]:
        """Check whether wallet/PDA already holds a specific NFT type.

        Returns:
            {"has_nft": bool, "mint": str|None, "matched_by": str|None}
        """
        target_type = self._normalize_nft_type(nft_type)
        registry = self._load_nft_registry()

        result = self._rpc_call("getTokenAccountsByOwner", [
            address,
            {"programId": TOKEN_2022_PROGRAM},
            {"encoding": "jsonParsed"},
        ])

        accounts = result.get("result", {}).get("value", [])
        for account in accounts:
            parsed = account.get("account", {}).get("data", {}).get("parsed", {}).get("info", {})
            mint = parsed.get("mint")
            token_amount = parsed.get("tokenAmount", {})
            amount_raw = token_amount.get("amount", 0)
            decimals = int(token_amount.get("decimals", 0))
            try:
                amount = int(amount_raw)
            except Exception:
                amount = 0

            if not mint or amount <= 0 or decimals != 0:
                continue

            reg_type = self._normalize_nft_type(registry.get(mint, ""))
            if reg_type and reg_type == target_type:
                return {"has_nft": True, "mint": mint, "matched_by": "registry"}

            try:
                mint_info = self._rpc_call("getAccountInfo", [mint, {"encoding": "jsonParsed"}])
                onchain_name = self._extract_onchain_name(mint_info)
                onchain_type = self._name_to_nft_type(onchain_name or "")
                if onchain_type == target_type:
                    return {"has_nft": True, "mint": mint, "matched_by": "metadata"}
            except Exception:
                continue

        return {"has_nft": False, "mint": None, "matched_by": None}
