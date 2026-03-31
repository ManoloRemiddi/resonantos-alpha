"""Wallet helpers shared by wallet routes and other server modules."""

from __future__ import annotations

import json
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any

from flask import current_app

from routes.config import (
    _DAILY_CLAIMS_FILE,
    _DAO_DETAILS,
    _MIN_SOL_FOR_GAS,
    _NFT_REGISTRY_FILE,
    _ONBOARDING_FILE,
    _RCT_CAPS_FILE,
    _RCT_DAILY_FLOOR,
    _RCT_DAILY_MAX,
    _RCT_DAILY_PER_HOLDER,
    _RCT_MAX_PER_WALLET_YEAR,
    _REGISTRATION_BASKET_KEYPAIR,
    _SOLANA_KEYPAIR,
    _SOLANA_RPCS,
    _SYMBIOTIC_PROGRAM_ID,
    NFTMinter,
    SolanaWallet,
)


def _get_wallet_pubkey() -> str | None:
    """Read the AI wallet public key.

    Returns:
        str | None: Base58 public key if the keypair can be read.
    """
    try:
        import json as _j

        from solders.keypair import Keypair as _Kp

        data = _j.loads(_SOLANA_KEYPAIR.read_text())
        kp = _Kp.from_bytes(bytes(data))
        return str(kp.pubkey())
    except Exception:
        return None


def _get_dao_details() -> dict[str, Any]:
    """Load DAO details from disk.

    Returns:
        dict[str, Any]: DAO metadata, or an empty dict on failure.
    """
    try:
        return json.loads(_DAO_DETAILS.read_text())
    except Exception:
        return {}


def _solana_rpc(network: str, method: str, params: list[Any] | None = None) -> dict[str, Any]:
    """Call the configured Solana RPC endpoint.

    Args:
        network: Solana network name.
        method: JSON-RPC method name.
        params: Optional JSON-RPC params.

    Returns:
        dict[str, Any]: Parsed JSON-RPC response.
    """
    url = _SOLANA_RPCS.get(network, _SOLANA_RPCS["devnet"])
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params or []}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def _get_fee_payer(network: str, recipient_address: str | None = None) -> tuple[str | None, str]:
    """Determine which wallet should pay gas.

    Args:
        network: Solana network name.
        recipient_address: Optional recipient address to inspect for SOL balance.

    Returns:
        tuple[str | None, str]: Fee payer keypair path and label.
    """
    if recipient_address:
        try:
            r = _solana_rpc(network, "getBalance", [recipient_address])
            bal = r.get("result", {}).get("value", 0) / 1e9
            if bal >= _MIN_SOL_FOR_GAS:
                return None, "user"
        except Exception:
            pass
    try:
        r = _solana_rpc(network, "getBalance", [_get_wallet_pubkey()])
        bal = r.get("result", {}).get("value", 0) / 1e9
        if bal >= _MIN_SOL_FOR_GAS:
            return str(_SOLANA_KEYPAIR), "ai_wallet"
    except Exception:
        pass
    return str(_REGISTRATION_BASKET_KEYPAIR), "dao_basket"


def _load_onboarding() -> dict[str, Any]:
    """Load onboarding data from disk.

    Returns:
        dict[str, Any]: Onboarding store.
    """
    try:
        return json.loads(_ONBOARDING_FILE.read_text())
    except Exception:
        return {}


def _save_onboarding(data: dict[str, Any]) -> None:
    """Persist onboarding data.

    Args:
        data: Onboarding store to persist.
    """
    _ONBOARDING_FILE.parent.mkdir(parents=True, exist_ok=True)
    _ONBOARDING_FILE.write_text(json.dumps(data, indent=2))


def _derive_symbiotic_pda(human_pubkey_str: str) -> str:
    """Derive the Symbiotic PDA for a human wallet.

    Args:
        human_pubkey_str: Human wallet public key.

    Returns:
        str: Derived PDA address.
    """
    from solders.pubkey import Pubkey as _Pubkey

    program_id = _Pubkey.from_string(_SYMBIOTIC_PROGRAM_ID)
    human = _Pubkey.from_string(human_pubkey_str)
    seeds = [b"symbiotic", bytes(human), bytes([0])]
    pda, _bump = _Pubkey.find_program_address(seeds, program_id)
    return str(pda)


def _wallet_has_nft(address: str, nft_type: str, network: str = "devnet") -> bool:
    """Check whether a wallet or its PDA holds a known NFT.

    Args:
        address: Human wallet address.
        nft_type: NFT type key.
        network: Solana network name.

    Returns:
        bool: True if the NFT is detected.
    """
    checked_addresses = []
    try:
        pda = _derive_symbiotic_pda(address)
        checked_addresses.append(pda)
    except Exception:
        pass
    checked_addresses.append(address)

    if NFTMinter and SolanaWallet:
        try:
            minter = NFTMinter(SolanaWallet(network=network))
            for acct in checked_addresses:
                try:
                    found = minter.check_wallet_has_nft(acct, nft_type)
                    if found.get("has_nft"):
                        return True
                except Exception:
                    continue
        except Exception:
            pass

    onboarding = _load_onboarding().get(address, {})
    key_map = {
        "identity": ("identityNftMinted", "identityNftMint", "identityNft"),
        "alpha_tester": ("alphaNftMinted", "alphaNftMint", "alphaNft"),
        "symbiotic_license": ("licenseSigned", "licenseNft"),
        "manifesto": ("manifestoSigned", "manifestoNft"),
    }
    for key in key_map.get(nft_type, ()):
        if onboarding.get(key):
            return True
    return False


def _require_identity_nft(wallet_address: str) -> bool:
    """Require an identity NFT for a wallet.

    Args:
        wallet_address: Wallet public key.

    Returns:
        bool: True when the wallet has an identity NFT.
    """
    return _wallet_has_nft(wallet_address, "identity")


def _load_daily_claims() -> dict[str, Any]:
    """Load daily claim records.

    Returns:
        dict[str, Any]: Daily claim store.
    """
    try:
        return json.loads(_DAILY_CLAIMS_FILE.read_text())
    except Exception:
        return {}


def _save_daily_claims(data: dict[str, Any]) -> None:
    """Persist daily claim records.

    Args:
        data: Daily claim store to persist.
    """
    _DAILY_CLAIMS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _DAILY_CLAIMS_FILE.write_text(json.dumps(data, indent=2))


def _load_rct_caps() -> dict[str, Any]:
    """Load RCT cap state.

    Returns:
        dict[str, Any]: RCT cap tracking store.
    """
    try:
        return json.loads(_RCT_CAPS_FILE.read_text())
    except Exception:
        return {"wallets_yearly": {}, "daily": []}


def _save_rct_caps(caps: dict[str, Any]) -> None:
    """Persist RCT cap state.

    Args:
        caps: RCT cap tracking store.
    """
    _RCT_CAPS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _RCT_CAPS_FILE.write_text(json.dumps(caps, indent=2))


def _short_wallet(addr: str | None) -> str:
    """Shorten a wallet string for display.

    Args:
        addr: Wallet address.

    Returns:
        str: Shortened wallet display string.
    """
    if not addr:
        return ""
    return f"{addr[:6]}...{addr[-4:]}" if len(addr) > 10 else addr


def _is_valid_pubkey(addr: str) -> bool:
    """Validate a Solana public key string.

    Args:
        addr: Wallet address to validate.

    Returns:
        bool: True when the address parses as a pubkey.
    """
    try:
        from solders.pubkey import Pubkey as _Pubkey

        _Pubkey.from_string(addr)
        return True
    except Exception:
        return False


def _check_rct_cap(recipient: str, amount_human: float) -> tuple[bool, str]:
    """Check whether an RCT mint stays inside configured caps.

    Args:
        recipient: Human wallet address.
        amount_human: Human-readable RCT amount.

    Returns:
        tuple[bool, str]: Whether the mint is allowed and the reason.
    """
    caps = _load_rct_caps()
    year = str(datetime.now(timezone.utc).year)
    yearly = caps.get("wallets_yearly", {}).get(recipient, {}).get(year, 0)
    if yearly + amount_human > _RCT_MAX_PER_WALLET_YEAR:
        return False, f"Annual cap: {yearly}/{_RCT_MAX_PER_WALLET_YEAR} $RCT ({year})"
    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(hours=24)).isoformat()
    daily_total = sum(e["amount"] for e in caps.get("daily", []) if e["ts"] > cutoff)
    holder_count = caps.get("holder_count", 10)
    daily_cap = max(_RCT_DAILY_FLOOR, min(_RCT_DAILY_MAX, _RCT_DAILY_PER_HOLDER * holder_count))
    if daily_total + amount_human > daily_cap:
        return False, f"Global daily cap: {daily_total}/{daily_cap} $RCT"
    return True, "ok"


def _record_rct_mint(recipient: str, amount_human: float) -> None:
    """Record an RCT mint for cap enforcement.

    Args:
        recipient: Human wallet address.
        amount_human: Human-readable RCT amount.
    """
    caps = _load_rct_caps()
    year = str(datetime.now(timezone.utc).year)
    caps.setdefault("wallets_yearly", {})
    caps["wallets_yearly"].setdefault(recipient, {})
    caps["wallets_yearly"][recipient][year] = caps["wallets_yearly"][recipient].get(year, 0) + amount_human
    now_iso = datetime.now(timezone.utc).isoformat()
    caps.setdefault("daily", [])
    caps["daily"].append({"ts": now_iso, "recipient": recipient, "amount": amount_human})
    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    caps["daily"] = [e for e in caps["daily"] if e["ts"] > cutoff]
    _save_rct_caps(caps)


def _load_nft_registry() -> dict[str, str]:
    """Load the NFT registry.

    Returns:
        dict[str, str]: Mapping of mint address to NFT type.
    """
    try:
        return json.loads(_NFT_REGISTRY_FILE.read_text())
    except Exception:
        return {}


def _save_nft_registry(data: dict[str, str]) -> None:
    """Persist the NFT registry.

    Args:
        data: Mapping of mint address to NFT type.
    """
    _NFT_REGISTRY_FILE.parent.mkdir(parents=True, exist_ok=True)
    _NFT_REGISTRY_FILE.write_text(json.dumps(data, indent=2))


def get_wallet_shared(name: str) -> Any:
    """Fetch a shared server dependency injected into app config.

    Args:
        name: Shared dependency key.

    Returns:
        Any: Shared dependency value.
    """
    shared = current_app.config.get("WALLET_SHARED", {})
    return shared[name]
