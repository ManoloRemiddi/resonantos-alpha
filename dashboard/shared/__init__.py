"""
Shared utilities for ResonantOS Dashboard.
Platform detection, path resolution, config loading, and helper functions.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

IS_WINDOWS = sys.platform.startswith("win")
IS_MAC = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")

def is_windows():
    return IS_WINDOWS

def is_mac():
    return IS_MAC

def is_linux():
    return IS_LINUX

def open_file_using_system(filepath):
    """Open a file with the system default application, cross-platform."""
    import webbrowser
    filepath = Path(filepath)
    if not filepath.exists():
        return False
    try:
        if IS_WINDOWS:
            os.startfile(str(filepath))
        elif IS_MAC:
            subprocess.Popen(["open", str(filepath)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.Popen(["xdg-open", str(filepath)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except:
        return False

def restart_openclaw_gateway():
    """Restart the OpenClaw gateway, cross-platform."""
    try:
        if IS_WINDOWS:
            subprocess.run(["taskkill", "/F", "/IM", "node.exe", "/T"], capture_output=True, timeout=5)
            time.sleep(1)
            subprocess.Popen(["npm", "start"], cwd=str(Path.home() / ".openclaw"))
        elif IS_MAC:
            subprocess.run(["launchctl", "stop", "com.openclaw.gateway"], capture_output=True, timeout=5)
            subprocess.run(["launchctl", "start", "com.openclaw.gateway"], capture_output=True, timeout=5)
        else:
            subprocess.run(["systemctl", "restart", "openclaw-gateway"], capture_output=True, timeout=5)
    except:
        pass

def get_openclaw_skills_dir():
    """Find OpenClaw's builtin skills directory, cross-platform."""
    try:
        result = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            skills = Path(result.stdout.strip()) / "openclaw" / "skills"
            if skills.exists():
                return skills
    except:
        pass
    for base in ["/opt/homebrew", "/usr/local", "/usr"]:
        skills = Path(base) / "lib" / "node_modules" / "openclaw" / "skills"
        if skills.exists():
            return skills
    return None

def resolve_data_file(path_from_cfg: str, default_rel: str, dashboard_dir: Path) -> Path:
    """Resolve a data file path, checking multiple candidates."""
    candidates = [
        dashboard_dir / default_rel,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[-1]

class Config:
    """Centralized configuration loader."""
    _instance = None
    _cfg = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load()
        return cls._instance

    def _load(self):
        dashboard_dir = Path(__file__).resolve().parent
        config_file = dashboard_dir / "config.json"
        if config_file.exists():
            try:
                self._cfg = json.loads(config_file.read_text())
            except Exception:
                pass

    def get(self, *keys, default=None):
        val = self._cfg
        for k in keys:
            if isinstance(val, dict):
                val = val.get(k)
            else:
                return default
            if val is None:
                return default
        return val

def load_config():
    """Load dashboard config.json."""
    return Config()

OPENCLAW_HOME = Path(os.getenv("OPENCLAW_HOME", str(Path.home() / ".openclaw"))).expanduser()
OPENCLAW_CONFIG = OPENCLAW_HOME / "openclaw.json"
BUILTIN_SKILLS_DIR = get_openclaw_skills_dir()
CUSTOM_SKILLS_DIR = OPENCLAW_HOME / "workspace" / "skills"
SSOT_ACCESS_FILE = Path("~/.openclaw/ssot_access.json").expanduser()
WORKSPACE = OPENCLAW_HOME / "workspace"
SSOT_ROOT = WORKSPACE / "resonantos-alpha" / "ssot"
AGENTS_DIR = OPENCLAW_HOME / "agents"
EXTENSIONS_DIR = OPENCLAW_HOME / "extensions"
RMEMORY_DIR = WORKSPACE / "r-memory"
RMEMORY_LOG = RMEMORY_DIR / "r-memory.log"
RMEMORY_CONFIG = RMEMORY_DIR / "config.json"
R_AWARENESS_LOG = WORKSPACE / "r-awareness" / "r-awareness.log"
DASHBOARD_DIR = Path(__file__).resolve().parent.parent

_cfg = Config()._cfg

_SOLANA_KEYPAIR = Path(_cfg.get("solana", {}).get("keypairPath", "~/.config/solana/id.json")).expanduser()
_RCT_MINT = _cfg.get("tokens", {}).get("RCT_MINT", "2z2GEVqhTVUc6Pb3pzmVTTyBh2BeMHqSw1Xrej8KVUKG")
_RES_MINT = _cfg.get("tokens", {}).get("RES_MINT", "DiZuWvmQ6DEwsfz7jyFqXCsMfnJiMVahCj3J5MxkdV5N")

_SOLANA_RPCS = _cfg.get("solana", {}).get("rpcs") or {
    "devnet": "https://api.devnet.solana.com",
    "testnet": "https://api.testnet.solana.com",
    "mainnet-beta": "https://api.mainnet-beta.solana.com",
}

_RCT_CAPS = {
    "maxPerWalletYear": _cfg.get("rctCaps", {}).get("maxPerWalletYear", 10_000),
    "dailyPerHolder": _cfg.get("rctCaps", {}).get("dailyPerHolder", 30),
    "dailyFloor": _cfg.get("rctCaps", {}).get("dailyFloor", 300),
    "dailyMax": _cfg.get("rctCaps", {}).get("dailyMax", 100_000),
    "decimals": _cfg.get("rctCaps", {}).get("decimals", 9),
}
