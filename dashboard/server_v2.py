#!/usr/bin/env python3
"""
ResonantOS Dashboard v2 — Clean OpenClaw-native server.
Connects to OpenClaw gateway via WebSocket for real-time data.
No legacy Clawdbot/Watchtower dependencies.
"""

import json
import os
import re
import subprocess
import threading
import time
import hashlib
import traceback
import urllib.request
import urllib.error
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_from_directory
from flask_cors import CORS

# Derive repo root from this script's location (works for any clone name)
_DASHBOARD_SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = _DASHBOARD_SCRIPT_DIR.parent  # <repo>/dashboard/../ = <repo>

# Solana wallet integration imports
sys.path.insert(0, str(REPO_ROOT / "solana-toolkit"))
try:
    from nft_minter import NFTMinter
    from token_manager import TokenManager
    from wallet import SolanaWallet
except ImportError:
    # Graceful fallback if solana-toolkit not available
    NFTMinter = None
    TokenManager = None
    SolanaWallet = None

try:
    from protocol_nft_minter import ProtocolNFTMinter, PROTOCOL_NFTS
except ImportError:
    ProtocolNFTMinter = None
    PROTOCOL_NFTS = {}

# ---------------------------------------------------------------------------
# Paths & Config
# ---------------------------------------------------------------------------

OPENCLAW_HOME = Path.home() / ".openclaw"
OPENCLAW_CONFIG = OPENCLAW_HOME / "openclaw.json"
WORKSPACE = OPENCLAW_HOME / "workspace"
# SSoT root: prefer ssot/, fall back to ssot-template/ for alpha users
_ssot_candidate = REPO_ROOT / "ssot"
SSOT_ROOT = _ssot_candidate if _ssot_candidate.exists() else REPO_ROOT / "ssot-template"
AGENTS_DIR = OPENCLAW_HOME / "agents"
EXTENSIONS_DIR = OPENCLAW_HOME / "extensions"
RMEMORY_DIR = WORKSPACE / "r-memory"
RMEMORY_LOG = RMEMORY_DIR / "r-memory.log"
RMEMORY_CONFIG = RMEMORY_DIR / "config.json"
R_AWARENESS_LOG = WORKSPACE / "r-awareness" / "r-awareness.log"
LOGICIAN_ROOT = REPO_ROOT / "logician"
LOGICIAN_RULES_DIR = LOGICIAN_ROOT / "rules"
LOGICIAN_CONFIG_DIR = LOGICIAN_ROOT / "config"
LOGICIAN_ENABLED_RULES_FILE = LOGICIAN_CONFIG_DIR / "enabled_rules.json"

# --- Load config.json (with hardcoded fallbacks for backward compatibility) ---
_DASHBOARD_DIR = _DASHBOARD_SCRIPT_DIR  # reuse from above
_CONFIG_FILE = _DASHBOARD_DIR / "config.json"
_CFG = {}
if _CONFIG_FILE.exists():
    try:
        _CFG = json.loads(_CONFIG_FILE.read_text())
    except Exception:
        pass

# Solana wallet integration
_SOLANA_KEYPAIR = Path(_CFG.get("solana", {}).get("keypairPath", "~/.config/solana/id.json")).expanduser()
_DAO_DETAILS = REPO_ROOT / _CFG.get("paths", {}).get("daoDetails", "ssot/L2/DAO_DETAILS.json")
_REGISTRATION_BASKET_KEYPAIR = Path(_CFG.get("solana", {}).get("daoRegistrationBasketKeypairPath", "~/.config/solana/dao-registration-basket.json")).expanduser()
_MIN_SOL_FOR_GAS = _CFG.get("solana", {}).get("minSolForGas", 0.01)

_RCT_MINT = _CFG.get("tokens", {}).get("RCT_MINT", "2z2GEVqhTVUc6Pb3pzmVTTyBh2BeMHqSw1Xrej8KVUKG")
_RES_MINT = _CFG.get("tokens", {}).get("RES_MINT", "DiZuWvmQ6DEwsfz7jyFqXCsMfnJiMVahCj3J5MxkdV5N")

_SOLANA_RPCS = {
    "devnet": "https://api.devnet.solana.com",
    "testnet": "https://api.testnet.solana.com",
    "mainnet-beta": "https://api.mainnet-beta.solana.com",
}

_REX_MINTS = {
    "GOV": "7Zxr6WLPdo5owVwhkuPUKSVRMHGknadBesQExmBSsKpj",
    "FIN": "zwwrrG6neRMwLY76oZfF41BtLZ7kmqWXpqKCCzDkbaL",
    "COM": "7sybHSXWfxFeoUoTv78veNZHRkd4UeNhCt3pmkeJU43S",
    "CRE": "8HQF2jTRouqTcTmzJctGaTPKXkGEk2iyXBmMZ2mrRyKV",
    "TEC": "9V4oLeX77iFSjr1dnHjKXsAWCNhGcADo6L9CH37zLnBF",
}
_REX_DISPLAY = {
    "GOV": "Governance Contribution",
    "FIN": "Financial Contribution",
    "COM": "Community Contribution",
    "CRE": "Creative Contribution",
    "TEC": "Technical Contribution",
}

# RCT Safety Caps (from config.json or defaults)
_rct_caps_cfg = _CFG.get("rctCaps", {})
_RCT_MAX_PER_WALLET_YEAR = _rct_caps_cfg.get("maxPerWalletYear", 10_000)
_RCT_DAILY_PER_HOLDER = _rct_caps_cfg.get("dailyPerHolder", 30)
_RCT_DAILY_FLOOR = _rct_caps_cfg.get("dailyFloor", 300)
_RCT_DAILY_MAX = _rct_caps_cfg.get("dailyMax", 100_000)
_RCT_DECIMALS = _rct_caps_cfg.get("decimals", 9)
_paths_cfg = _CFG.get("paths", {})
_RCT_CAPS_FILE = REPO_ROOT / _paths_cfg.get("rctCapsFile", "data/rct_caps.json")
_ONBOARDING_FILE = REPO_ROOT / _paths_cfg.get("onboardingFile", "data/onboarding.json")
_DAILY_CLAIMS_FILE = REPO_ROOT / "data" / "daily_claims.json"

# Level thresholds for reputation
_LEVEL_THRESHOLDS = [0, 10, 50, 150, 400, 1000, 2500, 6000, 15000, 40000]

# Gateway WS config
GW_HOST = "127.0.0.1"
GW_PORT = 18789
GW_WS_URL = f"ws://{GW_HOST}:{GW_PORT}"

# Read auth token
def _read_gw_token():
    try:
        cfg = json.loads(OPENCLAW_CONFIG.read_text())
        return cfg.get("gateway", {}).get("auth", {}).get("token", "")
    except Exception:
        return ""

GW_TOKEN = _read_gw_token()

# Solana wallet helper functions
def _get_wallet_pubkey():
    """Read AI wallet public key from keypair file."""
    try:
        import json as _j
        from solders.keypair import Keypair as _Kp
        data = _j.loads(_SOLANA_KEYPAIR.read_text())
        kp = _Kp.from_bytes(bytes(data))
        return str(kp.pubkey())
    except Exception:
        return None

def _get_dao_details():
    try:
        return json.loads(_DAO_DETAILS.read_text())
    except Exception:
        return {}

def _solana_rpc(network, method, params=None):
    url = _SOLANA_RPCS.get(network, _SOLANA_RPCS["devnet"])
    body = json.dumps({"jsonrpc":"2.0","id":1,"method":method,"params":params or []}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())

def _get_fee_payer(network, recipient_address=None):
    """Determine who pays gas. Returns (keypair_path, label)."""
    # Check if user has enough SOL
    if recipient_address:
        try:
            r = _solana_rpc(network, "getBalance", [recipient_address])
            bal = r.get("result",{}).get("value",0) / 1e9
            if bal >= _MIN_SOL_FOR_GAS:
                return None, "user"
        except Exception:
            pass
    # Check AI wallet
    try:
        r = _solana_rpc(network, "getBalance", [_get_wallet_pubkey()])
        bal = r.get("result",{}).get("value",0) / 1e9
        if bal >= _MIN_SOL_FOR_GAS:
            return str(_SOLANA_KEYPAIR), "ai_wallet"
    except Exception:
        pass
    # Fall back to basket
    return str(_REGISTRATION_BASKET_KEYPAIR), "dao_basket"

def _load_onboarding():
    try: return json.loads(_ONBOARDING_FILE.read_text())
    except Exception: return {}

def _save_onboarding(data):
    _ONBOARDING_FILE.parent.mkdir(parents=True, exist_ok=True)
    _ONBOARDING_FILE.write_text(json.dumps(data, indent=2))

def _require_identity_nft(wallet_address):
    """Return True if wallet holds Identity NFT, else False."""
    onboarding = _load_onboarding()
    return onboarding.get(wallet_address, {}).get("identityNftMinted", False)

def _load_daily_claims():
    try: return json.loads(_DAILY_CLAIMS_FILE.read_text())
    except Exception: return {}

def _save_daily_claims(data):
    _DAILY_CLAIMS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _DAILY_CLAIMS_FILE.write_text(json.dumps(data, indent=2))

def _load_rct_caps():
    try: return json.loads(_RCT_CAPS_FILE.read_text())
    except Exception: return {"wallets_yearly": {}, "daily": []}

def _save_rct_caps(caps):
    _RCT_CAPS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _RCT_CAPS_FILE.write_text(json.dumps(caps, indent=2))

def _check_rct_cap(recipient, amount_human):
    caps = _load_rct_caps()
    year = str(datetime.now(timezone.utc).year)
    # Per-wallet annual
    yearly = caps.get("wallets_yearly", {}).get(recipient, {}).get(year, 0)
    if yearly + amount_human > _RCT_MAX_PER_WALLET_YEAR:
        return False, f"Annual cap: {yearly}/{_RCT_MAX_PER_WALLET_YEAR} $RCT ({year})"
    # Daily global
    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(hours=24)).isoformat()
    daily_total = sum(e["amount"] for e in caps.get("daily", []) if e["ts"] > cutoff)
    # Dynamic daily cap based on holder count
    holder_count = caps.get("holder_count", 10)
    daily_cap = max(_RCT_DAILY_FLOOR, min(_RCT_DAILY_MAX, _RCT_DAILY_PER_HOLDER * holder_count))
    if daily_total + amount_human > daily_cap:
        return False, f"Global daily cap: {daily_total}/{daily_cap} $RCT"
    return True, "ok"

def _record_rct_mint(recipient, amount_human):
    caps = _load_rct_caps()
    year = str(datetime.now(timezone.utc).year)
    if "wallets_yearly" not in caps: caps["wallets_yearly"] = {}
    if recipient not in caps["wallets_yearly"]: caps["wallets_yearly"][recipient] = {}
    caps["wallets_yearly"][recipient][year] = caps["wallets_yearly"][recipient].get(year, 0) + amount_human
    now_iso = datetime.now(timezone.utc).isoformat()
    if "daily" not in caps: caps["daily"] = []
    caps["daily"].append({"ts": now_iso, "recipient": recipient, "amount": amount_human})
    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    caps["daily"] = [e for e in caps["daily"] if e["ts"] > cutoff]
    _save_rct_caps(caps)

# ---------------------------------------------------------------------------
# Gateway WebSocket Client (background thread)
# ---------------------------------------------------------------------------

try:
    import websocket  # pip install websocket-client
except ImportError:
    websocket = None

class GatewayClient:
    """Persistent WS connection to OpenClaw gateway. Caches latest state."""

    def __init__(self):
        self.connected = False
        self.conn_id = None
        self.health = {}
        self.features = {}
        self.agents_snapshot = []
        self.sessions_snapshot = []
        self.last_tick = 0
        self.last_health_ts = 0
        self.error = None
        self._ws = None
        self._lock = threading.Lock()
        self._msg_id = 0
        self._pending = {}  # id -> threading.Event + result

    def _next_id(self):
        self._msg_id += 1
        return f"r{self._msg_id}"

    def start(self):
        t = threading.Thread(target=self._run, daemon=True)
        t.start()

    def _run(self):
        while True:
            try:
                self._connect()
            except Exception as e:
                self.connected = False
                self.error = str(e)
            time.sleep(3)  # reconnect delay

    def _send_connect(self, ws, nonce=None):
        connect_msg = {
            "type": "req", "id": "c0", "method": "connect",
            "params": {
                "auth": {"token": GW_TOKEN},
                "minProtocol": 3, "maxProtocol": 3,
                "role": "operator",
                "scopes": ["operator.admin"],
                "caps": [],
                "client": {
                    "id": "gateway-client",
                    "mode": "backend",
                    "version": "2.0.0",
                    "platform": "darwin"
                }
            }
        }
        ws.send(json.dumps(connect_msg))

    def _connect(self):
        if websocket is None:
            self.error = "websocket-client not installed (pip install websocket-client)"
            import time; time.sleep(30)
            return
        ws = websocket.WebSocket()
        ws.settimeout(10)
        ws.connect(GW_WS_URL)
        self._ws = ws

        # Wait for challenge event, then send connect with nonce
        challenge_received = False
        ws.settimeout(5)
        try:
            raw = ws.recv()
            if raw:
                msg = json.loads(raw)
                if msg.get("type") == "event" and msg.get("event") == "connect.challenge":
                    nonce = msg.get("payload", {}).get("nonce")
                    self._send_connect(ws, nonce)
                    challenge_received = True
                else:
                    self._handle(msg)
        except Exception:
            pass

        if not challenge_received:
            # Fallback: send connect without nonce (older protocol)
            self._send_connect(ws)

        # Read loop
        ws.settimeout(60)
        while True:
            try:
                raw = ws.recv()
                if not raw:
                    break
                msg = json.loads(raw)
                self._handle(msg)
            except websocket.WebSocketTimeoutException:
                # Send ping to keep alive
                try:
                    ws.ping()
                except Exception:
                    break
            except Exception:
                break

        self.connected = False
        try:
            ws.close()
        except Exception:
            pass

    def _handle(self, msg):
        mtype = msg.get("type")

        if mtype == "res":
            mid = msg.get("id")
            # Handle connect response
            if mid == "c0":
                if msg.get("ok"):
                    self.connected = True
                    self.error = None
                    payload = msg.get("payload", {})
                    self.conn_id = payload.get("server", {}).get("connId")
                    self.features = payload.get("features", {})
                    # Extract agents from snapshot
                    snap = payload.get("snapshot", {})
                    # Health data is in the snapshot too
                else:
                    self.error = msg.get("error", {}).get("message", "connect failed")

            # Handle pending request responses
            if mid in self._pending:
                evt, _ = self._pending[mid]
                self._pending[mid] = (evt, msg)
                evt.set()

        elif mtype == "event":
            event = msg.get("event")
            payload = msg.get("payload", {})

            if event == "tick":
                self.last_tick = payload.get("ts", 0)

            elif event == "health":
                with self._lock:
                    self.health = payload
                    self.last_health_ts = payload.get("ts", 0)

            elif event == "connect.challenge":
                pass  # Handled by protocol

    def request(self, method, params=None, timeout=10):
        """Send a request and wait for response."""
        if not self.connected or not self._ws:
            return {"ok": False, "error": "not connected"}

        mid = self._next_id()
        evt = threading.Event()
        self._pending[mid] = (evt, None)

        try:
            msg = {"type": "req", "id": mid, "method": method}
            if params:
                msg["params"] = params
            self._ws.send(json.dumps(msg))
            evt.wait(timeout=timeout)
            _, result = self._pending.pop(mid, (None, None))
            if result is None:
                return {"ok": False, "error": "timeout"}
            return result
        except Exception as e:
            self._pending.pop(mid, None)
            return {"ok": False, "error": str(e)}


# Singleton
gw = GatewayClient()

# ---------------------------------------------------------------------------
# Flask App
# ---------------------------------------------------------------------------

app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.jinja_env.auto_reload = True
CORS(app)


def _get_version():
    """Derive version from git commit count: v3.<count>."""
    try:
        import subprocess
        count = subprocess.check_output(
            ["git", "rev-list", "--count", "HEAD"],
            cwd=os.path.dirname(__file__), stderr=subprocess.DEVNULL
        ).decode().strip()
        return f"v3.{count}"
    except Exception:
        return "v3.0"


@app.context_processor
def inject_version():
    return {"resonantos_version": _get_version()}


# ---------------------------------------------------------------------------
# R-Memory Data Helpers
# ---------------------------------------------------------------------------

import re as _re
import glob as _glob

def _rmem_config():
    """Read r-memory/config.json."""
    try:
        return json.loads(RMEMORY_CONFIG.read_text())
    except Exception:
        return {"compressTrigger": 36000, "evictTrigger": 80000, "blockSize": 4000}

def _rmem_camouflage():
    """Read r-memory/camouflage.json."""
    try:
        return json.loads((RMEMORY_DIR / "camouflage.json").read_text())
    except Exception:
        return {"enabled": False}

def _rmem_effective_models():
    """Resolve the actual runtime models for compression and narrative.
    Config overrides (narrativeModel) take priority over camouflage routing."""
    cfg = _rmem_config()
    camo = _rmem_camouflage()
    base_model = cfg.get("compressionModel", "anthropic/claude-haiku-4-5")

    # Config-level overrides take priority over camouflage routing
    narrative_override = cfg.get("narrativeModel")

    if camo.get("enabled") and camo.get("elements", {}).get("trafficSegregation"):
        pref = camo.get("preferredBackgroundProvider", "openai")
        bg_models = camo.get("backgroundModels", {})
        compression_model = bg_models.get(pref, base_model) if camo.get("routeCompressionOffAnthro") else base_model
        narrative_model = narrative_override or (bg_models.get(f"{pref}-narrative", bg_models.get(pref, base_model)) if camo.get("routeNarrativeOffAnthro") else base_model)
    else:
        compression_model = base_model
        narrative_model = narrative_override or base_model

    return {
        "compression": compression_model,
        "narrative": narrative_model,
    }

def _rmem_history_blocks(session_id=None):
    """Read compressed blocks from history-{sessionId}.json files.
    If session_id given, only that file. Otherwise aggregate all.
    Returns list of block dicts with compressed, tokensRaw, tokensCompressed, timestamp."""
    pattern = str(RMEMORY_DIR / "history-*.json")
    all_blocks = []
    files = _glob.glob(pattern)
    for f in files:
        if session_id and session_id not in f:
            continue
        try:
            data = json.loads(Path(f).read_text())
            if isinstance(data, list):
                for b in data:
                    b["_file"] = Path(f).name
                    all_blocks.append(b)
        except Exception:
            pass
    return all_blocks

def _rmem_current_session_id():
    """Get the current main session ID (short hash) from the most recently modified history file."""
    pattern = str(RMEMORY_DIR / "history-*.json")
    files = _glob.glob(pattern)
    if not files:
        return None
    newest = max(files, key=lambda f: Path(f).stat().st_mtime)
    m = _re.search(r'history-([a-f0-9]+)\.json', newest)
    return m.group(1) if m else None

def _rmem_parse_log():
    """Parse r-memory.log (text format) into structured events.
    Log lines: [ISO_TS] [LEVEL] message {json}
    Key patterns: init, Session, === COMPACTION ===, Swap plan, Block compressed, === DONE ===, FIFO evicted, FIFO done
    """
    events = []
    if not RMEMORY_LOG.exists():
        return events
    try:
        text = RMEMORY_LOG.read_text(errors="ignore")
    except Exception:
        return events

    line_re = _re.compile(
        r'^\[(\d{4}-\d{2}-\d{2}T[\d:.]+Z)\]\s+\[(\w+)\]\s+(.*)', _re.MULTILINE
    )
    for m in line_re.finditer(text):
        ts, level, body = m.group(1), m.group(2), m.group(3)
        evt = {"ts": ts, "level": level, "raw": body}

        # Try to extract inline JSON
        json_match = _re.search(r'\{.*\}', body)
        payload = {}
        if json_match:
            try:
                payload = json.loads(json_match.group())
            except Exception:
                pass

        if "=== COMPACTION ===" in body:
            evt["event"] = "compaction_start"
            evt.update(payload)
        elif "=== DONE ===" in body:
            evt["event"] = "compaction_done"
            evt.update(payload)
        elif "Swap plan" in body:
            evt["event"] = "swap_plan"
            evt.update(payload)
        elif "Block compressed" in body:
            evt["event"] = "block_compressed"
            evt.update(payload)
        elif "FIFO evicted" in body:
            evt["event"] = "fifo_evicted"
            evt.update(payload)
        elif "FIFO done" in body:
            evt["event"] = "fifo_done"
            evt.update(payload)
        elif body.startswith("Session "):
            evt["event"] = "session"
            evt.update(payload)
        elif "init" in body and ("R-Memory" in body or "r-memory" in body.lower()):
            evt["event"] = "init"
            evt.update(payload)
        elif "Config loaded" in body:
            evt["event"] = "config_loaded"
            evt.update(payload)
        else:
            evt["event"] = "info"

        events.append(evt)
    return events

def _rmem_gateway_session():
    """Get main session data from sessions.json file directly."""
    session_paths = [
        Path.home() / ".openclaw" / "agents" / "main" / "sessions" / "sessions.json",
        Path.home() / ".openclaw" / "memory" / "agents" / "main" / "sessions" / "sessions.json",
    ]
    for sessions_path in session_paths:
        if not sessions_path.exists():
            continue
        try:
            data = json.loads(sessions_path.read_text())
            # sessions.json is a dict keyed by session key
            if isinstance(data, dict) and "agent:main:main" in data:
                return data["agent:main:main"]
            # Fallback: list format
            if isinstance(data, list):
                for s in data:
                    if s.get("key") == "agent:main:main":
                        return s
        except Exception:
            pass
    # Fallback: try WS
    try:
        sess_result = gw.request("sessions.list", timeout=5)
        if sess_result.get("ok") and sess_result.get("payload"):
            sessions = sess_result["payload"].get("sessions", [])
            for s in sessions:
                if s.get("key") == "agent:main:main":
                    return s
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Page Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html", active_page="overview")

@app.route("/agents")
def agents_page():
    return render_template("agents.html", active_page="agents")

@app.route("/r-memory")
def r_memory_page():
    return render_template("r-memory.html", active_page="r-memory")

@app.route("/projects")
def projects_page():
    return render_template("projects.html", active_page="projects")

@app.route("/chatbots")
def chatbots_page():
    return render_template("chatbots.html", active_page="chatbots")

@app.route("/wallet")
def wallet_page():
    return render_template("wallet.html", active_page="wallet")

@app.route("/protocol-store")
def protocol_store_page():
    cfg = {}
    cfg_path = Path(__file__).parent / "config.json"
    if cfg_path.exists():
        try:
            cfg = json.loads(cfg_path.read_text())
        except Exception:
            pass
    return render_template("protocol-store.html", active_page="protocol-store", config=cfg)

@app.route("/docs")
def docs_page():
    gitbook_url = app.config.get("GITBOOK_URL", "https://resonantos.gitbook.io/resonantos-docs/")
    return render_template("docs.html", active_page="docs", gitbook_url=gitbook_url)

@app.route("/license")
def license_page():
    return render_template("license.html", active_page="license")


# ============================================================================
# Docs API — browse, read, and search documentation
# ============================================================================

DOCS_WORKSPACE = WORKSPACE  # ~/.openclaw/workspace
REPO_DIR = REPO_ROOT  # derived from script location — works regardless of clone name
REPO_NAME = REPO_ROOT.name  # e.g. "resonantos-alpha" or "resonantos-augmentor"

WORKSPACE_SYSTEM_FILES = {
    "AGENTS.md", "SOUL.md", "USER.md", "TOOLS.md", "IDENTITY.md",
    "HEARTBEAT.md", "BOOTSTRAP.md",
}


def _docs_build_folder_tree(root, prefix=""):
    """Recursively build a file tree for docs browsing."""
    SKIP = {"node_modules", "target", "dist", "build", "__pycache__", "venv", ".venv", ".git", "media"}
    items = []
    if not root.exists() or not root.is_dir():
        return items
    try:
        for entry in sorted(root.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
            if entry.name.startswith(".") or entry.name in SKIP:
                continue
            rel = f"{prefix}/{entry.name}" if prefix else entry.name
            if entry.is_dir():
                children = _docs_build_folder_tree(entry, rel)
                if children:
                    fc = sum(1 for c in children if c["type"] == "file") + sum(c.get("fileCount", 0) for c in children if c["type"] == "folder")
                    items.append({"name": entry.name, "type": "folder", "path": rel, "children": children, "fileCount": fc})
            elif entry.suffix.lower() in (".md", ".txt", ".json", ".py", ".js", ".html", ".css"):
                try:
                    st = entry.stat()
                    items.append({"name": entry.name, "type": "file", "path": rel, "size": st.st_size, "modified": int(st.st_mtime * 1000)})
                except Exception:
                    pass
    except PermissionError:
        pass
    return items


def _docs_build_tree():
    """Build full docs tree from workspace sources."""
    tree = []

    # 1. Repo docs/
    docs_dir = REPO_DIR / "docs"
    if docs_dir.exists():
        items = _docs_build_folder_tree(docs_dir, f"{REPO_NAME}/docs")
        if items:
            tree.append({"name": "docs", "type": "folder", "path": f"{REPO_NAME}/docs", "icon": "📖", "children": items, "fileCount": sum(i.get("fileCount", 0) if i["type"] == "folder" else 1 for i in items)})

    # 2. SSoT
    ssot_dir = REPO_DIR / "ssot"
    if ssot_dir.exists():
        items = _docs_build_folder_tree(ssot_dir, f"{REPO_NAME}/ssot")
        if items:
            tree.append({"name": "ssot", "type": "folder", "path": f"{REPO_NAME}/ssot", "icon": "🗂️", "children": items, "fileCount": sum(i.get("fileCount", 0) if i["type"] == "folder" else 1 for i in items)})

    # 3. Dashboard source
    dash_dir = REPO_DIR / "dashboard"
    if dash_dir.exists():
        items = _docs_build_folder_tree(dash_dir, f"{REPO_NAME}/dashboard")
        if items:
            tree.append({"name": "dashboard", "type": "folder", "path": f"{REPO_NAME}/dashboard", "icon": "📊", "children": items, "fileCount": sum(i.get("fileCount", 0) if i["type"] == "folder" else 1 for i in items)})

    # 4. Reference
    ref_dir = REPO_DIR / "reference"
    if ref_dir.exists():
        items = _docs_build_folder_tree(ref_dir, f"{REPO_NAME}/reference")
        if items:
            tree.append({"name": "reference", "type": "folder", "path": f"{REPO_NAME}/reference", "icon": "📚", "children": items, "fileCount": sum(i.get("fileCount", 0) if i["type"] == "folder" else 1 for i in items)})

    # 5. Workspace root .md files (excluding system files)
    root_docs = []
    for f in sorted(DOCS_WORKSPACE.glob("*.md")):
        if f.name not in WORKSPACE_SYSTEM_FILES:
            try:
                st = f.stat()
                root_docs.append({"name": f.name, "type": "file", "path": f.name, "size": st.st_size, "modified": int(st.st_mtime * 1000)})
            except Exception:
                pass
    if root_docs:
        tree.append({"name": "workspace", "type": "folder", "path": "", "icon": "📄", "children": root_docs, "fileCount": len(root_docs)})

    # 6. Memory folder
    mem_dir = DOCS_WORKSPACE / "memory"
    if mem_dir.exists():
        items = _docs_build_folder_tree(mem_dir, "memory")
        if items:
            tree.append({"name": "memory", "type": "folder", "path": "memory", "icon": "🧠", "children": items, "fileCount": sum(i.get("fileCount", 0) if i["type"] == "folder" else 1 for i in items)})

    return tree


@app.route("/api/docs/tree")
def api_docs_tree():
    tree = _docs_build_tree()
    total = sum(i.get("fileCount", 0) for i in tree)
    return jsonify({"tree": tree, "root": str(DOCS_WORKSPACE), "totalFiles": total})


@app.route("/api/docs/file")
def api_docs_file():
    path = request.args.get("path", "")
    if path.startswith("/"):
        filepath = Path(path)
    elif path.startswith(f"{REPO_NAME}/"):
        # Resolve against actual repo location
        sub = path[len(f"{REPO_NAME}/"):]
        filepath = REPO_DIR / sub
    else:
        filepath = DOCS_WORKSPACE / path
    try:
        resolved = filepath.resolve()
        allowed = resolved.is_relative_to(DOCS_WORKSPACE.resolve()) or resolved.is_relative_to(REPO_DIR.resolve())
        if not allowed:
            return jsonify({"error": "Access denied"}), 403
    except Exception:
        return jsonify({"error": "Invalid path"}), 403
    if not filepath.exists():
        return jsonify({"error": "File not found"}), 404
    if not filepath.is_file():
        return jsonify({"error": "Not a file"}), 400
    try:
        content = filepath.read_text(errors="replace")
        stat = filepath.stat()
        title = filepath.stem
        for line in content.split("\n")[:10]:
            if line.startswith("# "):
                title = line[2:].strip()
                break
        return jsonify({"path": path, "name": filepath.name, "title": title, "content": content, "size": stat.st_size, "modified": int(stat.st_mtime * 1000), "wordCount": len(content.split()), "lineCount": content.count("\n") + 1})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/docs/open-in-editor", methods=["POST"])
def api_docs_open_editor():
    data = request.get_json() or {}
    path = data.get("path", "")
    if not path:
        return jsonify({"error": "No path"}), 400
    if path.startswith("/"):
        filepath = Path(path)
    elif path.startswith(f"{REPO_NAME}/"):
        filepath = REPO_DIR / path[len(f"{REPO_NAME}/"):]
    else:
        filepath = DOCS_WORKSPACE / path
    try:
        resolved = filepath.resolve()
        if not (resolved.is_relative_to(DOCS_WORKSPACE.resolve()) or resolved.is_relative_to(REPO_DIR.resolve())):
            return jsonify({"error": "Access denied"}), 403
    except Exception:
        return jsonify({"error": "Invalid path"}), 403
    if not filepath.exists():
        return jsonify({"error": "Not found"}), 404
    try:
        import shutil
        if shutil.which("code"):
            subprocess.Popen(["code", str(filepath)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return jsonify({"success": True, "editor": "VS Code"})
        else:
            subprocess.Popen(["open", str(filepath)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return jsonify({"success": True, "editor": "system"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/docs/search")
def api_docs_search():
    q = request.args.get("q", "")
    if len(q) < 2:
        return jsonify({"results": [], "query": q, "count": 0})
    results = []
    search_term = q.lower()

    def _search_file(fp, rel_path):
        try:
            content = fp.read_text(errors="replace")
            lines = content.split("\n")
            matches = []
            for i, line in enumerate(lines):
                if search_term in line.lower():
                    start, end = max(0, i - 1), min(len(lines), i + 2)
                    matches.append({"line": i + 1, "text": line.strip()[:200], "snippet": "\n".join(lines[start:end])[:300]})
                    if len(matches) >= 5:
                        break
            if matches:
                title = fp.stem
                for line in content.split("\n")[:10]:
                    if line.startswith("# "):
                        title = line[2:].strip()
                        break
                results.append({"path": rel_path, "name": fp.name, "title": title, "matches": matches, "matchCount": len(matches)})
        except Exception:
            pass

    # Search all browsable sources (REPO_DIR is the repo root, not inside workspace)
    search_roots = [
        (REPO_DIR / "docs", f"{REPO_NAME}/docs"),
        (REPO_DIR / "ssot", f"{REPO_NAME}/ssot"),
        (REPO_DIR / "reference", f"{REPO_NAME}/reference"),
        (DOCS_WORKSPACE / "memory", "memory"),
    ]
    for root, prefix in search_roots:
        if root.exists():
            for fp in root.rglob("*.md"):
                if len(results) >= 30:
                    break
                _search_file(fp, f"{prefix}/{fp.relative_to(root)}")

    # Root workspace docs
    for fp in DOCS_WORKSPACE.glob("*.md"):
        if len(results) >= 30:
            break
        if fp.name not in WORKSPACE_SYSTEM_FILES:
            _search_file(fp, fp.name)

    results.sort(key=lambda x: x["matchCount"], reverse=True)
    return jsonify({"results": results, "query": q, "count": len(results)})


@app.route("/api/docs/search/semantic")
def api_docs_search_semantic():
    import re
    from difflib import SequenceMatcher

    q = request.args.get("q", "")
    if len(q) < 2:
        return jsonify({"results": [], "query": q, "count": 0})
    results = []
    query_words = q.lower().split()

    def _relevance(content, fpath):
        cl = content.lower()
        fl = fpath.lower()
        score = 0.0
        if q.lower() in cl:
            score += 50.0
        wf = sum(1 for w in query_words if w in cl)
        score += (wf / len(query_words)) * 30.0
        score += sum(1 for w in query_words if w in fl) * 10.0
        for word in query_words:
            if word in cl:
                for m in re.finditer(re.escape(word), cl):
                    nearby = cl[max(0, m.start() - 100):m.start() + 100]
                    score += sum(1 for w in query_words if w in nearby) * 2.0
        for word in query_words:
            for cw in set(re.findall(r"\b\w+\b", cl)):
                if len(cw) > 3:
                    r = SequenceMatcher(None, word, cw).ratio()
                    if 0.8 < r < 1.0:
                        score += r * 5.0
        return score

    def _snippet(content):
        lines = content.split("\n")
        best_i, best_s = 0, 0
        for i, line in enumerate(lines):
            ll = line.lower()
            s = sum(1 for w in query_words if w in ll)
            if q.lower() in ll:
                s += 5
            if s > best_s:
                best_s = s
                best_i = i
        start, end = max(0, best_i - 1), min(len(lines), best_i + 3)
        snip = "\n".join(lines[start:end])[:300]
        return snip, best_i + 1

    search_roots = [
        (f"{REPO_NAME}/docs", REPO_DIR / "docs"),
        (f"{REPO_NAME}/ssot", REPO_DIR / "ssot"),
        (f"{REPO_NAME}/reference", REPO_DIR / "reference"),
        ("memory", DOCS_WORKSPACE / "memory"),
    ]
    for prefix, root in search_roots:
        if not root.exists():
            continue
        for fp in root.rglob("*.md"):
            try:
                content = fp.read_text(errors="replace")
                rel = f"{prefix}/{fp.relative_to(root)}"
                score = _relevance(content, rel)
                if score < 5.0:
                    continue
                snip, ln = _snippet(content)
                title = fp.stem
                for line in content.split("\n")[:5]:
                    if line.startswith("# "):
                        title = line[2:].strip()
                        break
                results.append({"path": rel, "name": fp.name, "title": title, "matches": [{"line": ln, "text": snip[:200], "snippet": snip}], "matchCount": 1, "score": round(score, 2)})
            except Exception:
                continue
    results.sort(key=lambda x: x["score"], reverse=True)
    return jsonify({"query": q, "mode": "semantic", "results": results[:20], "count": len(results)})


# ---------------------------------------------------------------------------
# API: Wallet & DAO (Solana integration)
# ---------------------------------------------------------------------------

@app.route("/api/wallet")
def api_wallet():
    """Get wallet balances for both SPL and Token-2022 accounts."""
    try:
        network = request.args.get("network", "devnet")
        address = request.args.get("address")
        
        if not address:
            try:
                address = str(_get_wallet_pubkey())
            except Exception:
                return jsonify({"error": "address parameter required"}), 400
        
        # Query both SPL and Token-2022 token accounts
        spl_program = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
        token22_program = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"
        
        balances = {}
        
        # Get SOL balance
        try:
            sol_result = _solana_rpc(network, "getBalance", [address])
            sol_balance = sol_result.get("result", {}).get("value", 0) / 1e9
            balances["SOL"] = {"balance": sol_balance, "decimals": 9}
        except Exception as e:
            print(f"Error getting SOL balance: {e}")
            balances["SOL"] = {"balance": 0, "decimals": 9}
        
        # Query token accounts for both programs
        for program in [spl_program, token22_program]:
            try:
                result = _solana_rpc(network, "getTokenAccountsByOwner", [
                    address,
                    {"programId": program},
                    {"encoding": "jsonParsed"}
                ])
                
                for account in result.get("result", {}).get("value", []):
                    parsed = account.get("account", {}).get("data", {}).get("parsed", {}).get("info", {})
                    mint = parsed.get("mint")
                    token_amount = parsed.get("tokenAmount", {})
                    amount = float(token_amount.get("amount", 0))
                    decimals = token_amount.get("decimals", 0)
                    ui_amount = amount / (10 ** decimals) if decimals > 0 else amount
                    
                    # Map known mints to symbols
                    symbol = mint
                    if mint == _RCT_MINT:
                        symbol = "$RCT"
                    elif mint == _RES_MINT:
                        symbol = "$RES"
                    elif mint in _REX_MINTS.values():
                        for k, v in _REX_MINTS.items():
                            if v == mint:
                                symbol = f"$REX-{k}"
                                break
                    
                    balances[symbol] = {
                        "balance": ui_amount,
                        "decimals": decimals,
                        "mint": mint
                    }
            except Exception as e:
                print(f"Error querying token accounts for {program}: {e}")
        
        return jsonify({
            "address": address,
            "network": network,
            "balances": balances
        })
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/api/wallet/user")
def api_wallet_user():
    """Query any address for balances + last claim time."""
    try:
        network = request.args.get("network", "devnet")
        address = request.args.get("address")
        
        if not address:
            return jsonify({"error": "address parameter required"}), 400
        
        # Get balances using existing endpoint logic
        wallet_data = api_wallet().get_json()
        
        # Get last claim time
        claims = _load_daily_claims()
        claim_val = claims.get(address)
        last_claim = claim_val if isinstance(claim_val, str) else (claim_val.get("last_claim") if isinstance(claim_val, dict) else None)
        
        return jsonify({
            "address": address,
            "network": network,
            "balances": wallet_data.get("balances", {}),
            "lastClaim": last_claim,
            "canClaim": True  # Will be calculated based on 24h cooldown
        })
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/api/wallet/mint-nft", methods=["POST"])
def api_wallet_mint_nft():
    """Mint soulbound NFT + reward tokens with RCT cap check."""
    try:
        if not NFTMinter or not TokenManager:
            return jsonify({"error": "Solana toolkit not available"}), 500
            
        data = request.get_json() or {}
        network = data.get("network", "devnet")
        recipient = data.get("recipient")
        nft_type = data.get("type", "identity")  # identity, alpha_tester
        signature = data.get("signature")  # Phantom co-signature
        
        # Devnet only for alpha
        if network != "devnet":
            return jsonify({"error": "Only devnet supported during alpha"}), 400
        
        if not recipient or not signature:
            return jsonify({"error": "recipient and signature required"}), 400
        
        # Reward amounts
        rewards = {
            "identity": {"rct": 5, "res": 500},
            "alpha_tester": {"rct": 50, "res": 1000}
        }
        
        reward = rewards.get(nft_type, rewards["identity"])
        
        # Check RCT cap
        can_mint, reason = _check_rct_cap(recipient, reward["rct"])
        if not can_mint:
            return jsonify({"error": f"RCT cap exceeded: {reason}"}), 429
        
        # Determine fee payer
        fee_payer_path, fee_payer_label = _get_fee_payer(network, recipient)
        
        # Mint NFT to Symbiotic PDA (not user wallet)
        pda_address = _derive_symbiotic_pda(recipient)
        nft_minter = NFTMinter(SolanaWallet(network=network))
        nft_result = nft_minter.mint_soulbound_nft(
            recipient=pda_address,
            nft_type=nft_type,
            name=f"ResonantOS {nft_type.replace('_', ' ').title()}",
            symbol="ROS-NFT",
            fee_payer_keypair=fee_payer_path
        )
        
        # Mint reward tokens
        token_manager = TokenManager(SolanaWallet(network=network))
        
        # Mint RCT (Token-2022) → Symbiotic PDA
        rct_result = token_manager.mint_tokens(
            mint=_RCT_MINT,
            destination_owner=pda_address,
            amount=reward["rct"] * (10 ** _RCT_DECIMALS),
            token_program="token2022"
        )
        
        # Mint RES (SPL) → Symbiotic PDA
        res_result = token_manager.mint_tokens(
            mint=_RES_MINT,
            destination_owner=pda_address,
            amount=reward["res"] * (10 ** 6),
            token_program="spl"
        )
        
        # Record RCT mint for cap tracking
        _record_rct_mint(recipient, reward["rct"])
        
        # Update NFT registry for display name resolution
        try:
            reg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "nft_registry.json")
            registry = {}
            if os.path.exists(reg_path):
                with open(reg_path) as rf:
                    registry = json.load(rf)
            nft_mint_addr = nft_result.get("mint")
            if nft_mint_addr:
                registry[nft_mint_addr] = nft_type  # "identity" or "alpha_tester" → map alpha_tester to "alpha"
                if nft_type == "alpha_tester":
                    registry[nft_mint_addr] = "alpha"
                with open(reg_path, "w") as wf:
                    json.dump(registry, wf, indent=2)
        except Exception as e:
            print(f"Warning: could not update nft_registry: {e}")
        
        # Update onboarding status
        onboarding = _load_onboarding()
        if recipient not in onboarding:
            onboarding[recipient] = {}
        if nft_type == "identity":
            onboarding[recipient]["identityNftMinted"] = True
            onboarding[recipient]["identityNftMint"] = nft_result.get("mint")
        elif nft_type == "alpha_tester":
            onboarding[recipient]["alphaNftMinted"] = True
            onboarding[recipient]["alphaNftMint"] = nft_result.get("mint")
        _save_onboarding(onboarding)
        
        return jsonify({
            "success": True,
            "nftMint": nft_result.get("mint"),
            "rctAmount": reward["rct"],
            "resAmount": reward["res"],
            "feePayer": fee_payer_label,
            "transactions": {
                "nft": nft_result.get("signature") if isinstance(nft_result, dict) else str(nft_result),
                "rct": rct_result if isinstance(rct_result, str) else rct_result if isinstance(rct_result, str) else rct_result.get("signature"),
                "res": res_result if isinstance(res_result, str) else res_result if isinstance(res_result, str) else res_result.get("signature")
            }
        })
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/api/wallet/build-transfer-tx", methods=["POST"])
def api_wallet_build_transfer_tx():
    """Build a transfer_out transaction for Phantom to sign.

    The PDA transfer requires the on-chain program to authorize via CPI.
    Human signs the transaction via Phantom, server builds the instruction.

    Body: { sender, recipient, amount, token (RCT|RES), network }
    Returns: { transaction: base64-encoded serialized tx (message only, for Phantom signing) }
    """
    try:
        import hashlib as _hl
        import struct as _st
        import base64
        from solders.pubkey import Pubkey as _Pubkey
        from solders.instruction import Instruction as _Ix, AccountMeta as _AM
        from solders.transaction import Transaction as _Tx
        from solders.message import Message as _Msg
        from solana.rpc.api import Client as _Client

        data = request.get_json(force=True)
        network = data.get("network", "devnet")
        sender = data.get("sender", "").strip()
        recipient = data.get("recipient", "").strip()
        amount = float(data.get("amount", 0))
        token = data.get("token", "RCT").upper()

        if not sender or not recipient or amount <= 0:
            return jsonify({"error": "Missing sender, recipient, or valid amount"}), 400

        # Verify sender has Identity NFT
        onboarding = _load_onboarding()
        user_data = onboarding.get(sender, {})
        if not user_data.get("identityNftMinted"):
            return jsonify({"error": "Identity NFT required to send tokens"}), 403

        # Token config
        if token == "RCT":
            mint_str = _RCT_MINT
            decimals = 9
            token_prog_str = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"  # Token-2022
        elif token == "RES":
            mint_str = _RES_MINT
            decimals = 6
            token_prog_str = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"  # SPL Token
        else:
            return jsonify({"error": f"Unknown token: {token}"}), 400

        # Validate base58 addresses
        import re as _re
        _b58_re = _re.compile(r'^[1-9A-HJ-NP-Za-km-z]{32,44}$')
        if not _b58_re.match(sender):
            return jsonify({"error": f"Invalid sender address (not base58)"}), 400
        if not _b58_re.match(recipient):
            return jsonify({"error": f"Invalid recipient address (not base58)"}), 400

        # Derive PDA
        program_id = _Pubkey.from_string(_SYMBIOTIC_PROGRAM_ID)
        human = _Pubkey.from_string(sender)
        recipient_pk = _Pubkey.from_string(recipient)
        mint = _Pubkey.from_string(mint_str)
        token_prog = _Pubkey.from_string(token_prog_str)

        pda, bump = _Pubkey.find_program_address(
            [b"symbiotic", bytes(human), bytes([0])], program_id
        )

        # Derive ATAs
        from spl.token.instructions import get_associated_token_address
        from_ata = get_associated_token_address(pda, mint, token_prog)
        to_ata = get_associated_token_address(recipient_pk, mint, token_prog)

        # Build transfer_out instruction
        disc = _hl.sha256(b"global:transfer_out").digest()[:8]
        raw_amount = int(amount * (10 ** decimals))
        ix_data = disc + _st.pack("<Q", raw_amount)

        accounts = [
            _AM(pubkey=pda, is_signer=False, is_writable=False),
            _AM(pubkey=human, is_signer=True, is_writable=True),
            _AM(pubkey=from_ata, is_signer=False, is_writable=True),
            _AM(pubkey=to_ata, is_signer=False, is_writable=True),
            _AM(pubkey=mint, is_signer=False, is_writable=False),
            _AM(pubkey=token_prog, is_signer=False, is_writable=False),
        ]

        ix = _Ix(program_id, ix_data, accounts)

        # Optionally create recipient ATA if it doesn't exist
        rpcs = {"devnet": "https://api.devnet.solana.com", "testnet": "https://api.testnet.solana.com", "mainnet-beta": "https://api.mainnet-beta.com"}
        client = _Client(rpcs.get(network, network))

        instructions = []

        # Check if recipient ATA exists
        ata_info = client.get_account_info(to_ata)
        if ata_info.value is None:
            # Create ATA instruction
            from spl.token.instructions import create_associated_token_account
            create_ata_ix = create_associated_token_account(
                payer=human, owner=recipient_pk, mint=mint, token_program_id=token_prog
            )
            instructions.append(create_ata_ix)

        instructions.append(ix)

        # Build transaction message
        blockhash_resp = client.get_latest_blockhash()
        blockhash = blockhash_resp.value.blockhash
        msg = _Msg.new_with_blockhash(instructions, human, blockhash)
        tx = _Tx.new_unsigned(msg)

        # Serialize for Phantom
        tx_bytes = bytes(tx)
        tx_b64 = base64.b64encode(tx_bytes).decode("ascii")

        return jsonify({
            "transaction": tx_b64,
            "pda": str(pda),
            "fromAta": str(from_ata),
            "toAta": str(to_ata),
            "rawAmount": raw_amount,
            "decimals": decimals,
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/api/wallet/build-sol-transfer", methods=["POST"])
def api_wallet_build_sol_transfer():
    """Build a simple SOL transfer from Phantom wallet (system program).
    Body: { sender, recipient, amount, network }
    Returns: { transaction: base64 }
    """
    try:
        import struct as _st
        import base64
        from solders.pubkey import Pubkey as _Pubkey
        from solders.instruction import Instruction as _Ix, AccountMeta as _AM
        from solders.transaction import Transaction as _Tx
        from solders.message import Message as _Msg
        from solana.rpc.api import Client as _Client

        data = request.get_json(force=True)
        network = data.get("network", "devnet")
        sender = data.get("sender", "").strip()
        recipient = data.get("recipient", "").strip()
        amount = float(data.get("amount", 0))

        if not sender or not recipient or amount <= 0:
            return jsonify({"error": "Missing sender, recipient, or valid amount"}), 400

        import re as _re
        _b58_re = _re.compile(r'^[1-9A-HJ-NP-Za-km-z]{32,44}$')
        if not _b58_re.match(sender) or not _b58_re.match(recipient):
            return jsonify({"error": "Invalid address (not base58)"}), 400

        sender_pk = _Pubkey.from_string(sender)
        recipient_pk = _Pubkey.from_string(recipient)
        lamports = int(amount * 1_000_000_000)  # SOL → lamports

        # System program transfer instruction
        system_prog = _Pubkey.from_string("11111111111111111111111111111111")
        ix_data = _st.pack("<II", 2, 0) + _st.pack("<Q", lamports)  # instruction index 2 = Transfer
        # Simpler: use solders system_program if available
        try:
            from solders.system_program import transfer, TransferParams
            ix = transfer(TransferParams(from_pubkey=sender_pk, to_pubkey=recipient_pk, lamports=lamports))
        except ImportError:
            accounts = [
                _AM(pubkey=sender_pk, is_signer=True, is_writable=True),
                _AM(pubkey=recipient_pk, is_signer=False, is_writable=True),
            ]
            ix = _Ix(system_prog, ix_data, accounts)

        rpcs = {"devnet": "https://api.devnet.solana.com", "testnet": "https://api.testnet.solana.com", "mainnet-beta": "https://api.mainnet-beta.com"}
        client = _Client(rpcs.get(network, network))
        blockhash_resp = client.get_latest_blockhash()
        blockhash = blockhash_resp.value.blockhash

        msg = _Msg.new_with_blockhash([ix], sender_pk, blockhash)
        tx = _Tx.new_unsigned(msg)
        tx_b64 = base64.b64encode(bytes(tx)).decode("ascii")

        return jsonify({"transaction": tx_b64, "lamports": lamports})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/wallet/send-tokens", methods=["POST"])
def api_wallet_send_tokens():
    """Legacy endpoint — redirects to build-transfer-tx."""
    return api_wallet_build_transfer_tx()

@app.route("/api/wallet/daily-claim", methods=["POST"])
def api_wallet_daily_claim():
    """24h cooldown, mint 1 RCT + 500 RES with cap check."""
    try:
        if not TokenManager:
            return jsonify({"error": "Solana toolkit not available"}), 500
            
        data = request.get_json() or {}
        network = data.get("network", "devnet")
        recipient = data.get("recipient")
        signature = data.get("signature")  # Phantom co-signature
        
        # Devnet only for alpha
        if network != "devnet":
            return jsonify({"error": "Only devnet supported during alpha"}), 400
        
        if not recipient or not signature:
            return jsonify({"error": "recipient and signature required"}), 400
        
        # Require Identity NFT
        if not _require_identity_nft(recipient):
            return jsonify({"error": "Identity NFT required. Complete onboarding first."}), 403
        
        # Check 24h cooldown
        claims = _load_daily_claims()
        raw_claim = claims.get(recipient)
        # Handle both old format (string timestamp) and new format (dict)
        if isinstance(raw_claim, str):
            user_claims = {"last_claim": raw_claim, "total_claims": 0}
        elif isinstance(raw_claim, dict):
            user_claims = raw_claim
        else:
            user_claims = {}
        last_claim = user_claims.get("last_claim")
        
        if last_claim:
            last_claim_time = datetime.fromisoformat(last_claim.replace("Z", "+00:00"))
            if last_claim_time.tzinfo is None:
                last_claim_time = last_claim_time.replace(tzinfo=timezone.utc)
            hours_since = (datetime.now(timezone.utc) - last_claim_time).total_seconds() / 3600
            if hours_since < 24:
                hours_remaining = 24 - hours_since
                return jsonify({
                    "error": f"Cooldown active. {hours_remaining:.1f} hours remaining.",
                    "hoursRemaining": hours_remaining
                }), 429
        
        # Check RCT cap
        can_mint, reason = _check_rct_cap(recipient, 1)
        if not can_mint:
            return jsonify({"error": f"RCT cap exceeded: {reason}"}), 429
        
        # Determine fee payer
        fee_payer_path, fee_payer_label = _get_fee_payer(network, recipient)
        
        # Mint tokens
        token_manager = TokenManager(SolanaWallet(network=network))
        pda_address = _derive_symbiotic_pda(recipient)
        
        # Mint 1 RCT → Symbiotic PDA
        rct_result = token_manager.mint_tokens(
            mint=_RCT_MINT,
            destination_owner=pda_address,
            amount=1 * (10 ** _RCT_DECIMALS),
            token_program="token2022"
        )
        
        # Mint 500 RES → Symbiotic PDA
        res_result = token_manager.mint_tokens(
            mint=_RES_MINT,
            destination_owner=pda_address,
            amount=500 * (10 ** 6),
            token_program="spl"
        )
        
        # Record claim and RCT mint
        claims[recipient] = {
            "last_claim": datetime.now(timezone.utc).isoformat(),
            "total_claims": user_claims.get("total_claims", 0) + 1
        }
        _save_daily_claims(claims)
        _record_rct_mint(recipient, 1)
        
        return jsonify({
            "success": True,
            "rctAmount": 1,
            "resAmount": 500,
            "feePayer": fee_payer_label,
            "nextClaimAvailable": (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat(),
            "transactions": {
                "rct": rct_result if isinstance(rct_result, str) else rct_result.get("signature"),
                "res": res_result if isinstance(res_result, str) else res_result.get("signature")
            }
        })
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/api/wallet/onboarding-status")
def api_wallet_onboarding_status():
    """Check license/manifesto/NFT status."""
    try:
        address = request.args.get("address")
        if not address:
            return jsonify({"error": "address parameter required"}), 400
        
        onboarding = _load_onboarding()
        user_onboarding = onboarding.get(address, {})
        
        return jsonify({
            "address": address,
            "alphaAgreed": user_onboarding.get("alphaAgreed", False),
            "licenseSigned": user_onboarding.get("licenseSigned", False),
            "manifestoSigned": user_onboarding.get("manifestoSigned", False),
            "identityNftMinted": user_onboarding.get("identityNftMinted", False),
            "alphaNftMinted": user_onboarding.get("alphaNftMinted", False),
            "onboardingComplete": all([
                user_onboarding.get("alphaAgreed"),
                user_onboarding.get("licenseSigned"),
                user_onboarding.get("manifestoSigned"),
                user_onboarding.get("identityNftMinted"),
                user_onboarding.get("alphaNftMinted")
            ])
        })
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/api/wallet/agree-alpha", methods=["POST"])
def api_wallet_agree_alpha():
    """Record Alpha Testing Agreement acceptance."""
    try:
        data = request.get_json() or {}
        address = data.get("address")
        signature = data.get("signature")

        if not address or not signature:
            return jsonify({"error": "address and signature required"}), 400

        onboarding = _load_onboarding()
        if address not in onboarding:
            onboarding[address] = {}

        if onboarding[address].get("alphaAgreed"):
            return jsonify({"error": "Already agreed"}), 409

        onboarding[address]["alphaAgreed"] = True
        onboarding[address]["alphaAgreedAt"] = datetime.now(timezone.utc).isoformat()
        onboarding[address]["alphaSignature"] = signature
        _save_onboarding(onboarding)

        return jsonify({"success": True})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/wallet/sign-license", methods=["POST"])
def api_wallet_sign_license():
    """Co-sign license, mint License NFT."""
    try:
        if not NFTMinter:
            return jsonify({"error": "Solana toolkit not available"}), 500
            
        data = request.get_json() or {}
        network = data.get("network", "devnet")
        address = data.get("address")
        signature = data.get("signature")  # Phantom signature of license hash
        
        if not address or not signature:
            return jsonify({"error": "address and signature required"}), 400
        
        # Verify signature is of correct license hash
        license_text = "Resonant Commons Symbiotic License (RC-SL) v1.0"
        expected_hash = hashlib.sha256(license_text.encode()).hexdigest()
        
        # Store signing record
        onboarding = _load_onboarding()
        if address not in onboarding:
            onboarding[address] = {}
        
        onboarding[address]["licenseSigned"] = True
        onboarding[address]["licenseSignedAt"] = datetime.now(timezone.utc).isoformat()
        onboarding[address]["licenseHash"] = expected_hash
        onboarding[address]["licenseSignature"] = signature
        
        _save_onboarding(onboarding)
        
        # Mint License NFT to Symbiotic PDA
        fee_payer_path, fee_payer_label = _get_fee_payer(network, address)
        pda_address = _derive_symbiotic_pda(address)
        
        nft_minter = NFTMinter(SolanaWallet(network=network))
        nft_result = nft_minter.mint_soulbound_nft(
            recipient=pda_address,
            nft_type="symbiotic_license",
            name="Resonant Commons License Signatory",
            symbol="RC-LIC",
            fee_payer_keypair=fee_payer_path
        )
        
        # Store NFT mint in onboarding record
        if nft_result.get("mint"):
            onboarding[address]["licenseNft"] = nft_result["mint"]
            _save_onboarding(onboarding)
        
        return jsonify({
            "success": True,
            "licenseHash": expected_hash,
            "nftMint": nft_result.get("mint"),
            "feePayer": fee_payer_label,
            "transaction": nft_result.get("signature")
        })
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/api/wallet/sign-manifesto", methods=["POST"])
def api_wallet_sign_manifesto():
    """Co-sign manifesto, mint Manifesto NFT."""
    try:
        if not NFTMinter:
            return jsonify({"error": "Solana toolkit not available"}), 500
            
        data = request.get_json() or {}
        network = data.get("network", "devnet")
        address = data.get("address")
        signature = data.get("signature")  # Phantom signature of manifesto hash
        
        if not address or not signature:
            return jsonify({"error": "address and signature required"}), 400
        
        # Require license signed first
        onboarding = _load_onboarding()
        user_onboarding = onboarding.get(address, {})
        
        if not user_onboarding.get("licenseSigned"):
            return jsonify({"error": "Must sign license first"}), 400
        
        # Verify signature is of correct manifesto hash
        manifesto_text = "Augmentatism Manifesto v2.2"
        expected_hash = hashlib.sha256(manifesto_text.encode()).hexdigest()
        
        # Store signing record
        onboarding[address]["manifestoSigned"] = True
        onboarding[address]["manifestoSignedAt"] = datetime.now(timezone.utc).isoformat()
        onboarding[address]["manifestoHash"] = expected_hash
        onboarding[address]["manifestoSignature"] = signature
        
        _save_onboarding(onboarding)
        
        # Mint Manifesto NFT to Symbiotic PDA
        fee_payer_path, fee_payer_label = _get_fee_payer(network, address)
        pda_address = _derive_symbiotic_pda(address)
        
        nft_minter = NFTMinter(SolanaWallet(network=network))
        nft_result = nft_minter.mint_soulbound_nft(
            recipient=pda_address,
            nft_type="manifesto",
            name="Augmentatism Manifesto Signatory",
            symbol="AUG-MAN",
            fee_payer_keypair=fee_payer_path
        )
        
        # Store NFT mint in onboarding record
        if nft_result.get("mint"):
            onboarding[address]["manifestoNft"] = nft_result["mint"]
            _save_onboarding(onboarding)
        
        return jsonify({
            "success": True,
            "manifestoHash": expected_hash,
            "nftMint": nft_result.get("mint"),
            "feePayer": fee_payer_label,
            "transaction": nft_result.get("signature")
        })
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/api/wallet/reputation")
def api_wallet_reputation():
    """Query REX token balances, compute levels."""
    try:
        network = request.args.get("network", "devnet")
        address = request.args.get("address")
        
        if not address:
            return jsonify({"error": "address parameter required"}), 400
        
        reputation = {"address": address, "network": network, "categories": {}}
        
        # Query REX token balances
        for category, mint in _REX_MINTS.items():
            try:
                result = _solana_rpc(network, "getTokenAccountsByOwner", [
                    address,
                    {"mint": mint},
                    {"encoding": "jsonParsed"}
                ])
                
                balance = 0
                for account in result.get("result", {}).get("value", []):
                    parsed = account.get("account", {}).get("data", {}).get("parsed", {}).get("info", {})
                    token_amount = parsed.get("tokenAmount", {})
                    amount = float(token_amount.get("amount", 0))
                    decimals = token_amount.get("decimals", 0)
                    balance = amount / (10 ** decimals) if decimals > 0 else amount
                    break
                
                # Compute level from thresholds
                level = 0
                for i, threshold in enumerate(_LEVEL_THRESHOLDS):
                    if balance >= threshold:
                        level = i
                    else:
                        break
                
                reputation["categories"][category] = {
                    "balance": balance,
                    "level": level,
                    "mint": mint,
                    "display": _REX_DISPLAY[category]
                }
                
            except Exception as e:
                print(f"Error querying REX {category}: {e}")
                reputation["categories"][category] = {
                    "balance": 0,
                    "level": 0,
                    "mint": mint,
                    "display": _REX_DISPLAY[category]
                }
        
        # Compute overall level (max of all categories)
        overall_level = max([cat.get("level", 0) for cat in reputation["categories"].values()] + [0])
        reputation["overallLevel"] = overall_level
        
        return jsonify(reputation)
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/api/wallet/grant-xp", methods=["POST"])
def api_wallet_grant_xp():
    """Mint REX tokens + 10 RCT bonus."""
    try:
        if not TokenManager:
            return jsonify({"error": "Solana toolkit not available"}), 500
            
        data = request.get_json() or {}
        network = data.get("network", "devnet")
        recipient = data.get("recipient")
        category = data.get("category")  # GOV, FIN, COM, CRE, TEC
        amount = data.get("amount", 10)  # XP amount to grant
        signature = data.get("signature")  # Phantom co-signature
        
        if not recipient or not category or category not in _REX_MINTS:
            return jsonify({"error": "recipient and valid category required"}), 400
        
        # Require Identity NFT
        if not _require_identity_nft(recipient):
            return jsonify({"error": "Identity NFT required. Complete onboarding first."}), 403
        
        # Check RCT cap for the 10 RCT bonus
        can_mint, reason = _check_rct_cap(recipient, 10)
        if not can_mint:
            return jsonify({"error": f"RCT cap exceeded: {reason}"}), 429
        
        # Determine fee payer
        fee_payer_path, fee_payer_label = _get_fee_payer(network, recipient)
        
        token_manager = TokenManager(SolanaWallet(network=network))
        pda_address = _derive_symbiotic_pda(recipient)
        
        # Mint REX tokens (Token-2022, 0 decimals) → Symbiotic PDA
        rex_result = token_manager.mint_tokens(
            mint=_REX_MINTS[category],
            destination_owner=pda_address,
            amount=amount,
            token_program="token2022"
        )
        
        # Mint 10 RCT bonus → Symbiotic PDA
        rct_result = token_manager.mint_tokens(
            mint=_RCT_MINT,
            destination_owner=pda_address,
            amount=10 * (10 ** _RCT_DECIMALS),
            token_program="token2022"
        )
        
        # Record RCT mint
        _record_rct_mint(recipient, 10)
        
        return jsonify({
            "success": True,
            "category": category,
            "categoryDisplay": _REX_DISPLAY[category],
            "xpAmount": amount,
            "rctBonus": 10,
            "feePayer": fee_payer_label,
            "transactions": {
                "rex": rex_result if isinstance(rex_result, str) else rex_result.get("signature"),
                "rct": rct_result if isinstance(rct_result, str) else rct_result.get("signature")
            }
        })
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/api/wallet/leaderboard")
def api_wallet_leaderboard():
    """Rankings by RCT and REX categories — only Identity NFT holders."""
    try:
        network = request.args.get("network", "devnet")
        
        leaderboard = {"network": network, "overall": [], "categories": {}}
        
        # Load onboarding data — only include users with Identity NFT
        onboarding = _load_onboarding()
        identity_holders = {
            addr for addr, data in onboarding.items()
            if data.get("identityNftMinted")
        }

        # Build PDA→human mapping for all identity holders
        pda_to_human = {}
        for human_addr in identity_holders:
            try:
                pda = _derive_symbiotic_pda(human_addr)
                pda_to_human[pda] = human_addr
            except Exception:
                pass

        # Helper: resolve token account (ATA) → owner address
        def _resolve_owner(network, ata_address):
            try:
                info = _solana_rpc(network, "getAccountInfo", [
                    ata_address, {"encoding": "jsonParsed"}
                ])
                parsed = (info.get("result", {}).get("value", {})
                          .get("data", {}).get("parsed", {})
                          .get("info", {}))
                return parsed.get("owner", ata_address)
            except Exception:
                return ata_address

        # Helper: build ranked list — tokens live on PDAs now
        def _build_board(mint, decimals, max_entries):
            if not identity_holders:
                return []
            try:
                result = _solana_rpc(network, "getTokenLargestAccounts", [mint])
                accounts = result.get("result", {}).get("value", [])
            except Exception as e:
                print(f"Error getting largest accounts for {mint}: {e}")
                return []

            board = []
            for account in accounts:
                if len(board) >= max_entries:
                    break

                ata = account.get("address")
                amount = account.get("amount")
                dec = account.get("decimals", decimals)
                balance = int(amount) / (10 ** dec) if amount else 0
                if balance <= 0:
                    continue

                owner = _resolve_owner(network, ata)

                # Owner could be a PDA or a human wallet
                # Accept if owner IS an identity holder (human wallet)
                # OR if owner is a PDA that maps to an identity holder
                human_addr = pda_to_human.get(owner)
                if human_addr:
                    display_addr = human_addr  # show human wallet, not PDA
                elif owner in identity_holders:
                    display_addr = owner
                else:
                    continue  # skip non-identity-holder wallets

                level = 0
                for j, threshold in enumerate(_LEVEL_THRESHOLDS):
                    if balance >= threshold:
                        level = j
                    else:
                        break

                board.append({
                    "rank": len(board) + 1,
                    "address": display_addr,
                    "balance": balance,
                    "level": level
                })
            return board
        
        # Overall RCT leaderboard
        leaderboard["overall"] = _build_board(_RCT_MINT, _RCT_DECIMALS, 10)
        
        # REX category leaderboards
        for category, mint in _REX_MINTS.items():
            leaderboard["categories"][category] = {
                "display": _REX_DISPLAY[category],
                "rankings": _build_board(mint, 9, 5)
            }
        
        return jsonify(leaderboard)
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

# ---------------------------------------------------------------------------
# Protocol Store API
# ---------------------------------------------------------------------------

# Track minted protocol NFTs: {protocol_id: {wallet: mint_address}}
_PROTOCOL_MINTS_FILE = Path(__file__).parent / "data" / "protocol_mints.json"

def _load_protocol_mints():
    try:
        if _PROTOCOL_MINTS_FILE.exists():
            return json.loads(_PROTOCOL_MINTS_FILE.read_text())
    except Exception:
        pass
    return {}

def _save_protocol_mints(data):
    _PROTOCOL_MINTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _PROTOCOL_MINTS_FILE.write_text(json.dumps(data, indent=2))

@app.route("/api/protocol-store/list", methods=["GET"])
def api_protocol_store_list():
    """List available protocols with prices and creator info."""
    # Add creator to each protocol (Manolo's wallet for all official ones)
    enriched = {}
    for pid, pdata in PROTOCOL_NFTS.items():
        enriched[pid] = {**pdata, "creator": "vbYQ7rZu19Rjtro9obQxFeHq5UPNF5RQXA8jP8qywfF"}
    return jsonify({"protocols": enriched})

@app.route("/api/protocol-store/purchase", methods=["POST"])
def api_protocol_store_purchase():
    """Purchase a protocol NFT. Body: {protocol_id, wallet_address, network}"""
    try:
        if not ProtocolNFTMinter:
            return jsonify({"error": "Protocol NFT minter not available"}), 500

        data = request.get_json() or {}
        protocol_id = data.get("protocol_id")
        wallet_address = data.get("wallet_address")
        network = data.get("network", "devnet")

        if network != "devnet":
            return jsonify({"error": "Only devnet supported during alpha"}), 400

        if not protocol_id or not wallet_address:
            return jsonify({"error": "protocol_id and wallet_address required"}), 400

        # Require Identity NFT
        if not _require_identity_nft(wallet_address):
            return jsonify({"error": "Identity NFT required. Complete onboarding first."}), 403

        if protocol_id not in PROTOCOL_NFTS:
            return jsonify({"error": f"Unknown protocol: {protocol_id}"}), 400

        # Check if already purchased
        mints = _load_protocol_mints()
        wallet_mints = mints.get(wallet_address, {})
        if protocol_id in wallet_mints:
            return jsonify({
                "error": "Already purchased",
                "mint": wallet_mints[protocol_id]
            }), 409

        # ── Verify $RES payment: check Symbiotic PDA balance ──
        protocol_info = PROTOCOL_NFTS[protocol_id]
        price_res = protocol_info.get("price_res", 0)  # price in $RES
        if price_res > 0:
            from solders.pubkey import Pubkey as _Pk
            from solana.rpc.api import Client as _Cl
            program_id = _Pk.from_string(_SYMBIOTIC_PROGRAM_ID)
            human_pk = _Pk.from_string(wallet_address)
            pda, _ = _Pk.find_program_address(
                [b"symbiotic", bytes(human_pk), bytes([0])], program_id
            )
            res_mint = _Pk.from_string(_RES_MINT)
            res_prog = _Pk.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")
            from spl.token.instructions import get_associated_token_address
            pda_ata = get_associated_token_address(pda, res_mint, res_prog)
            rpcs = {"devnet": "https://api.devnet.solana.com"}
            cl = _Cl(rpcs.get(network, network))
            ata_info = cl.get_account_info_json_parsed(pda_ata)
            pda_balance = 0
            if ata_info.value:
                try:
                    pda_balance = int(ata_info.value.data.parsed["info"]["tokenAmount"]["amount"]) / 1e6
                except Exception:
                    pass
            if pda_balance < price_res:
                return jsonify({
                    "error": f"Insufficient $RES balance. Need {price_res}, have {pda_balance:.2f}",
                    "required": price_res,
                    "balance": pda_balance,
                }), 402

            # TODO: Actual $RES burn/transfer via on-chain escrow program
            # Currently: balance check only (gate). Deduction requires Anchor
            # marketplace program CPI (5wpGj4EG6J5uEqozLqUyHzEQbU26yjaL5aUE5FwBiYe5).
            # For alpha: balance check prevents abuse; users can't purchase
            # without sufficient $RES in their Symbiotic PDA.
            app.logger.info(
                f"Protocol purchase: {wallet_address} buying {protocol_id} "
                f"(price={price_res} $RES, balance={pda_balance:.2f} $RES) "
                f"— BALANCE CHECK PASSED, deduction pending on-chain escrow"
            )

        # Use Registration Basket as fee payer
        fee_payer = str(_REGISTRATION_BASKET_KEYPAIR)

        minter = ProtocolNFTMinter()
        result = minter.mint_protocol_nft(
            recipient=wallet_address,
            protocol_id=protocol_id,
            fee_payer_keypair=fee_payer,
        )

        # Record the mint
        if wallet_address not in mints:
            mints[wallet_address] = {}
        mints[wallet_address][protocol_id] = result["mint"]
        _save_protocol_mints(mints)

        return jsonify({
            "success": True,
            "mint": result["mint"],
            "ata": result["ata"],
            "protocol_id": protocol_id,
            "name": result["name"],
            "symbol": result["symbol"],
            "signature": result["mint_signature"],
            "transferable": True,
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/api/protocol-store/owned", methods=["GET"])
def api_protocol_store_owned():
    """Check which protocols a wallet owns. Query: ?wallet=<address>"""
    try:
        wallet = request.args.get("wallet")
        if not wallet:
            return jsonify({"error": "wallet parameter required"}), 400

        mints = _load_protocol_mints()
        wallet_mints = mints.get(wallet, {})

        owned = []
        for protocol_id, mint_address in wallet_mints.items():
            # Optionally verify on-chain ownership
            if ProtocolNFTMinter:
                try:
                    minter = ProtocolNFTMinter()
                    if minter.check_ownership(wallet, mint_address):
                        owned.append({"protocol_id": protocol_id, "mint": mint_address})
                except Exception:
                    # If check fails, trust the local record
                    owned.append({"protocol_id": protocol_id, "mint": mint_address})
            else:
                owned.append({"protocol_id": protocol_id, "mint": mint_address})

        return jsonify({"wallet": wallet, "owned": owned})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/api/protocol-store/content/<protocol_id>", methods=["GET"])
def api_protocol_store_content(protocol_id):
    """Get protocol content (SOUL.md) if wallet owns the NFT. Query: ?wallet=<address>&mint=<mint_address>"""
    try:
        wallet = request.args.get("wallet")
        mint_address = request.args.get("mint")

        if not wallet or not mint_address:
            return jsonify({"error": "wallet and mint parameters required"}), 400

        if protocol_id not in PROTOCOL_NFTS:
            return jsonify({"error": f"Unknown protocol: {protocol_id}"}), 404

        # Verify ownership
        mints = _load_protocol_mints()
        wallet_mints = mints.get(wallet, {})
        if protocol_id not in wallet_mints or wallet_mints[protocol_id] != mint_address:
            return jsonify({"error": "You do not own this protocol NFT"}), 403

        # On-chain verification if available
        if ProtocolNFTMinter:
            try:
                minter = ProtocolNFTMinter()
                if not minter.check_ownership(wallet, mint_address):
                    return jsonify({"error": "On-chain ownership verification failed"}), 403
            except Exception:
                pass  # Fall through if RPC fails

        # Read protocol content
        protocol_file = Path(__file__).parent / "protocols" / f"{protocol_id}.md"
        if not protocol_file.exists():
            return jsonify({"error": "Protocol content not available"}), 404

        content = protocol_file.read_text()
        return jsonify({
            "protocol_id": protocol_id,
            "name": PROTOCOL_NFTS[protocol_id]["name"],
            "content": content,
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

# ---------------------------------------------------------------------------
# Marketplace API (secondary market — all state on-chain via escrow program)
# ---------------------------------------------------------------------------
# Program: 5wpGj4EG6J5uEqozLqUyHzEQbU26yjaL5aUE5FwBiYe5 (DevNet)
# No server-side state. Listings read from Solana. Transactions signed by Phantom.

_MARKETPLACE_PROGRAM_ID = _CFG.get("programs", {}).get("MARKETPLACE_PROGRAM_ID", "5wpGj4EG6J5uEqozLqUyHzEQbU26yjaL5aUE5FwBiYe5")
_RCT_SELL_THRESHOLD = 500

try:
    from marketplace_client import get_all_listings, MARKETPLACE_PROGRAM_ID
except ImportError:
    get_all_listings = None
    MARKETPLACE_PROGRAM_ID = _MARKETPLACE_PROGRAM_ID


@app.route("/api/protocol-store/marketplace", methods=["GET"])
def api_marketplace_list():
    """List active marketplace listings from chain."""
    try:
        if get_all_listings is None:
            return jsonify({"listings": [], "warning": "marketplace_client not available"})

        network = request.args.get("network", "devnet")
        rpc = _SOLANA_RPCS.get(network, _SOLANA_RPCS["devnet"])
        listings = get_all_listings(rpc=rpc)

        # Enrich with protocol metadata from known mints
        mints_file = Path(__file__).parent.parent / "data" / "protocol_mints.json"
        mint_to_protocol = {}
        if mints_file.exists():
            records = json.loads(mints_file.read_text())
            for r in records.get("mints", []):
                mint_to_protocol[r["mint"]] = r.get("protocol_id", "")

        for l in listings:
            pid = mint_to_protocol.get(l["nft_mint"], "")
            l["protocol_id"] = pid
            if pid in PROTOCOL_NFTS:
                l["protocol_name"] = PROTOCOL_NFTS[pid]["name"]
                l["symbol"] = PROTOCOL_NFTS[pid]["symbol"]
                l["description"] = PROTOCOL_NFTS[pid].get("description", "")
                l["image"] = PROTOCOL_NFTS[pid].get("image", "")

        return jsonify({"listings": listings, "program_id": _MARKETPLACE_PROGRAM_ID})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"listings": [], "error": str(e)})


@app.route("/api/protocol-store/marketplace/config", methods=["GET"])
def api_marketplace_config():
    """Return marketplace program config for frontend transaction building."""
    return jsonify({
        "program_id": _MARKETPLACE_PROGRAM_ID,
        "res_mint": _RES_MINT,
        "res_decimals": 6,
        "rct_sell_threshold": _RCT_SELL_THRESHOLD,
        "token_2022_program": "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb",
        "spl_token_program": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
        "associated_token_program": "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL",
    })


# ---------------------------------------------------------------------------
# End Protocol Store & Marketplace API
# ---------------------------------------------------------------------------

@app.route("/api/wallet/document")
def api_wallet_document():
    """Return license or manifesto text."""
    try:
        doc_type = request.args.get("type", "license")
        
        if doc_type == "license":
            # Try to read from templates/license.html
            license_path = Path(__file__).parent / "templates" / "license.html"
            if license_path.exists():
                import re
                raw = license_path.read_text()
                # Strip Jinja extends/block lines entirely
                content = re.sub(r'\{%\s*extends.*?%\}\s*', '', raw)
                content = re.sub(r'\{%\s*block\s+title\s*%\}.*?\{%\s*endblock\s*%\}\s*', '', content)
                content = re.sub(r'\{%\s*(?:end)?block\s+\w+\s*%\}\s*', '', content)
                content = content.strip()
                return jsonify({
                    "type": "license",
                    "title": "Resonant Commons Symbiotic License (RC-SL) v1.0",
                    "content": content,
                    "hash": hashlib.sha256("Resonant Commons Symbiotic License (RC-SL) v1.0".encode()).hexdigest()
                })
            else:
                # Hardcoded fallback
                content = """# Resonant Commons Symbiotic License (RC-SL) v1.0

A license for symbiotic collaboration between human creativity and artificial intelligence.

[Full license text would be here...]"""
                return jsonify({
                    "type": "license",
                    "title": "Resonant Commons Symbiotic License (RC-SL) v1.0",
                    "content": content,
                    "hash": hashlib.sha256("Resonant Commons Symbiotic License (RC-SL) v1.0".encode()).hexdigest()
                })
        
        elif doc_type == "manifesto":
            try:
                # Try to fetch from augmentatism.com
                req = urllib.request.Request("https://augmentatism.com/manifesto")
                with urllib.request.urlopen(req, timeout=10) as resp:
                    content = resp.read().decode()
                    return jsonify({
                        "type": "manifesto",
                        "title": "Augmentatism Manifesto v2.2",
                        "content": content,
                        "hash": hashlib.sha256("Augmentatism Manifesto v2.2".encode()).hexdigest()
                    })
            except Exception:
                # Cached fallback
                content = """# Augmentatism Manifesto v2.2

The philosophy of symbiotic human-AI collaboration.

[Manifesto content would be cached here...]"""
                return jsonify({
                    "type": "manifesto",
                    "title": "Augmentatism Manifesto v2.2",
                    "content": content,
                    "hash": hashlib.sha256("Augmentatism Manifesto v2.2".encode()).hexdigest()
                })
        
        else:
            return jsonify({"error": "Invalid document type"}), 400
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/api/wallet/owned-nfts")
def api_wallet_owned_nfts():
    """Return NFTs owned by address."""
    try:
        network = request.args.get("network", "devnet")
        address = request.args.get("address")
        
        if not address:
            return jsonify({"error": "address parameter required"}), 400
        
        nfts = []
        
        # Query Token-2022 accounts (where soulbound NFTs are minted)
        try:
            result = _solana_rpc(network, "getTokenAccountsByOwner", [
                address,
                {"programId": "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"},
                {"encoding": "jsonParsed"}
            ])
            
            for account in result.get("result", {}).get("value", []):
                parsed = account.get("account", {}).get("data", {}).get("parsed", {}).get("info", {})
                mint = parsed.get("mint")
                token_amount = parsed.get("tokenAmount", {})
                amount = float(token_amount.get("amount", 0))
                
                if amount > 0 and int(token_amount.get("decimals", 0)) == 0:
                    # Check onboarding records to identify NFT type by mint
                    onboarding = _load_onboarding()
                    nft_data = {
                        "mint": mint,
                        "name": f"NFT {mint[:8]}...",
                        "tag": "Soulbound",
                        "img": None,
                        "soulbound": True
                    }
                    
                    # Match mint against known NFT mints from onboarding records
                    matched = False
                    for addr, record in onboarding.items():
                        if record.get("licenseNft") == mint:
                            nft_data.update({"name": "Symbiotic License", "tag": "Co-signed Agreement", "img": "/static/img/nfts/symbiotic-license.png"})
                            matched = True; break
                        elif record.get("manifestoNft") == mint:
                            nft_data.update({"name": "Augmentatism Manifesto", "tag": "Co-signed Commitment", "img": "/static/img/nfts/manifesto.png"})
                            matched = True; break
                        elif record.get("identityNft") == mint:
                            nft_data.update({"name": "Augmentor Identity", "tag": "AI Agent NFT", "img": "/static/img/nfts/ai-identity.png"})
                            matched = True; break
                        elif record.get("alphaNft") == mint:
                            nft_data.update({"name": "AI Artisan Alpha Tester", "tag": "Early Adopter", "img": "/static/img/nfts/alpha-tester.png"})
                            matched = True; break
                    
                    # Fallback 0: check nft_registry.json
                    if not matched:
                        try:
                            reg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "nft_registry.json")
                            if os.path.exists(reg_path):
                                with open(reg_path) as rf:
                                    registry = json.load(rf)
                                nft_type_key = registry.get(mint)
                                if nft_type_key:
                                    _type_display = {
                                        "identity": {"name": "Augmentor Identity", "tag": "AI Agent NFT", "img": "/static/img/nfts/ai-identity.png"},
                                        "alpha": {"name": "AI Artisan Alpha Tester", "tag": "Early Adopter", "img": "/static/img/nfts/alpha-tester.png"},
                                        "license": {"name": "Symbiotic License", "tag": "Co-signed Agreement", "img": "/static/img/nfts/symbiotic-license.png"},
                                        "manifesto": {"name": "Augmentatism Manifesto", "tag": "Co-signed Commitment", "img": "/static/img/nfts/manifesto.png"},
                                        "founder": {"name": "ResonantOS Founder", "tag": "Founder", "img": "/static/img/nfts/founder.png"},
                                        "dao_genesis": {"name": "DAO Genesis", "tag": "Genesis", "img": "/static/img/nfts/dao-genesis.png"},
                                    }
                                    if nft_type_key in _type_display:
                                        nft_data.update(_type_display[nft_type_key])
                                        matched = True
                        except Exception as e:
                            print(f"Error reading nft_registry: {e}")

                    # Fallback 1: try on-chain metadata
                    if not matched:
                        # Map known names to display info
                        _name_map = {
                            "Augmentor Identity": {"name": "Augmentor Identity", "tag": "AI Agent NFT", "img": "/static/img/nfts/ai-identity.png"},
                            "AI Artisan — Alpha Tester": {"name": "AI Artisan Alpha Tester", "tag": "Early Adopter", "img": "/static/img/nfts/alpha-tester.png"},
                            "AI Artisan — Alpha": {"name": "AI Artisan Alpha Tester", "tag": "Early Adopter", "img": "/static/img/nfts/alpha-tester.png"},
                            "Symbiotic License Agreement": {"name": "Symbiotic License", "tag": "Co-signed Agreement", "img": "/static/img/nfts/symbiotic-license.png"},
                            "Augmentatism Manifesto": {"name": "Augmentatism Manifesto", "tag": "Co-signed Commitment", "img": "/static/img/nfts/manifesto.png"},
                            "ResonantOS Founder": {"name": "ResonantOS Founder", "tag": "Founder", "img": "/static/img/nfts/founder.png"},
                            "Resonant Economy DAO Genesis": {"name": "DAO Genesis", "tag": "Genesis", "img": "/static/img/nfts/dao-genesis.png"},
                        }
                        # Try reading on-chain metadata from mint account
                        try:
                            mint_info = _solana_rpc(network, "getAccountInfo", [
                                mint, {"encoding": "jsonParsed"}
                            ])
                            mint_data = mint_info.get("result", {}).get("value", {}).get("data", {})
                            # Token-2022 parsed data may include extensions with metadata
                            extensions = []
                            if isinstance(mint_data, dict):
                                parsed_info = mint_data.get("parsed", {}).get("info", {})
                                extensions = parsed_info.get("extensions", [])
                            for ext in extensions:
                                if ext.get("extension") == "tokenMetadata":
                                    state = ext.get("state", {})
                                    onchain_name = state.get("name", "").strip().rstrip("\x00")
                                    if onchain_name:
                                        # Try matching against known names
                                        for known_name, info in _name_map.items():
                                            if known_name.lower() in onchain_name.lower() or onchain_name.lower() in known_name.lower():
                                                nft_data.update(info)
                                                matched = True
                                                break
                                        if not matched:
                                            nft_data["name"] = onchain_name
                                            matched = True
                                    break
                        except Exception as e:
                            print(f"Error reading mint metadata for {mint}: {e}")
                        
                    if not matched:
                        # Skip unidentified NFTs — only show recognized ones
                        continue
                    
                    nfts.append(nft_data)
        except Exception as e:
            print(f"Error querying NFTs: {e}")
        
        return jsonify({
            "address": address,
            "network": network,
            "nfts": nfts,
            "count": len(nfts)
        })
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

# ---------------------------------------------------------------------------
# Symbiotic Wallet On-Chain Endpoints
# ---------------------------------------------------------------------------

_SYMBIOTIC_PROGRAM_ID = _CFG.get("programs", {}).get("SYMBIOTIC_PROGRAM_ID", "HMthR7AStR3YKJ4m8GMveWx5dqY3D2g2cfnji7VdcVoG")
_AI_WALLET_PUBKEY = None  # Lazily loaded


def _get_ai_pubkey_str():
    global _AI_WALLET_PUBKEY
    if _AI_WALLET_PUBKEY is None:
        _AI_WALLET_PUBKEY = str(_get_wallet_pubkey())
    return _AI_WALLET_PUBKEY


def _derive_symbiotic_pda(human_pubkey_str):
    """Derive the Symbiotic PDA address for a human wallet."""
    from solders.pubkey import Pubkey as _Pubkey
    program_id = _Pubkey.from_string(_SYMBIOTIC_PROGRAM_ID)
    human = _Pubkey.from_string(human_pubkey_str)
    seeds = [b"symbiotic", bytes(human), bytes([0])]
    pda, _bump = _Pubkey.find_program_address(seeds, program_id)
    return str(pda)


@app.route("/api/symbiotic/build-init-tx", methods=["POST"])
def symbiotic_build_init_tx():
    """Build an initialize_pair transaction for Phantom to sign.

    Body: { "humanPubkey": "<base58>", "network": "devnet" }
    Returns: { "transaction": "<base64>", "pda": "<base58>", "bump": int }

    The human wallet must sign this transaction in Phantom.
    """
    try:
        data = request.get_json(force=True)
        human_str = data.get("humanPubkey", "").strip()
        network = data.get("network", "devnet")

        if network != "devnet":
            return jsonify({"error": "Alpha: devnet only"}), 400
        if not human_str:
            return jsonify({"error": "humanPubkey required"}), 400

        import struct as _struct
        import base64 as _b64
        from solders.pubkey import Pubkey as _Pubkey
        from solders.instruction import Instruction as _Ix, AccountMeta as _AM
        from solders.system_program import ID as _SYS
        from solders.transaction import Transaction as _Tx
        from solders.message import Message as _Msg
        from solana.rpc.api import Client as _Client

        program_id = _Pubkey.from_string(_SYMBIOTIC_PROGRAM_ID)
        human = _Pubkey.from_string(human_str)
        ai = _Pubkey.from_string(_get_ai_pubkey_str())
        pair_nonce = 0

        # Derive PDA
        seeds = [b"symbiotic", bytes(human), bytes([pair_nonce])]
        pda, bump = _Pubkey.find_program_address(seeds, program_id)

        # Build instruction data: discriminator + pair_nonce (u8)
        disc = hashlib.sha256(b"global:initialize_pair").digest()[:8]
        ix_data = disc + _struct.pack("<B", pair_nonce)

        accounts = [
            _AM(pubkey=pda, is_signer=False, is_writable=True),
            _AM(pubkey=human, is_signer=True, is_writable=True),
            _AM(pubkey=ai, is_signer=False, is_writable=False),
            _AM(pubkey=_SYS, is_signer=False, is_writable=False),
        ]

        ix = _Ix(program_id, ix_data, accounts)

        # Get recent blockhash
        rpc_url = _SOLANA_RPCS.get(network, _SOLANA_RPCS["devnet"])
        client = _Client(rpc_url)
        bh_resp = client.get_latest_blockhash()
        blockhash = bh_resp.value.blockhash

        # Build message with human as fee payer
        msg = _Msg.new_with_blockhash([ix], human, blockhash)
        tx = _Tx.new_unsigned(msg)

        # Serialize to base64 for Phantom
        tx_bytes = bytes(tx)
        tx_b64 = _b64.b64encode(tx_bytes).decode("ascii")

        return jsonify({
            "transaction": tx_b64,
            "pda": str(pda),
            "bump": bump,
            "aiPubkey": _get_ai_pubkey_str(),
            "humanPubkey": human_str,
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/symbiotic/pair-info")
def symbiotic_pair_info():
    """Get symbiotic pair info for a human wallet.

    Query: ?humanPubkey=<base58>&network=devnet
    Returns pair data if it exists, or {"exists": false}.
    """
    try:
        human_str = request.args.get("humanPubkey", "").strip()
        network = request.args.get("network", "devnet")

        if not human_str:
            return jsonify({"error": "humanPubkey required"}), 400

        from solders.pubkey import Pubkey as _Pubkey

        program_id = _Pubkey.from_string(_SYMBIOTIC_PROGRAM_ID)
        human = _Pubkey.from_string(human_str)

        seeds = [b"symbiotic", bytes(human), bytes([0])]
        pda, bump = _Pubkey.find_program_address(seeds, program_id)

        rpc_url = _SOLANA_RPCS.get(network, _SOLANA_RPCS["devnet"])
        rpc_data = json.loads(urllib.request.urlopen(
            urllib.request.Request(
                rpc_url,
                data=json.dumps({
                    "jsonrpc": "2.0", "id": 1,
                    "method": "getAccountInfo",
                    "params": [str(pda), {"encoding": "base64"}]
                }).encode(),
                headers={"Content-Type": "application/json"},
            ),
            timeout=10,
        ).read())

        account = rpc_data.get("result", {}).get("value")
        if account is None:
            return jsonify({"exists": False, "pda": str(pda)})

        import base64 as _b64, struct as _struct
        raw = _b64.b64decode(account["data"][0])
        if len(raw) < 93:
            return jsonify({"exists": False, "pda": str(pda)})

        d = raw[8:]  # skip discriminator
        from solders.pubkey import Pubkey as _P
        pair_data = {
            "exists": True,
            "pda": str(pda),
            "human": str(_P.from_bytes(d[0:32])),
            "ai": str(_P.from_bytes(d[32:64])),
            "pairNonce": d[64],
            "bump": d[65],
            "frozen": bool(d[66]),
            "lastClaim": _struct.unpack("<q", d[67:75])[0],
            "createdAt": _struct.unpack("<q", d[75:83])[0],
            "aiRotations": _struct.unpack("<H", d[83:85])[0],
        }
        return jsonify(pair_data)
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# End Wallet API
# ---------------------------------------------------------------------------

@app.route("/todo")
def todo_page():
    return render_template("todo.html", active_page="todo")

@app.route("/ideas")
def ideas_page():
    return render_template("ideas.html", active_page="ideas")

@app.route("/settings")
def settings_page():
    return render_template("settings.html", active_page="settings")

@app.route("/ssot")
def ssot_page():
    return render_template("ssot.html", active_page="ssot")


@app.route("/shield")
def shield_page():
    return render_template("shield.html", active_page="shield")

# ---------------------------------------------------------------------------
# API: Gateway Status & Health
# ---------------------------------------------------------------------------

@app.route("/api/gateway/status")
def api_gateway_status():
    """Overall gateway connection status."""
    return jsonify({
        "connected": gw.connected,
        "connId": gw.conn_id,
        "lastTick": gw.last_tick,
        "lastHealthTs": gw.last_health_ts,
        "error": gw.error,
    })

@app.route("/api/gateway/health")
def api_gateway_health():
    """Latest cached health data (channels, agents, heartbeat)."""
    with gw._lock:
        return jsonify(gw.health or {"error": "no health data yet"})

@app.route("/api/gateway/request", methods=["POST"])
def api_gateway_request():
    """Proxy arbitrary WS request to gateway. Body: {method, params}."""
    body = request.get_json(force=True)
    method = body.get("method")
    params = body.get("params")
    if not method:
        return jsonify({"ok": False, "error": "method required"}), 400
    result = gw.request(method, params)
    return jsonify(result)

@app.route("/api/gateway/restart", methods=["POST"])
def api_gateway_restart():
    """Restart the OpenClaw gateway via CLI."""
    try:
        import subprocess
        result = subprocess.run(
            ["openclaw", "gateway", "restart"],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0:
            return jsonify({"ok": True, "output": result.stdout.strip()})
        return jsonify({"ok": False, "error": result.stderr.strip() or "restart failed"}), 500
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ---------------------------------------------------------------------------
# API: Agents
# ---------------------------------------------------------------------------

@app.route("/api/agents")
def api_agents():
    """List agents from gateway health + local workspace directories."""
    agents = []
    seen_ids = set()

    # Helper: read workspace files for an agent
    def _read_workspace(agent_id):
        workspace_files = {}
        # Check per-agent workspace first, then shared.
        # Some setups store agent files under workspace/agents/<id> or
        # workspace/memory/agents/<id> instead of workspace-<id>.
        if agent_id == "main":
            candidate_dirs = [WORKSPACE]
        else:
            candidate_dirs = [
                OPENCLAW_HOME / f"workspace-{agent_id}",
                WORKSPACE / "agents" / agent_id,
                WORKSPACE / "memory" / "agents" / agent_id,
                OPENCLAW_HOME / "memory" / "agents" / agent_id,
            ]
        for fname in ["SOUL.md", "AGENTS.md", "USER.md", "IDENTITY.md", "MEMORY.md"]:
            fpath = None
            for ws_dir in candidate_dirs:
                candidate = ws_dir / fname
                if candidate.exists():
                    fpath = candidate
                    break
            if fpath is None and agent_id != "main":
                if fname in ("IDENTITY.md", "SOUL.md", "MEMORY.md"):
                    continue  # agent-specific files should NOT fall back to main
                shared = WORKSPACE / fname  # fallback to shared for AGENTS.md, USER.md
                if shared.exists():
                    fpath = shared
            if fpath and fpath.exists():
                try:
                    workspace_files[fname] = fpath.read_text()[:2000]
                except Exception:
                    pass
        return workspace_files

    # Helper: resolve model for agent
    def _resolve_model(agent_id):
        try:
            cfg = json.loads(OPENCLAW_CONFIG.read_text())
            # 1. Check agent-specific model in agents.list
            for entry in cfg.get("agents", {}).get("list", []):
                if entry.get("id") == agent_id and entry.get("model"):
                    m = entry["model"]
                    # model can be string or {"primary": "..."} (OpenClaw docs format)
                    return m.get("primary", str(m)) if isinstance(m, dict) else m
            # 2. Check agents.defaults.model
            default_model = cfg.get("agents", {}).get("defaults", {}).get("model")
            if default_model:
                return default_model.get("primary", str(default_model)) if isinstance(default_model, dict) else default_model
            # 3. Check top-level model
            top_model = cfg.get("model")
            if top_model:
                return top_model if isinstance(top_model, str) else top_model.get("primary", str(top_model))
            return "default"
        except Exception:
            return "default"

    # Helper: parse identity for emoji/name
    def _parse_identity(workspace_files):
        identity = workspace_files.get("IDENTITY.md", "")
        emoji = "🤖"
        name = None
        for line in identity.splitlines():
            if "**Emoji:**" in line:
                parts = line.split("**Emoji:**")
                if len(parts) > 1 and parts[1].strip():
                    emoji = parts[1].strip()
            if "**Name:**" in line:
                parts = line.split("**Name:**")
                if len(parts) > 1 and parts[1].strip():
                    name = parts[1].strip()
        return emoji, name

    # Agent metadata for hierarchy
    AGENT_META = {
        "main":     {"tier": 0, "role": "Orchestrator & Strategist", "category": "core"},
        "doer":     {"tier": 1, "role": "Personal Assistant & Task Executor", "category": "direct"},
        "dao":      {"tier": 1, "role": "DAO Strategy & Governance", "category": "direct"},
        "youtube":  {"tier": 1, "role": "Content Creation", "category": "direct"},
        "website":  {"tier": 1, "role": "Marketing Website", "category": "direct"},
        "watchdog":      {"tier": 1, "role": "System Health Monitor", "category": "support"},
        "decoder":       {"tier": 1, "role": "Coding Agent", "category": "background"},
        "acupuncturist": {"tier": 1, "role": "Protocol Enforcement", "category": "support"},
        "blindspot":     {"tier": 1, "role": "Red Team & Vulnerability Hunter", "category": "support"},
    }

    # Inject R-Memory as a virtual "memory" agent with effective models
    rmem_cfg = _rmem_config()
    effective = _rmem_effective_models()
    rmem_log = RMEMORY_DIR / "r-memory.log"
    rmem_status = "active" if rmem_log.exists() and rmem_log.stat().st_size > 0 else "inactive"
    # Load usage stats for call counts
    usage_stats = {}
    try:
        usage_stats = json.loads((RMEMORY_DIR / "usage-stats.json").read_text())
    except Exception:
        pass
    agents.append({
        "agentId": "memory",
        "isDefault": False,
        "status": rmem_status,
        "mainModel": effective["compression"],
        "heartbeat": {},
        "sessions": {"count": 0},
        "workspaceFiles": _read_workspace("memory"),
        "emoji": "🧠",
        "displayName": "R-Memory",
        "tier": 0.5,
        "role": "Compression & Narrative Tracking",
        "category": "core",
        "virtual": True,
        "subAgents": {
            "compression": {
                "model": effective["compression"],
                "label": "Conversation Compression",
                "calls": usage_stats.get("compression", {}).get("calls", 0),
            },
            "narrative": {
                "model": effective["narrative"],
                "label": "Narrative Tracker",
                "calls": usage_stats.get("narrative", {}).get("calls", 0),
            },
        },
    })
    seen_ids.add("memory")

    # 1. Active agents from gateway health
    health = gw.health or {}
    for ag in health.get("agents", []):
        agent_id = ag.get("agentId", "unknown")
        seen_ids.add(agent_id)
        workspace_files = _read_workspace(agent_id)
        emoji, name = _parse_identity(workspace_files)
        agents.append({
            "agentId": agent_id,
            "isDefault": ag.get("isDefault", False),
            "status": "active",
            "mainModel": _resolve_model(agent_id),
            "heartbeat": ag.get("heartbeat", {}),
            "sessions": ag.get("sessions", {}),
            "workspaceFiles": workspace_files,
            "emoji": emoji,
            "displayName": name or agent_id,
            **(AGENT_META.get(agent_id, {"tier": 1, "role": "Agent", "category": "other"})),
        })

    # 2. Agents from openclaw.json config (always available, even without gateway)
    try:
        cfg = json.loads(OPENCLAW_CONFIG.read_text())
        for agent_entry in cfg.get("agents", {}).get("list", []):
            agent_id = agent_entry.get("id", "")
            if not agent_id or agent_id in seen_ids:
                continue
            seen_ids.add(agent_id)
            workspace_files = _read_workspace(agent_id)
            emoji, name = _parse_identity(workspace_files)
            # Use the model from this agent's config, or the defaults model
            raw = agent_entry.get("model") or cfg.get("agents", {}).get("defaults", {}).get("model") or "unknown"
            model = raw.get("primary", str(raw)) if isinstance(raw, dict) else raw
            agents.append({
                "agentId": agent_id,
                "isDefault": agent_entry.get("default", False),
                "status": "configured",
                "mainModel": model,
                "heartbeat": {},
                "sessions": {"count": 0},
                "workspaceFiles": workspace_files,
                "emoji": emoji,
                "displayName": name or agent_id,
                **(AGENT_META.get(agent_id, {"tier": 0 if agent_entry.get("default") else 1, "role": "Agent", "category": "other"})),
            })
    except Exception:
        pass

    # 3. Discover agents from workspace-* directories (not yet in gateway or config)
    for ws_path in sorted(OPENCLAW_HOME.glob("workspace-*")):
        if not ws_path.is_dir():
            continue
        agent_id = ws_path.name.replace("workspace-", "")
        if agent_id in seen_ids:
            continue
        seen_ids.add(agent_id)
        workspace_files = _read_workspace(agent_id)
        emoji, name = _parse_identity(workspace_files)
        agents.append({
            "agentId": agent_id,
            "isDefault": False,
            "status": "inactive",
            "mainModel": _resolve_model(agent_id),
            "heartbeat": {},
            "sessions": {"count": 0},
            "workspaceFiles": workspace_files,
            "emoji": emoji,
            "displayName": name or agent_id,
            **(AGENT_META.get(agent_id, {"tier": 1, "role": "Agent", "category": "other"})),
        })

    # 4. Guaranteed fallback: always include "main" agent
    # Single-agent users may not have agents.list or workspace-* dirs
    if "main" not in seen_ids:
        workspace_files = _read_workspace("main")
        emoji, name = _parse_identity(workspace_files)
        agents.append({
            "agentId": "main",
            "isDefault": True,
            "status": "configured",
            "mainModel": _resolve_model("main"),
            "heartbeat": {},
            "sessions": {"count": 0},
            "workspaceFiles": workspace_files,
            "emoji": emoji,
            "displayName": name or "Main Agent",
            **(AGENT_META.get("main", {"tier": 0, "role": "Orchestrator & Strategist", "category": "core"})),
        })

    # Sort: tier 0 first, then alphabetical
    agents.sort(key=lambda a: (a.get("tier", 1), a["agentId"]))
    return jsonify(agents)

@app.route("/api/agents/<agent_id>/sessions")
def api_agent_sessions(agent_id):
    """Get sessions for an agent via gateway."""
    result = gw.request("sessions.list", {"agentId": agent_id})
    return jsonify(result)

@app.route("/api/agents/<agent_id>/model", methods=["PUT"])
def api_agent_model(agent_id):
    """Update an agent's model in OpenClaw config."""
    data = request.get_json(force=True) or {}
    model = data.get("model")
    if not model:
        return jsonify({"error": "model required"}), 400

    # Read current config
    cfg_path = Path.home() / ".openclaw" / "openclaw.json"
    if not cfg_path.exists():
        return jsonify({"error": "openclaw.json not found"}), 500
    try:
        cfg = json.loads(cfg_path.read_text())
    except Exception as e:
        return jsonify({"error": f"Failed to read config: {e}"}), 500

    # Ensure agents section exists
    if "agents" not in cfg:
        cfg["agents"] = {}
    if agent_id not in cfg["agents"]:
        cfg["agents"][agent_id] = {}

    cfg["agents"][agent_id]["model"] = model

    try:
        cfg_path.write_text(json.dumps(cfg, indent=2))
    except Exception as e:
        return jsonify({"error": f"Failed to write config: {e}"}), 500

    return jsonify({"ok": True, "agentId": agent_id, "model": model})


# ---------------------------------------------------------------------------
# API: R-Memory (SSoT documents)
# ---------------------------------------------------------------------------

def _scan_ssot_layer(layer_dir, layer_name):
    """Scan a layer directory (recursively) for SSoT documents."""
    docs = []
    if not layer_dir.exists():
        return docs

    for f in sorted(layer_dir.rglob("*.md")):
        if f.name.startswith("."):
            continue
        # Skip .ai.md files only if the full version exists (shown via hasCompressed toggle)
        if f.name.endswith(".ai.md"):
            full_version = f.parent / (f.name[:-len(".ai.md")] + ".md")
            if full_version.exists():
                continue

        st = f.stat()
        # Check if compressed version exists
        ai_path = f.with_suffix(".ai.md")
        has_compressed = ai_path.exists()

        # Check lock status (macOS chflags uchg or schg)
        locked = False
        try:
            flags = st.st_flags
            locked = bool(flags & (0x02 | 0x00020000))  # UF_IMMUTABLE | SF_IMMUTABLE
        except AttributeError:
            pass

        # Token estimate (~4 chars per token)
        raw_tokens = st.st_size // 4
        compressed_tokens = None
        if has_compressed:
            compressed_tokens = ai_path.stat().st_size // 4

        docs.append({
            "path": str(f.relative_to(SSOT_ROOT)),
            "name": f.stem,
            "layer": layer_name,
            "size": st.st_size,
            "rawTokens": raw_tokens,
            "compressedTokens": compressed_tokens,
            "hasCompressed": has_compressed,
            "locked": locked,
            "modified": st.st_mtime,
        })

    return docs

@app.route("/api/r-memory/documents")
def api_rmemory_documents():
    """List all SSoT documents across layers."""
    all_docs = []
    for layer in ["L0", "L1", "L2", "L3", "L4"]:
        layer_dir = SSOT_ROOT / layer
        all_docs.extend(_scan_ssot_layer(layer_dir, layer))
    return jsonify(all_docs)

@app.route("/api/r-memory/document", methods=["GET"])
def api_rmemory_document():
    """Read a single SSoT document. ?path=L1/FOO.md&compressed=true"""
    rel_path = request.args.get("path", "")
    use_compressed = request.args.get("compressed", "false").lower() == "true"

    if not rel_path or ".." in rel_path:
        return jsonify({"error": "invalid path"}), 400

    doc_path = SSOT_ROOT / rel_path
    if use_compressed:
        ai_path = doc_path.with_suffix(".ai.md")
        if ai_path.exists():
            doc_path = ai_path

    if not doc_path.exists():
        return jsonify({"error": "not found"}), 404

    return jsonify({
        "path": rel_path,
        "content": doc_path.read_text(),
        "size": doc_path.stat().st_size,
    })

@app.route("/api/r-memory/available-models", methods=["GET"])
def api_rmemory_available_models():
    """Return compression model options based on user's configured providers."""
    cheap_models = {
        "anthropic": {"model": "anthropic/claude-haiku-4-5", "label": "Claude Haiku 4.5 (cheap)"},
        "openai": {"model": "openai/gpt-4o-mini", "label": "GPT-4o Mini (cheap)"},
        "google": {"model": "google/gemini-2.0-flash", "label": "Gemini 2.0 Flash (cheap)"},
    }
    full_models = {
        "anthropic": [
            {"model": "anthropic/claude-haiku-4-5", "label": "Claude Haiku 4.5 (cheap)"},
            {"model": "anthropic/claude-sonnet-4-5", "label": "Claude Sonnet 4.5"},
            {"model": "anthropic/claude-opus-4-6", "label": "Claude Opus 4.6"},
        ],
        "openai": [
            {"model": "openai/gpt-4o-mini", "label": "GPT-4o Mini (cheap)"},
            {"model": "openai/gpt-4o", "label": "GPT-4o"},
        ],
        "google": [
            {"model": "google/gemini-2.0-flash", "label": "Gemini 2.0 Flash (cheap)"},
        ],
    }
    available = []
    try:
        auth_path = Path.home() / ".openclaw" / "agents" / "main" / "agent" / "auth-profiles.json"
        if auth_path.exists():
            data = json.loads(auth_path.read_text())
            seen_providers = set()
            for key, profile in data.get("profiles", {}).items():
                if profile.get("token"):
                    prov = profile.get("provider") or key.split(":")[0]
                    if prov not in seen_providers:
                        seen_providers.add(prov)
                        available.extend(full_models.get(prov, [{"model": f"{prov}/default", "label": prov}]))
    except Exception:
        pass
    if not available:
        # Fallback: read model from openclaw.json config
        try:
            cfg = json.loads(OPENCLAW_CONFIG.read_text())
            raw_model = cfg.get("agents", {}).get("defaults", {}).get("model", "") or cfg.get("model", "")
            # model can be string or {"primary": "...", "fallbacks": [...]}
            if isinstance(raw_model, dict):
                default_model = raw_model.get("primary", "")
            else:
                default_model = raw_model
            if default_model:
                provider = default_model.split("/")[0] if "/" in default_model else "unknown"
                available = full_models.get(provider, [{"model": default_model, "label": default_model}])
        except Exception:
            pass
    if not available:
        available = [{"model": "unknown", "label": "No models configured"}]
    return jsonify({"models": available})

@app.route("/api/r-memory/config", methods=["GET", "PUT"])
def api_rmemory_config():
    """Read or update R-Memory config (including compressionModel)."""
    if request.method == "GET":
        return jsonify(_rmem_config())
    # PUT — merge patch into existing config
    patch = request.get_json(force=True) or {}
    cfg = _rmem_config()
    cfg.update(patch)
    try:
        RMEMORY_CONFIG.write_text(json.dumps(cfg, indent=2))
        return jsonify({"ok": True, "config": cfg})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/r-memory/effective-models", methods=["GET"])
def api_rmemory_effective_models():
    """Return the actual runtime models."""
    return jsonify(_rmem_effective_models())


@app.route("/api/r-memory/narrative-model", methods=["PUT"])
def api_rmemory_narrative_model():
    """Update the narrative tracker model in camouflage.json."""
    patch = request.get_json(force=True) or {}
    model = patch.get("model")
    if not model:
        return jsonify({"error": "model required"}), 400
    camo_path = RMEMORY_DIR / "camouflage.json"
    try:
        camo = json.loads(camo_path.read_text()) if camo_path.exists() else {}
        pref = camo.get("preferredBackgroundProvider", "openai")
        bg = camo.get("backgroundModels", {})
        bg[f"{pref}-narrative"] = model
        camo["backgroundModels"] = bg
        camo_path.write_text(json.dumps(camo, indent=2))
        return jsonify({"ok": True, "narrativeModel": model})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/r-memory/open-log", methods=["POST"])
def api_rmemory_open_log():
    """Open R-Memory log in Terminal.app."""
    import subprocess
    # PLACEHOLDER: replace command with user-provided string
    cmd = "tail -f ~/.openclaw/workspace/r-memory/r-memory.log"
    subprocess.Popen([
        "osascript", "-e",
        f'tell application "Terminal" to do script "{cmd}"'
    ])
    return jsonify({"ok": True})


@app.route("/api/r-memory/stats")
def api_rmemory_stats():
    """R-Memory runtime stats: blocks from history files, log events."""
    # Get all history blocks (all sessions)
    all_blocks = _rmem_history_blocks()
    total_raw = sum(b.get("tokensRaw", 0) for b in all_blocks)
    total_comp = sum(b.get("tokensCompressed", 0) for b in all_blocks)

    # Current session blocks (stored in history file)
    cur_sid = _rmem_current_session_id()
    cur_blocks = [b for b in all_blocks if cur_sid and cur_sid in b.get("_file", "")]

    # Parse log to determine what's actually in context RIGHT NOW.
    # After a gateway restart (init), context is empty until first compaction.
    # Compressed blocks persist in conversation across gateway restarts.
    # Always show last compaction data if available.
    log_events = _rmem_parse_log()

    last_compaction = None
    for ev in log_events:
        if ev.get("event") == "compaction_done":
            last_compaction = ev

    in_context_blocks = last_compaction.get("historyBlocks", 0) if last_compaction else 0
    in_context_tokens = last_compaction.get("contentTokens", 0) if last_compaction else 0

    stats = {
        "blockCount": in_context_blocks,
        "contentTokens": in_context_tokens,
        "totalRawTokens": sum(b.get("tokensRaw", 0) for b in cur_blocks),
        "totalCompressedTokens": sum(b.get("tokensCompressed", 0) for b in cur_blocks),
        "compressionRatio": None,
        "storedBlockCount": len(cur_blocks),
        "allSessionsBlockCount": len(all_blocks),
        "allSessionsRawTokens": total_raw,
        "allSessionsCompressedTokens": total_comp,
        "currentSessionId": cur_sid,
        "logsExist": RMEMORY_LOG.exists(),
        "recentEvents": [],
    }

    if stats["totalRawTokens"] > 0:
        stats["compressionRatio"] = round(
            stats["totalCompressedTokens"] / stats["totalRawTokens"], 3
        )

    # Recent log events (last 30)
    stats["recentEvents"] = log_events[-30:]

    return jsonify(stats)


@app.route("/api/token-savings")
def api_token_savings():
    """Token savings & cost tracker. Uses R-Memory history data."""
    all_blocks = _rmem_history_blocks()
    total_raw = sum(b.get("tokensRaw", 0) for b in all_blocks)
    total_comp = sum(b.get("tokensCompressed", 0) for b in all_blocks)

    cur_sid = _rmem_current_session_id()
    cur_blocks = [b for b in all_blocks if cur_sid and cur_sid in b.get("_file", "")]
    sess_raw = sum(b.get("tokensRaw", 0) for b in cur_blocks)
    sess_comp = sum(b.get("tokensCompressed", 0) for b in cur_blocks)

    def _calc(raw, comp):
        saved = raw - comp
        input_saved = saved * 0.6
        output_saved = saved * 0.4
        cost = (input_saved * 5 / 1_000_000) + (output_saved * 25 / 1_000_000)
        # costWithout = what it would cost WITHOUT compression (full raw tokens)
        cost_without = (raw * 0.6 * 5 / 1_000_000) + (raw * 0.4 * 25 / 1_000_000)
        ratio = round(comp / raw, 3) if raw > 0 else None
        return {
            "rawTokens": raw,
            "compressedTokens": comp,
            "tokensSaved": saved,
            "costSaved": round(cost, 4),
            "costWithout": round(cost_without, 4),
            "compressionRatio": ratio,
        }

    # Estimate non-block tokens (system prompt, workspace, SSoT, conversation)
    # These are NOT compressed — they represent fixed overhead
    overhead_tokens = 12000  # system prompt
    for fname in ["AGENTS.md","SOUL.md","USER.md","TOOLS.md","IDENTITY.md","HEARTBEAT.md","MEMORY.md"]:
        fp = WORKSPACE / fname
        if fp.exists():
            try: overhead_tokens += len(fp.read_text()) // 4
            except: pass

    return jsonify({
        "session": _calc(sess_raw, sess_comp),
        "lifetime": _calc(total_raw, total_comp),
        "sessionBlocks": len(cur_blocks),
        "lifetimeBlocks": len(all_blocks),
        "overheadTokens": overhead_tokens,
    })


@app.route("/api/r-memory/lock/<path:doc_path>", methods=["POST"])
def api_rmemory_lock(doc_path):
    """Lock a document with chflags schg (requires sudo password)."""
    full_path = SSOT_ROOT / doc_path
    if not full_path.exists():
        return jsonify({"error": "not found"}), 404
    body = request.get_json(force=True) or {}
    password = body.get("password", "")
    if not password:
        return jsonify({"error": "password required — schg needs root"}), 403
    try:
        proc = subprocess.run(
            ["sudo", "-S", "chflags", "schg", str(full_path)],
            input=password.encode() + b"\n",
            capture_output=True, timeout=10
        )
        if proc.returncode == 0:
            return jsonify({"ok": True, "locked": True})
        else:
            return jsonify({"ok": False, "error": "lock failed (wrong password?)"}), 403
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/r-memory/unlock/<path:doc_path>", methods=["POST"])
def api_rmemory_unlock(doc_path):
    """Unlock a document. Requires sudo password in body."""
    full_path = SSOT_ROOT / doc_path
    if not full_path.exists():
        return jsonify({"error": "not found"}), 404

    body = request.get_json(force=True) or {}
    password = body.get("password", "")
    if not password:
        return jsonify({"error": "password required"}), 400

    try:
        proc = subprocess.run(
            ["sudo", "-S", "chflags", "noschg", str(full_path)],
            input=password.encode() + b"\n",
            capture_output=True, timeout=10
        )
        if proc.returncode == 0:
            return jsonify({"ok": True, "locked": False})
        else:
            return jsonify({"ok": False, "error": "unlock failed (wrong password?)"}), 403
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/r-memory/document", methods=["PUT"])
def api_rmemory_document_save():
    """Save/update a SSoT document."""
    body = request.get_json(force=True) or {}
    rel_path = body.get("path", "")
    content = body.get("content", "")
    if not rel_path or ".." in rel_path:
        return jsonify({"ok": False, "error": "invalid path"}), 400
    full_path = SSOT_ROOT / rel_path
    if not full_path.exists():
        return jsonify({"ok": False, "error": "not found"}), 404
    # Check lock
    try:
        if hasattr(full_path.stat(), "st_flags") and full_path.stat().st_flags & 0x02:
            return jsonify({"ok": False, "error": "document is locked"}), 403
    except Exception:
        pass
    try:
        full_path.write_text(content)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


SSOT_KEYWORDS_FILE = SSOT_ROOT / ".ssot-keywords.json"
R_AWARENESS_KEYWORDS_FILE = WORKSPACE / "r-awareness" / "keywords.json"

def _load_keywords():
    """Load dashboard keywords {docPath: [kw1, kw2, ...]}."""
    try:
        return json.loads(SSOT_KEYWORDS_FILE.read_text())
    except Exception:
        return {}

def _load_r_awareness_keywords():
    """Load R-Awareness keywords {keyword: docPath} and invert to dashboard format."""
    try:
        ra = json.loads(R_AWARENESS_KEYWORDS_FILE.read_text())
        # Invert: {kw: path} → {path: [kw1, kw2]}
        result = {}
        for kw, path in ra.items():
            result.setdefault(path, []).append(kw)
        return result
    except Exception:
        return {}

def _sync_to_r_awareness(data):
    """Write inverted keyword map to R-Awareness keywords.json. {docPath: [kws]} → {kw: docPath}.
    Dashboard uses .md paths; R-Awareness needs .ai.md paths (prefer compressed variant)."""
    inverted = {}
    for doc_path, kws in data.items():
        # Convert .md → .ai.md for R-Awareness if compressed variant exists
        ra_path = doc_path
        if doc_path.endswith(".md") and not doc_path.endswith(".ai.md"):
            ai_candidate = doc_path[:-3] + ".ai.md"
            if (SSOT_ROOT / ai_candidate).exists():
                ra_path = ai_candidate
        for kw in kws:
            inverted[kw.strip().lower()] = ra_path
    try:
        R_AWARENESS_KEYWORDS_FILE.parent.mkdir(parents=True, exist_ok=True)
        R_AWARENESS_KEYWORDS_FILE.write_text(json.dumps(inverted, indent=2))
    except Exception:
        pass  # Best-effort sync

def _save_keywords(data):
    SSOT_KEYWORDS_FILE.write_text(json.dumps(data, indent=2))
    _sync_to_r_awareness(data)

@app.route("/api/ssot/keywords", methods=["GET"])
@app.route("/api/r-memory/keywords", methods=["GET"])
def api_ssot_keywords_get():
    return jsonify(_load_keywords())

@app.route("/api/ssot/keywords", methods=["PUT"])
@app.route("/api/r-memory/keywords", methods=["PUT"])
def api_ssot_keywords_put():
    body = request.get_json(force=True) or {}
    path = body.get("path", "")
    keywords = body.get("keywords", [])
    if not path:
        return jsonify({"ok": False, "error": "path required"}), 400
    data = _load_keywords()
    if keywords:
        data[path] = keywords
    else:
        data.pop(path, None)
    _save_keywords(data)
    return jsonify({"ok": True})


@app.route("/api/r-memory/lock-layer/<layer>", methods=["POST"])
def api_rmemory_lock_layer(layer):
    """Lock all documents in a layer."""
    layer_dir = SSOT_ROOT / layer
    if not layer_dir.exists():
        return jsonify({"ok": False, "error": "layer not found"}), 404
    body = request.get_json(force=True) or {}
    password = body.get("password", "")
    if not password:
        return jsonify({"ok": False, "error": "password required — schg needs root"}), 403
    count = 0
    errors = []
    for f in layer_dir.rglob("*.md"):
        if f.name.startswith("."):
            continue
        try:
            proc = subprocess.run(
                ["sudo", "-S", "chflags", "schg", str(f)],
                input=password.encode() + b"\n",
                capture_output=True, timeout=10
            )
            if proc.returncode == 0:
                count += 1
            else:
                errors.append(f"{f.name}: lock failed")
        except Exception as e:
            errors.append(f"{f.name}: {e}")
    if errors and count == 0:
        return jsonify({"ok": False, "error": "lock failed (wrong password?)", "errors": errors}), 403
    return jsonify({"ok": True, "count": count, "errors": errors})


@app.route("/api/r-memory/unlock-layer/<layer>", methods=["POST"])
def api_rmemory_unlock_layer(layer):
    """Unlock all documents in a layer. Requires password."""
    layer_dir = SSOT_ROOT / layer
    if not layer_dir.exists():
        return jsonify({"ok": False, "error": "layer not found"}), 404
    body = request.get_json(force=True) or {}
    password = body.get("password", "")
    if not password:
        return jsonify({"ok": False, "error": "password required"}), 400
    count = 0
    errors = []
    for f in layer_dir.rglob("*.md"):
        if f.name.startswith("."):
            continue
        try:
            proc = subprocess.run(
                ["sudo", "-S", "chflags", "noschg", str(f)],
                input=password.encode() + b"\n",
                capture_output=True, timeout=10
            )
            if proc.returncode == 0:
                count += 1
            else:
                errors.append(f"{f.name}: unlock failed")
        except Exception as e:
            errors.append(f"{f.name}: {e}")
    if errors and count == 0:
        return jsonify({"ok": False, "error": "unlock failed (wrong password?)", "errors": errors}), 403
    return jsonify({"ok": True, "count": count, "errors": errors})


# ---------------------------------------------------------------------------
# API: Memory Health (context window + subsystem status)
# ---------------------------------------------------------------------------

@app.route("/api/memory/health")
def api_memory_health():
    """Memory subsystem health: context window, compression, FIFO status.
    
    Data sources (per R-Memory V4.6.1 Dashboard Data Guide):
    - history-{sessionId}.json → compressed blocks actually in context
    - config.json → compressTrigger, evictTrigger, blockSize
    - r-memory.log → compaction events, FIFO events, session events
    - Gateway WS → actual totalTokens for the session
    """
    config = _rmem_config()
    compress_trigger = config.get("compressTrigger", 36000)
    evict_trigger = config.get("evictTrigger", 80000)

    # --- Get current session blocks from history files ---
    cur_sid = _rmem_current_session_id()
    cur_blocks = _rmem_history_blocks(cur_sid) if cur_sid else []
    all_blocks = _rmem_history_blocks()

    stored_blocks_raw = sum(b.get("tokensRaw", 0) for b in cur_blocks)
    stored_blocks_comp = sum(b.get("tokensCompressed", 0) for b in cur_blocks)
    stored_blocks_count = len(cur_blocks)

    # --- Parse log events ---
    log_events = _rmem_parse_log()

    # Find last session start, compaction done events
    last_init = None
    last_compaction_done = None
    last_session = None
    compaction_count = 0
    fifo_events = []
    cache_hits = 0
    cache_misses = 0

    for ev in log_events:
        etype = ev.get("event", "")
        if etype == "init":
            last_init = ev
        elif etype == "session":
            last_session = ev
        elif etype == "compaction_done":
            last_compaction_done = ev
            compaction_count += 1
            cache_hits += ev.get("cacheHits", 0)
            cache_misses += ev.get("cacheMisses", 0)
        elif etype == "fifo_evicted":
            fifo_events.append(ev)

    # --- Determine actual in-context blocks ---
    # Compressed blocks persist in the conversation as <summary> across gateway
    # restarts. An init event does NOT clear them — only a new session does.
    # So we always show the last compaction data if available.
    blocks_count = stored_blocks_count
    blocks_comp = stored_blocks_comp
    blocks_raw = stored_blocks_raw
    # If history files are empty but compaction ran, use compaction data
    if blocks_count == 0 and last_compaction_done:
        blocks_comp = last_compaction_done.get("compressed", 0) or last_compaction_done.get("contentTokens", 0) or 0
        blocks_raw = last_compaction_done.get("raw", 0) or 0
        blocks_count = last_compaction_done.get("blocksSwapped", 0) or last_compaction_done.get("historyBlocks", 0) or 0

    # --- Gateway session data ---
    gw_session = _rmem_gateway_session()
    actual_total = gw_session.get("totalTokens", 0) if gw_session else 0
    max_tokens = gw_session.get("contextTokens", 200000) if gw_session else 200000
    model = gw_session.get("model") if gw_session else None

    # --- Estimate workspace file sizes ---
    workspace_tokens = 0
    for fname in ["AGENTS.md", "SOUL.md", "TOOLS.md", "USER.md", "MEMORY.md",
                   "IDENTITY.md", "HEARTBEAT.md"]:
        fpath = WORKSPACE / fname
        if fpath.exists():
            try:
                workspace_tokens += len(fpath.read_text()) // 4
            except Exception:
                pass

    # OpenClaw system prompt includes: core instructions, tool schemas, skill list,
    # runtime context, formatting rules, safety rules — typically 12-15k tokens.
    # Workspace files are counted separately below, so this is the non-workspace portion.
    system_prompt_tokens = 12000

    # SSoT docs — read actual injection data from R-Awareness log
    ssot_tokens = 0
    ssot_count = 0
    ssot_injected_docs = []
    try:
        ra_log = WORKSPACE / "r-awareness" / "r-awareness.log"
        if ra_log.exists():
            import re
            lines = ra_log.read_text().splitlines()
            # Find last injection event for count/tokens
            for line in reversed(lines):
                if "Injecting into system prompt" in line:
                    m = re.search(r'"docs":(\d+),"tokens":(\d+)', line)
                    if m:
                        ssot_count = int(m.group(1))
                        ssot_tokens = int(m.group(2))
                    break
            # Reconstruct injected doc set: collect unique docs from the last
            # injection cycle (human keywords + queued AI keywords before it)
            last_inject_idx = None
            for i in range(len(lines)-1, -1, -1):
                if "Injecting into system prompt" in lines[i]:
                    last_inject_idx = i
                    break
            if last_inject_idx is not None:
                # Collect docs from keyword match lines in this cycle
                all_docs = set()
                # Look backwards from injection to find the keyword lines that fed it
                prev_inject_idx = None
                for i in range(last_inject_idx-1, -1, -1):
                    if "Injecting into system prompt" in lines[i]:
                        prev_inject_idx = i
                        break
                start = (prev_inject_idx + 1) if prev_inject_idx is not None else 0
                for i in range(start, last_inject_idx + 1):
                    m = re.search(r'"docs":\[([^\]]*)\]', lines[i])
                    if m and m.group(1):
                        for d in m.group(1).split(","):
                            d = d.strip().strip('"')
                            if d:
                                all_docs.add(d)
                ssot_injected_docs = sorted(all_docs)[:ssot_count]  # Cap at actual injected count
    except Exception:
        pass
    # Fallback: scan all docs if no log data
    if ssot_count == 0:
        try:
            docs = []
            for layer in ["L0", "L1", "L2", "L3", "L4"]:
                docs.extend(_scan_ssot_layer(SSOT_ROOT / layer, layer))
            ssot_count = len(docs)
            ssot_tokens = sum(d.get("tokens", 0) for d in docs)
        except Exception:
            pass

    # Conversation = actual total - fixed segments - compressed blocks
    conversation_tokens = max(0, actual_total - system_prompt_tokens - workspace_tokens - ssot_tokens - blocks_comp)

    # --- Build result ---
    result = {
        "contextWindow": {
            "maxTokens": max_tokens,
            "actualTotalTokens": actual_total,
            "model": model,
            "lastInputTokens": gw_session.get("inputTokens", 0) if gw_session else 0,
            "lastOutputTokens": gw_session.get("outputTokens", 0) if gw_session else 0,
            "injectedSSoTs": ssot_count,
            "injectedSSoTDocs": ssot_injected_docs,
            "injectedBlocks": blocks_count,
            "segments": {
                "systemPrompt": system_prompt_tokens,
                "workspaceFiles": workspace_tokens,
                "ssotDocs": ssot_tokens,
                "conversation": conversation_tokens,
                "compressedBlocks": blocks_comp,
            },
            "status": "ok",
        },
        "subsystems": {},
        "lastTurn": None,
        "lastEventTs": None,
    }

    # Context window status
    if actual_total > 0:
        ratio = actual_total / max_tokens
        if ratio < 0.5:
            result["contextWindow"]["status"] = "ok"
        elif ratio < 0.75:
            result["contextWindow"]["status"] = "warning"
        else:
            result["contextWindow"]["status"] = "critical"

    # --- Subsystem: Plugin (R-Memory init) ---
    if last_init:
        cached = last_init.get("cachedBlocks", last_init.get("cachedTurns", 0))
        result["subsystems"]["plugin"] = {
            "label": "R-Memory Plugin",
            "status": "ok",
            "detail": f"V4.6.1 running, {cached} cached blocks, trigger: {compress_trigger}",
            "lastSeen": last_init.get("ts"),
        }
    else:
        result["subsystems"]["plugin"] = {
            "label": "R-Memory Plugin",
            "status": "error",
            "detail": "No init event found in log",
            "lastSeen": None,
        }

    # --- Subsystem: Injection (SSoT awareness) ---
    # R-Memory V4.6.1 doesn't emit injection events; SSoTs come from manifest
    if ssot_count > 0:
        result["subsystems"]["injection"] = {
            "label": "R-Awareness (Injection)",
            "status": "ok",
            "detail": f"{ssot_count} SSoT docs ({ssot_tokens} tok)",
            "lastSeen": last_init.get("ts") if last_init else None,
        }
    else:
        result["subsystems"]["injection"] = {
            "label": "R-Awareness (Injection)",
            "status": "idle",
            "detail": "No SSoT documents found",
            "lastSeen": None,
        }

    # --- Subsystem: Keyword Detection (from R-Awareness log) ---
    kw_events = []
    if R_AWARENESS_LOG.exists():
        try:
            ra_text = R_AWARENESS_LOG.read_text(errors="ignore")
            kw_re = re.compile(
                r'^\[(\d{4}-\d{2}-\d{2}T[\d:.]+Z)\]\s+\[INFO\]\s+Human keywords matched\s+(\{.*\})',
                re.MULTILINE,
            )
            for m in kw_re.finditer(ra_text):
                try:
                    payload = json.loads(m.group(2))
                    kw_events.append({"ts": m.group(1), "keywords": payload.get("keywords", [])})
                except Exception:
                    pass
        except Exception:
            pass
    if kw_events:
        last_kw = kw_events[-1]
        result["subsystems"]["keywords"] = {
            "label": "Keyword Detection",
            "status": "ok",
            "detail": f"Last: {', '.join(last_kw['keywords'][:6])}",
            "lastSeen": last_kw["ts"],
        }
    else:
        result["subsystems"]["keywords"] = {
            "label": "Keyword Detection",
            "status": "idle",
            "detail": "No keyword triggers yet",
            "lastSeen": None,
        }

    # --- Subsystem: Compression ---
    if last_compaction_done:
        saving = last_compaction_done.get("saving", "?")
        swapped = last_compaction_done.get("turnsCompressed", 0)
        hit_rate = f"{cache_hits}/{cache_hits+cache_misses}" if (cache_hits + cache_misses) > 0 else "n/a"
        result["subsystems"]["compression"] = {
            "label": "Compression",
            "status": "ok",
            "detail": f"{blocks_count} blocks in context ({blocks_raw}→{blocks_comp} tok), "
                      f"saving: {saving}, cache: {hit_rate}",
            "lastSeen": last_compaction_done.get("ts"),
        }
    elif blocks_count > 0:
        ratio_str = f"{round(blocks_comp/blocks_raw*100)}%" if blocks_raw > 0 else "?"
        result["subsystems"]["compression"] = {
            "label": "Compression",
            "status": "ok",
            "detail": f"{blocks_count} blocks ({blocks_raw}→{blocks_comp} tok, {ratio_str})",
            "lastSeen": None,
        }
    else:
        result["subsystems"]["compression"] = {
            "label": "Compression",
            "status": "idle",
            "detail": f"No compression yet (trigger: {compress_trigger} total context)",
            "lastSeen": None,
        }

    # --- Subsystem: FIFO Eviction ---
    if fifo_events:
        last_fifo = fifo_events[-1]
        result["subsystems"]["eviction"] = {
            "label": "FIFO Eviction",
            "status": "ok",
            "detail": f"Last evicted block, {len(fifo_events)} total evictions",
            "lastSeen": last_fifo.get("ts"),
        }
    else:
        result["subsystems"]["eviction"] = {
            "label": "FIFO Eviction",
            "status": "idle",
            "detail": f"No evictions yet (trigger: {evict_trigger} compressed tok, current: {blocks_comp} tok)",
            "lastSeen": None,
        }

    # --- Conversation estimate (progress toward compression trigger) ---
    # Total context progress toward 36k trigger
    if actual_total > 0:
        pct = min(100, round((actual_total / compress_trigger) * 100))
        result["conversationEstimate"] = {
            "tokens": actual_total,
            "trigger": compress_trigger,
            "percent": pct,
            "msgCount": None,  # not tracked in V4.6.1 log
        }

    # --- Last event ---
    if log_events:
        result["lastEventTs"] = log_events[-1].get("ts")

    return jsonify(result)

# ---------------------------------------------------------------------------
# API: Chatbots (SQLite-backed)
# ---------------------------------------------------------------------------

import sqlite3

CHATBOTS_DB = Path(__file__).parent / "chatbots.db"

def _get_db():
    db = sqlite3.connect(str(CHATBOTS_DB))
    db.row_factory = sqlite3.Row
    # Auto-migrate icon columns
    try:
        db.execute("ALTER TABLE chatbots ADD COLUMN icon TEXT DEFAULT '💬'")
    except Exception:
        pass
    try:
        db.execute("ALTER TABLE chatbots ADD COLUMN icon_type TEXT DEFAULT 'emoji'")
    except Exception:
        pass
    return db

@app.route("/api/chatbots")
def api_chatbots():
    """List all chatbots."""
    if not CHATBOTS_DB.exists():
        return jsonify([])
    db = _get_db()
    bots = [dict(r) for r in db.execute("SELECT * FROM chatbots ORDER BY created_at DESC").fetchall()]
    # Get conversation counts
    total_convos = 0
    for bot in bots:
        count = db.execute("SELECT COUNT(*) FROM chatbot_conversations WHERE chatbot_id=?", (bot["id"],)).fetchone()[0]
        bot["conversation_count"] = count
        total_convos += count
    db.close()
    active = sum(1 for b in bots if b.get("status") == "active")
    return jsonify({
        "chatbots": bots,
        "total": len(bots),
        "active": active,
        "totalConversations": total_convos,
        "avgSatisfaction": 0
    })

@app.route("/api/chatbots/<bot_id>")
def api_chatbot_detail(bot_id):
    """Get a single chatbot."""
    db = _get_db()
    bot = db.execute("SELECT * FROM chatbots WHERE id=?", (bot_id,)).fetchone()
    if not bot:
        db.close()
        return jsonify({"error": "not found"}), 404
    result = dict(bot)
    result["conversation_count"] = db.execute("SELECT COUNT(*) FROM chatbot_conversations WHERE chatbot_id=?", (bot_id,)).fetchone()[0]
    result["message_count"] = db.execute("SELECT COUNT(*) FROM chatbot_messages WHERE conversation_id IN (SELECT id FROM chatbot_conversations WHERE chatbot_id=?)", (bot_id,)).fetchone()[0]
    db.close()
    return jsonify(result)

@app.route("/api/chatbots", methods=["POST"])
def api_chatbot_create():
    """Create a new chatbot."""
    import uuid, time
    body = request.get_json(force=True)
    bot_id = uuid.uuid4().hex[:8]
    now = int(time.time() * 1000)
    db = _get_db()
    db.execute("""INSERT INTO chatbots (id, user_id, name, system_prompt, greeting, suggested_prompts,
        position, theme, primary_color, bg_color, text_color, allowed_domains,
        rate_per_minute, rate_per_hour, enable_analytics, show_watermark, status,
        created_at, updated_at, api_type, model_id, icon, icon_type)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (bot_id, "default", body.get("name", "New Chatbot"),
         body.get("system_prompt", "You are a helpful assistant."),
         body.get("greeting", "Hi! How can I help you?"),
         json.dumps(body.get("suggested_prompts", [])),
         body.get("position", "bottom-right"), body.get("theme", "dark"),
         body.get("primary_color", "#4ade80"), body.get("bg_color", "#1a1a1a"),
         body.get("text_color", "#e0e0e0"), body.get("allowed_domains", ""),
         body.get("rate_per_minute", 10), body.get("rate_per_hour", 100),
         1, 1, "active", now, now,
         body.get("api_type", "internal"), body.get("model_id", "claude-haiku"),
         body.get("icon", "💬"), body.get("iconType", "emoji")))
    db.commit()
    db.close()
    return jsonify({"ok": True, "id": bot_id})

@app.route("/api/chatbots/<bot_id>", methods=["PUT"])
def api_chatbot_update(bot_id):
    """Update a chatbot."""
    import time
    body = request.get_json(force=True)
    db = _get_db()
    bot = db.execute("SELECT id FROM chatbots WHERE id=?", (bot_id,)).fetchone()
    if not bot:
        db.close()
        return jsonify({"error": "not found"}), 404
    fields = ["name", "system_prompt", "greeting", "position", "theme",
              "primary_color", "bg_color", "text_color", "allowed_domains",
              "rate_per_minute", "rate_per_hour", "status", "model_id", "api_type",
              "icon", "icon_type"]
    # Map frontend camelCase to DB snake_case
    if "iconType" in body:
        body["icon_type"] = body.pop("iconType")
    updates = []
    values = []
    for f in fields:
        if f in body:
            updates.append(f"{f}=?")
            values.append(body[f])
    if updates:
        updates.append("updated_at=?")
        values.append(int(time.time() * 1000))
        values.append(bot_id)
        db.execute(f"UPDATE chatbots SET {','.join(updates)} WHERE id=?", values)
        db.commit()
    db.close()
    return jsonify({"ok": True})

@app.route("/api/chatbots/<bot_id>", methods=["DELETE"])
def api_chatbot_delete(bot_id):
    """Delete a chatbot and its data."""
    db = _get_db()
    db.execute("DELETE FROM chatbot_messages WHERE chatbot_id=?", (bot_id,))
    db.execute("DELETE FROM chatbot_conversations WHERE chatbot_id=?", (bot_id,))
    db.execute("DELETE FROM chatbots WHERE id=?", (bot_id,))
    db.commit()
    db.close()
    return jsonify({"ok": True})

@app.route("/api/chatbots/<bot_id>/conversations")
def api_chatbot_conversations(bot_id):
    """List conversations for a chatbot."""
    db = _get_db()
    convs = [dict(r) for r in db.execute(
        "SELECT * FROM chatbot_conversations WHERE chatbot_id=? ORDER BY started_at DESC LIMIT 50",
        (bot_id,)).fetchall()]
    db.close()
    return jsonify(convs)

# ---------------------------------------------------------------------------
# API: Widget Chat
# ---------------------------------------------------------------------------

@app.route("/api/widget/chat", methods=["POST"])
def api_widget_chat():
    """Handle chat messages from the embeddable widget."""
    data = request.get_json() or {}
    bot_id = data.get("botId")
    messages = data.get("messages", [])
    if not bot_id or not messages:
        return jsonify({"error": "botId and messages required"}), 400

    db = _get_db()
    bot = db.execute("SELECT * FROM chatbots WHERE id=?", (bot_id,)).fetchone()
    db.close()
    if not bot:
        return jsonify({"error": "chatbot not found"}), 404

    bot = dict(bot)
    system_prompt = bot.get("system_prompt", "")

    # Load API keys
    try:
        import json as _json
        auth_path = os.path.expanduser("~/.openclaw/agents/main/agent/auth-profiles.json")
        with open(auth_path) as f:
            auth = _json.load(f)
    except Exception as e:
        return jsonify({"error": f"Auth config not found: {e}"}), 500

    # Build messages
    api_messages = []
    for m in messages[-20:]:
        role = m.get("role", "user")
        if role in ("user", "assistant"):
            api_messages.append({"role": role, "content": m.get("content", "")})

    model_id = bot.get("model_id", "claude-sonnet")

    try:
        import urllib.request

        # Route to appropriate provider
        if model_id.startswith("gpt"):
            # OpenAI
            api_key = auth["profiles"]["openai:manual"]["token"]
            oai_model = {"gpt-4o": "gpt-4o", "gpt-4": "gpt-4"}.get(model_id, "gpt-4o")
            oai_messages = [{"role": "system", "content": system_prompt}] + api_messages
            req_body = _json.dumps({"model": oai_model, "max_tokens": 1024, "messages": oai_messages}).encode()
            req = urllib.request.Request(
                "https://api.openai.com/v1/chat/completions",
                data=req_body,
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = _json.loads(resp.read())
            reply = result["choices"][0]["message"]["content"]
        else:
            # Anthropic (default for claude-*)
            api_key = auth["profiles"]["anthropic:manual"]["token"]
            ant_model = {
                "claude-sonnet": "claude-sonnet-4-20250514",
                "claude-opus": "claude-opus-4-20250514",
                "claude-haiku": "claude-haiku-4-20250514",
            }.get(model_id, "claude-sonnet-4-20250514")
            req_body = _json.dumps({
                "model": ant_model, "max_tokens": 1024,
                "system": system_prompt, "messages": api_messages,
            }).encode()
            req = urllib.request.Request(
                "https://api.anthropic.com/v1/messages",
                data=req_body,
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                },
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = _json.loads(resp.read())
            reply = result.get("content", [{}])[0].get("text", "Sorry, I couldn't generate a response.")

        return jsonify({"reply": reply})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/widget.js")
def widget_js():
    """Serve the embeddable chat widget JavaScript."""
    return send_from_directory(
        os.path.join(os.path.dirname(__file__), "static"),
        "widget.js",
        mimetype="application/javascript",
    )

# ---------------------------------------------------------------------------
# API: Shield Status
# ---------------------------------------------------------------------------

@app.route("/api/shield/status")
def api_shield_status():
    """Shield status including file guard."""
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "file_guard",
            os.path.join(os.path.dirname(__file__), "..", "shield", "file_guard.py"),
        )
        fg = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fg)
        guard_status = fg.get_status()
        total_groups = len(guard_status)
        total_files = sum(g["total"] for g in guard_status.values())
        locked_files = sum(g["locked_count"] for g in guard_status.values())
        mode = "protected" if locked_files > 0 else "unlocked"
        return jsonify({
            "active": locked_files > 0,
            "available": True,
            "mode": mode,
            "file_guard": {
                "total_files": total_files,
                "locked_files": locked_files,
                "summary": {
                    "total_groups": total_groups,
                    "total_files": total_files,
                    "locked_files": locked_files,
                    "unlocked_files": max(0, total_files - locked_files),
                },
                "groups": guard_status,
            },
        })
    except Exception as e:
        return jsonify({
            "active": False,
            "available": False,
            "mode": "off",
            "error": str(e),
        })


@app.route("/api/shield/guard/status")
def api_shield_guard_status():
    """File guard status for all groups."""
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "file_guard",
            os.path.join(os.path.dirname(__file__), "..", "shield", "file_guard.py"),
        )
        fg = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fg)
        return jsonify(fg.get_status())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/shield/guard/lock", methods=["POST"])
def api_shield_guard_lock():
    """Lock a file group (requires password for schg). Body: {group: 'group_id', password: '...'} or {file: '/path', password: '...'}"""
    data = request.get_json(silent=True) or {}
    password = data.get("password", "")
    if not password:
        return jsonify({"error": "Password required — schg needs root"}), 403
    # Validate password
    check = subprocess.run(
        ["sudo", "-S", "echo", "ok"],
        input=password + "\n", capture_output=True, text=True, timeout=10,
    )
    if check.returncode != 0:
        return jsonify({"error": "Invalid password"}), 403
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "file_guard",
            os.path.join(os.path.dirname(__file__), "..", "shield", "file_guard.py"),
        )
        fg = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fg)
        if "group" in data:
            return jsonify(fg.lock_group(data["group"], password=password))
        elif "file" in data:
            return jsonify(fg.lock_file(data["file"], password=password))
        return jsonify({"error": "Provide 'group' or 'file'"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/shield/guard/unlock", methods=["POST"])
def api_shield_guard_unlock():
    """Unlock a file group. Requires password. Body: {group: 'group_id', password: '...'}"""
    data = request.get_json(silent=True) or {}
    password = data.get("password", "")
    if not password:
        return jsonify({"error": "Password required to unlock"}), 403
    # Validate password by attempting sudo -S with it
    check = subprocess.run(
        ["sudo", "-S", "echo", "ok"],
        input=password + "\n", capture_output=True, text=True, timeout=10,
    )
    if check.returncode != 0:
        return jsonify({"error": "Invalid password"}), 403
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "file_guard",
            os.path.join(os.path.dirname(__file__), "..", "shield", "file_guard.py"),
        )
        fg = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fg)
        if "group" in data:
            return jsonify(fg.unlock_group(data["group"], password=password))
        elif "file" in data:
            return jsonify(fg.unlock_file(data["file"], password=password))
        return jsonify({"error": "Provide 'group' or 'file'"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ---------------------------------------------------------------------------
# API: Logician Status
# ---------------------------------------------------------------------------

def _safe_logician_filename(filename):
    name = Path(filename).name
    if name != filename:
        return None
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", name):
        return None
    return name


def _logician_rules_state():
    state = {"enabled": {}, "locked": []}
    if not LOGICIAN_ENABLED_RULES_FILE.exists():
        return state
    try:
        data = json.loads(LOGICIAN_ENABLED_RULES_FILE.read_text())
        if isinstance(data.get("enabled"), dict):
            state["enabled"] = data["enabled"]
        if isinstance(data.get("locked"), list):
            state["locked"] = data["locked"]
    except Exception:
        pass
    return state


def _save_logician_rules_state(state):
    LOGICIAN_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "enabled": state.get("enabled", {}),
        "locked": state.get("locked", []),
        "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    LOGICIAN_ENABLED_RULES_FILE.write_text(json.dumps(payload, indent=2))


def _logician_rule_summary(text):
    description = ""
    rules_count = 0
    facts_count = 0
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("%"):
            if not description:
                desc = line.lstrip("%").strip()
                if desc and not set(desc).issubset(set("=-_ ")):
                    description = desc
            continue
        if ":-" in line:
            rules_count += 1
        elif line.endswith("."):
            facts_count += 1
    if not description:
        description = "Logician rules"
    return description, rules_count, facts_count


@app.route("/api/logician/rules")
def api_logician_rules():
    """List available Logician rule files and enabled/locked state."""
    if not LOGICIAN_RULES_DIR.exists():
        return jsonify({"rules": [], "status": "unavailable"})

    state = _logician_rules_state()
    enabled_map = state.get("enabled", {})
    locked = set(state.get("locked", []))
    rules = []

    for fpath in sorted(LOGICIAN_RULES_DIR.glob("*")):
        if not fpath.is_file() or fpath.suffix.lower() not in {".mg", ".mangle"}:
            continue
        try:
            content = fpath.read_text()
            description, rules_count, facts_count = _logician_rule_summary(content)
        except Exception:
            content = ""
            description, rules_count, facts_count = ("Unreadable rule file", 0, 0)
        rules.append({
            "filename": fpath.name,
            "description": description,
            "rules": rules_count,
            "facts": facts_count,
            "enabled": bool(enabled_map.get(fpath.name, True)),
            "locked": fpath.name in locked,
        })

    return jsonify({"rules": rules, "status": "ok"})


@app.route("/api/logician/rules/<filename>")
def api_logician_rule_content(filename):
    """Read one Logician rule file."""
    safe_name = _safe_logician_filename(filename)
    if not safe_name:
        return jsonify({"error": "invalid filename"}), 400
    if not LOGICIAN_RULES_DIR.exists():
        return jsonify({"error": "rules directory not found"}), 404

    fpath = LOGICIAN_RULES_DIR / safe_name
    if not fpath.exists() or not fpath.is_file():
        return jsonify({"error": "rule not found"}), 404
    if fpath.suffix.lower() not in {".mg", ".mangle"}:
        return jsonify({"error": "unsupported rule file type"}), 400

    try:
        content = fpath.read_text()
        return jsonify({"filename": safe_name, "content": content})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/logician/rules/<filename>/toggle", methods=["POST"])
def api_logician_rule_toggle(filename):
    """Enable/disable one Logician rule in enabled_rules.json."""
    safe_name = _safe_logician_filename(filename)
    if not safe_name:
        return jsonify({"error": "invalid filename"}), 400
    if not LOGICIAN_RULES_DIR.exists():
        return jsonify({"error": "rules directory not found"}), 404

    fpath = LOGICIAN_RULES_DIR / safe_name
    if not fpath.exists() or not fpath.is_file():
        return jsonify({"error": "rule not found"}), 404
    if fpath.suffix.lower() not in {".mg", ".mangle"}:
        return jsonify({"error": "unsupported rule file type"}), 400

    data = request.get_json(silent=True) or {}
    if "enabled" not in data:
        return jsonify({"error": "enabled required"}), 400
    enabled = bool(data.get("enabled"))

    state = _logician_rules_state()
    locked = set(state.get("locked", []))
    if safe_name in locked:
        return jsonify({"error": "rule is locked"}), 403

    enabled_map = state.get("enabled", {})
    enabled_map[safe_name] = enabled
    state["enabled"] = enabled_map
    _save_logician_rules_state(state)
    return jsonify({"ok": True, "filename": safe_name, "enabled": enabled})


@app.route("/api/logician/status")
def api_logician_status():
    """Read Logician monitor status file (deterministic, no AI)."""
    status_file = str(REPO_ROOT / "logician" / "monitor" / "status.json")
    try:
        with open(status_file) as f:
            data = json.load(f)
        return jsonify(data)
    except FileNotFoundError:
        return jsonify({"status": "unknown", "error": "monitor not running"})
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)})


# ---------------------------------------------------------------------------
# API: System Info (openclaw status)
# ---------------------------------------------------------------------------

@app.route("/api/system/status")
def api_system_status():
    """Run `openclaw status --json` and return result."""
    try:
        result = subprocess.run(
            ["openclaw", "status", "--json"],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0:
            return jsonify(json.loads(result.stdout))
        else:
            # Try without --json
            result2 = subprocess.run(
                ["openclaw", "status"],
                capture_output=True, text=True, timeout=15
            )
            return jsonify({"raw": result2.stdout, "error": result2.stderr})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/system/restart", methods=["POST"])
def api_system_restart():
    """Restart OpenClaw gateway via SIGUSR1 (works for TUI and service modes)."""
    import signal
    try:
        # Find gateway process (node process on port 18789)
        result = subprocess.run(
            ["lsof", "-ti", "tcp:18789"], capture_output=True, text=True
        )
        pids = result.stdout.strip().split('\n')
        if not pids or not pids[0]:
            return jsonify({"ok": False, "error": "Gateway process not found on port 18789"}), 404
        # Send SIGUSR1 to trigger graceful restart
        pid = int(pids[0])
        os.kill(pid, signal.SIGUSR1)
        return jsonify({"ok": True, "message": f"SIGUSR1 sent to PID {pid}, restart initiated"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# ---------------------------------------------------------------------------
# API: Config
# ---------------------------------------------------------------------------

@app.route("/api/config")
def api_config():
    """Read openclaw.json (redacting sensitive fields)."""
    try:
        cfg = json.loads(OPENCLAW_CONFIG.read_text())
        # Redact token
        if "gateway" in cfg and "auth" in cfg["gateway"]:
            cfg["gateway"]["auth"]["token"] = "***"
        return jsonify(cfg)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ---------------------------------------------------------------------------
# API: Models
# ---------------------------------------------------------------------------

@app.route("/api/models")
def api_models():
    """List available models via gateway."""
    result = gw.request("models.list")
    return jsonify(result)

# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Projects API (Monday.com-inspired project manager)
# ---------------------------------------------------------------------------

PROJECTS_DIR = Path(__file__).parent / "data" / "projects"
PROJECTS_DIR.mkdir(parents=True, exist_ok=True)

import uuid as _uuid

def _load_projects():
    """Load all project JSON files."""
    projects = []
    for f in sorted(PROJECTS_DIR.glob("*.json")):
        if f.name.startswith("_"):
            continue
        try:
            projects.append(json.loads(f.read_text()))
        except Exception:
            pass
    return projects

def _save_project(project):
    """Save a single project to disk."""
    pid = project["id"]
    path = PROJECTS_DIR / f"{pid}.json"
    path.write_text(json.dumps(project, indent=2))
    return project

def _compute_metrics(project):
    """Compute task metrics for a project."""
    tasks = project.get("tasks", [])
    total = len(tasks)
    done = sum(1 for t in tasks if t.get("status") == "done")
    blocked = sum(1 for t in tasks if t.get("status") == "blocked")
    in_progress = sum(1 for t in tasks if t.get("status") == "in_progress")
    todo = sum(1 for t in tasks if t.get("status") == "todo")
    project["metrics"] = {
        "totalTasks": total,
        "completedTasks": done,
        "blockedTasks": blocked,
        "inProgressTasks": in_progress,
        "todoTasks": todo,
        "completionPercent": round(done / total * 100) if total else 0
    }
    return project

@app.route("/api/projects")
def api_projects_list():
    projects = _load_projects()
    for p in projects:
        _compute_metrics(p)
    return jsonify({"projects": projects})

@app.route("/api/projects/<project_id>")
def api_project_get(project_id):
    path = PROJECTS_DIR / f"{project_id}.json"
    if not path.exists():
        return jsonify({"error": "Project not found"}), 404
    project = json.loads(path.read_text())
    _compute_metrics(project)
    return jsonify(project)

@app.route("/api/projects", methods=["POST"])
def api_project_create():
    data = request.json or {}
    pid = data.get("id") or str(_uuid.uuid4())[:8]
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    project = {
        "id": pid,
        "name": data.get("name", "Untitled Project"),
        "description": data.get("description", ""),
        "status": data.get("status", "planning"),
        "priority": data.get("priority", "medium"),
        "icon": data.get("icon", "🚀"),
        "color": data.get("color", "#6C5CE7"),
        "createdAt": now,
        "updatedAt": now,
        "deadline": data.get("deadline"),
        "tags": data.get("tags", []),
        "tasks": data.get("tasks", [])
    }
    _save_project(project)
    _compute_metrics(project)
    return jsonify(project), 201

@app.route("/api/projects/<project_id>", methods=["PUT"])
def api_project_update(project_id):
    path = PROJECTS_DIR / f"{project_id}.json"
    if not path.exists():
        return jsonify({"error": "Project not found"}), 404
    project = json.loads(path.read_text())
    data = request.json or {}
    for key in ("name", "description", "status", "priority", "icon", "color", "deadline", "tags"):
        if key in data:
            project[key] = data[key]
    project["updatedAt"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    _save_project(project)
    _compute_metrics(project)
    return jsonify(project)

@app.route("/api/projects/<project_id>", methods=["DELETE"])
def api_project_delete(project_id):
    path = PROJECTS_DIR / f"{project_id}.json"
    if not path.exists():
        return jsonify({"error": "Project not found"}), 404
    path.unlink()
    return jsonify({"deleted": project_id})

# --- Task CRUD within a project ---

@app.route("/api/projects/<project_id>/tasks", methods=["POST"])
def api_task_create(project_id):
    path = PROJECTS_DIR / f"{project_id}.json"
    if not path.exists():
        return jsonify({"error": "Project not found"}), 404
    project = json.loads(path.read_text())
    data = request.json or {}
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    task = {
        "id": data.get("id") or str(_uuid.uuid4())[:8],
        "title": data.get("title", "Untitled Task"),
        "description": data.get("description", ""),
        "status": data.get("status", "todo"),
        "priority": data.get("priority", "medium"),
        "assignee": data.get("assignee"),
        "deadline": data.get("deadline"),
        "blockedBy": data.get("blockedBy"),
        "createdAt": now,
        "updatedAt": now,
        "completedAt": None
    }
    project.setdefault("tasks", []).append(task)
    project["updatedAt"] = now
    _save_project(project)
    return jsonify(task), 201

@app.route("/api/projects/<project_id>/tasks/<task_id>", methods=["PUT"])
def api_task_update(project_id, task_id):
    path = PROJECTS_DIR / f"{project_id}.json"
    if not path.exists():
        return jsonify({"error": "Project not found"}), 404
    project = json.loads(path.read_text())
    data = request.json or {}
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    for task in project.get("tasks", []):
        if task["id"] == task_id:
            for key in ("title", "description", "status", "priority", "assignee", "deadline", "blockedBy"):
                if key in data:
                    task[key] = data[key]
            task["updatedAt"] = now
            if data.get("status") == "done" and not task.get("completedAt"):
                task["completedAt"] = now
            elif data.get("status") != "done":
                task["completedAt"] = None
            project["updatedAt"] = now
            _save_project(project)
            return jsonify(task)
    return jsonify({"error": "Task not found"}), 404

@app.route("/api/projects/<project_id>/tasks/<task_id>", methods=["DELETE"])
def api_task_delete(project_id, task_id):
    path = PROJECTS_DIR / f"{project_id}.json"
    if not path.exists():
        return jsonify({"error": "Project not found"}), 404
    project = json.loads(path.read_text())
    before = len(project.get("tasks", []))
    project["tasks"] = [t for t in project.get("tasks", []) if t["id"] != task_id]
    if len(project["tasks"]) == before:
        return jsonify({"error": "Task not found"}), 404
    project["updatedAt"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    _save_project(project)
    return jsonify({"deleted": task_id})

# --- Bulk task reorder (drag-and-drop support) ---

@app.route("/api/projects/<project_id>/tasks/reorder", methods=["POST"])
def api_tasks_reorder(project_id):
    path = PROJECTS_DIR / f"{project_id}.json"
    if not path.exists():
        return jsonify({"error": "Project not found"}), 404
    project = json.loads(path.read_text())
    data = request.json or {}
    task_ids = data.get("taskIds", [])
    if task_ids:
        task_map = {t["id"]: t for t in project.get("tasks", [])}
        reordered = [task_map[tid] for tid in task_ids if tid in task_map]
        remaining = [t for t in project.get("tasks", []) if t["id"] not in task_ids]
        project["tasks"] = reordered + remaining
        _save_project(project)
    return jsonify({"ok": True})

# ---------------------------------------------------------------------------
# TODO API — aggregates project tasks + standalone todos
# ---------------------------------------------------------------------------

TODOS_FILE = Path(__file__).parent / "data" / "todos.json"


def _load_standalone_todos():
    if TODOS_FILE.exists():
        return json.loads(TODOS_FILE.read_text())
    return []


def _save_standalone_todos(todos):
    TODOS_FILE.parent.mkdir(parents=True, exist_ok=True)
    TODOS_FILE.write_text(json.dumps(todos, indent=2))


@app.route("/api/todo")
def api_todo_list():
    """Return all todos: project tasks + standalone, sorted by priority."""
    items = []
    priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}

    # Pull tasks from all projects
    projects = _load_projects()
    for p in projects:
        color = p.get("color", "#ffffff")
        pname = p.get("name", "")
        pid = p.get("id", "")
        icon = p.get("icon", "")
        for t in p.get("tasks", []):
            items.append({
                **t,
                "projectId": pid,
                "projectName": pname,
                "projectIcon": icon,
                "projectColor": color,
                "source": "project",
            })

    # Standalone todos
    for t in _load_standalone_todos():
        items.append({
            **t,
            "projectId": None,
            "projectName": None,
            "projectIcon": None,
            "projectColor": "#ffffff",
            "source": "standalone",
        })

    # Sort: incomplete first, then by priority, then by deadline
    def sort_key(item):
        done = 1 if item.get("status") == "done" else 0
        prio = priority_order.get(item.get("priority", "medium"), 2)
        dl = item.get("deadline") or "9999-12-31"
        return (done, prio, dl)

    items.sort(key=sort_key)
    return jsonify({"items": items, "count": len(items)})


@app.route("/api/todo/standalone", methods=["POST"])
def api_todo_create_standalone():
    """Create a standalone todo (not linked to any project)."""
    data = request.json or {}
    if not data.get("title"):
        return jsonify({"error": "Title required"}), 400
    todos = _load_standalone_todos()
    import uuid
    todo = {
        "id": str(uuid.uuid4())[:8],
        "title": data["title"],
        "description": data.get("description", ""),
        "status": data.get("status", "todo"),
        "priority": data.get("priority", "medium"),
        "deadline": data.get("deadline"),
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    }
    todos.append(todo)
    _save_standalone_todos(todos)
    return jsonify(todo), 201


@app.route("/api/todo/standalone/<todo_id>", methods=["PUT"])
def api_todo_update_standalone(todo_id):
    todos = _load_standalone_todos()
    for t in todos:
        if t["id"] == todo_id:
            data = request.json or {}
            for k in ("title", "description", "status", "priority", "deadline"):
                if k in data:
                    t[k] = data[k]
            t["updatedAt"] = datetime.now(timezone.utc).isoformat()
            if data.get("status") == "done" and not t.get("completedAt"):
                t["completedAt"] = datetime.now(timezone.utc).isoformat()
            _save_standalone_todos(todos)
            return jsonify(t)
    return jsonify({"error": "Not found"}), 404


@app.route("/api/todo/standalone/<todo_id>", methods=["DELETE"])
def api_todo_delete_standalone(todo_id):
    todos = _load_standalone_todos()
    todos = [t for t in todos if t["id"] != todo_id]
    _save_standalone_todos(todos)
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    """Start the dashboard server."""
    print(f"\n⚡ ResonantOS Dashboard v2")
    print(f"   Gateway: {GW_WS_URL}")
    print(f"   SSoT root: {SSOT_ROOT}")
    print(f"   Auth token: ***{GW_TOKEN[-6:]}" if GW_TOKEN else "   Auth token: (none)")

    gw.start()

    # Wait briefly for connection
    time.sleep(1)
    if gw.connected:
        print(f"   ✓ Gateway connected (connId: {gw.conn_id})")
    else:
        print(f"   ✗ Gateway not connected yet ({gw.error or 'connecting...'})")

    print(f"\n   Dashboard: http://localhost:19100\n")
    app.run(host="0.0.0.0", port=19100, debug=False)


if __name__ == "__main__":
    main()
