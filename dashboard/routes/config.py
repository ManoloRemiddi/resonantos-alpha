"""Shared dashboard configuration and Solana constants."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

DASHBOARD_DIR: Path = Path(__file__).resolve().parent.parent
REPO_DIR: Path = DASHBOARD_DIR.parent

OPENCLAW_HOME: Path = Path.home() / ".openclaw"
OPENCLAW_CONFIG: Path = OPENCLAW_HOME / "openclaw.json"
BUILTIN_SKILLS_DIR: Path = Path("/opt/homebrew/lib/node_modules/openclaw/skills")
CUSTOM_SKILLS_DIR: Path = OPENCLAW_HOME / "workspace" / "skills"
SSOT_ACCESS_FILE: Path = Path("~/.openclaw/ssot_access.json").expanduser()
WORKSPACE: Path = OPENCLAW_HOME / "workspace"
SSOT_ROOT: Path = REPO_DIR / "ssot"
AGENTS_DIR: Path = OPENCLAW_HOME / "agents"
EXTENSIONS_DIR: Path = OPENCLAW_HOME / "extensions"
RMEMORY_DIR: Path = WORKSPACE / "r-memory"
RMEMORY_LOG: Path = RMEMORY_DIR / "r-memory.log"
RMEMORY_CONFIG: Path = RMEMORY_DIR / "config.json"
R_AWARENESS_LOG: Path = WORKSPACE / "r-awareness" / "r-awareness.log"

_CONFIG_FILE: Path = DASHBOARD_DIR / "config.json"
_CFG: dict[str, Any] = {}
if _CONFIG_FILE.exists():
    try:
        _CFG = json.loads(_CONFIG_FILE.read_text())
    except Exception:
        _CFG = {}

_toolkit_candidates: list[Path] = [
    REPO_DIR / "solana-toolkit",
]
for _toolkit_path in _toolkit_candidates:
    if _toolkit_path.exists():
        sys.path.insert(0, str(_toolkit_path))
        break

try:
    from nft_minter import NFTMinter
    from token_manager import TokenManager
    from wallet import SolanaWallet
except ImportError:
    NFTMinter = None
    TokenManager = None
    SolanaWallet = None

try:
    from protocol_nft_minter import PROTOCOL_NFTS, ProtocolNFTMinter
except ImportError:
    ProtocolNFTMinter = None
    PROTOCOL_NFTS = {}


def _resolve_repo_path(path_from_cfg: str | None, default_rel: str) -> Path:
    """Resolve a repo-relative config path against the current checkout."""
    raw_path = Path(path_from_cfg or default_rel).expanduser()
    if raw_path.is_absolute():
        return raw_path
    return REPO_DIR / raw_path


_SOLANA_KEYPAIR: Path = Path(_CFG.get("solana", {}).get("keypairPath", "~/.config/solana/id.json")).expanduser()
_DAO_DETAILS: Path = _resolve_repo_path(_CFG.get("paths", {}).get("daoDetails"), "ssot/L2/DAO_DETAILS.json")
_REGISTRATION_BASKET_KEYPAIR: Path = Path(
    _CFG.get("solana", {}).get("daoRegistrationBasketKeypairPath", "~/.config/solana/dao-registration-basket.json")
).expanduser()
_MIN_SOL_FOR_GAS: float = _CFG.get("solana", {}).get("minSolForGas", 0.01)

_RCT_MINT: str = _CFG.get("tokens", {}).get("RCT_MINT", "2z2GEVqhTVUc6Pb3pzmVTTyBh2BeMHqSw1Xrej8KVUKG")
_RES_MINT: str = _CFG.get("tokens", {}).get("RES_MINT", "DiZuWvmQ6DEwsfz7jyFqXCsMfnJiMVahCj3J5MxkdV5N")

_SOLANA_RPCS: dict[str, str] = _CFG.get("solana", {}).get("rpcs") or {
    "devnet": "https://api.devnet.solana.com",
    "testnet": "https://api.testnet.solana.com",
    "mainnet-beta": "https://api.mainnet-beta.solana.com",
}

_REX_MINTS: dict[str, str] = {
    "GOV": "7Zxr6WLPdo5owVwhkuPUKSVRMHGknadBesQExmBSsKpj",
    "FIN": "zwwrrG6neRMwLY76oZfF41BtLZ7kmqWXpqKCCzDkbaL",
    "COM": "7sybHSXWfxFeoUoTv78veNZHRkd4UeNhCt3pmkeJU43S",
    "CRE": "8HQF2jTRouqTcTmzJctGaTPKXkGEk2iyXBmMZ2mrRyKV",
    "TEC": "9V4oLeX77iFSjr1dnHjKXsAWCNhGcADo6L9CH37zLnBF",
}
_REX_DISPLAY: dict[str, str] = {
    "GOV": "Governance Contribution",
    "FIN": "Financial Contribution",
    "COM": "Community Contribution",
    "CRE": "Creative Contribution",
    "TEC": "Technical Contribution",
}

_rct_caps_cfg: dict[str, Any] = _CFG.get("rctCaps", {})
_RCT_MAX_PER_WALLET_YEAR: int = _rct_caps_cfg.get("maxPerWalletYear", 10_000)
_RCT_DAILY_PER_HOLDER: int = _rct_caps_cfg.get("dailyPerHolder", 30)
_RCT_DAILY_FLOOR: int = _rct_caps_cfg.get("dailyFloor", 300)
_RCT_DAILY_MAX: int = _rct_caps_cfg.get("dailyMax", 100_000)
_RCT_DECIMALS: int = _rct_caps_cfg.get("decimals", 9)
_LEVEL_THRESHOLDS: list[int] = [0, 10, 50, 150, 400, 1000, 2500, 6000, 15000, 40000]

_SYMBIOTIC_PROGRAM_ID: str = _CFG.get("programs", {}).get(
    "SYMBIOTIC_PROGRAM_ID", "HMthR7AStR3YKJ4m8GMveWx5dqY3D2g2cfnji7VdcVoG"
)
_MARKETPLACE_PROGRAM_ID: str = _CFG.get("programs", {}).get(
    "MARKETPLACE_PROGRAM_ID",
    "5wpGj4EG6J5uEqozLqUyHzEQbU26yjaL5aUE5FwBiYe5",
)

_paths_cfg: dict[str, Any] = _CFG.get("paths", {})


def _resolve_data_file(path_from_cfg: str | None, default_rel: str) -> Path:
    """Resolve the preferred on-disk location for a dashboard data file.

    Check the configured relative path against the workspace checkout first and
    then the dashboard directory fallback. Return the last candidate even when
    neither path currently exists so callers still receive a writable target.

    Args:
        path_from_cfg: Relative path from config, if present.
        default_rel: Default relative path inside the dashboard repo.

    Called by:
        Module-level data file constant initialization.
    Side effects:
        None.

    Returns:
        Path: Resolved data file path to read from or write to.
    """
    rel = path_from_cfg or default_rel
    candidates = [
        REPO_DIR / rel,
        DASHBOARD_DIR / rel,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[-1]


_RCT_CAPS_FILE: Path = _resolve_data_file(_paths_cfg.get("rctCapsFile"), "data/rct_caps.json")
_ONBOARDING_FILE: Path = _resolve_data_file(_paths_cfg.get("onboardingFile"), "data/onboarding.json")
_DAILY_CLAIMS_FILE: Path = _resolve_data_file(_paths_cfg.get("dailyClaims"), "data/daily_claims.json")
_NFT_REGISTRY_FILE: Path = _resolve_data_file(_paths_cfg.get("nftRegistry"), "data/nft_registry.json")
_BOUNTIES_FILE: Path = DASHBOARD_DIR / "data" / "bounties.json"
_TRIBES_FILE: Path = DASHBOARD_DIR / "data" / "tribes.json"
_PROFILES_FILE: Path = DASHBOARD_DIR / "data" / "profiles.json"
