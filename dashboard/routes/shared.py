"""Shared dashboard helpers used across route blueprints."""

from __future__ import annotations

import json
import os
import threading
import time
from datetime import timezone, datetime
from typing import Any

from routes.config import OPENCLAW_CONFIG, SSOT_ACCESS_FILE, _BOUNTIES_FILE, _PROFILES_FILE, _TRIBES_FILE
from routes.logging_config import get_logger

try:
    import websocket  # pip install websocket-client
except ImportError:
    websocket = None

logger = get_logger(__name__)

DEFAULT_GW_HOST = os.environ.get("OPENCLAW_GATEWAY_HOST", "127.0.0.1")
DEFAULT_GW_PORT = 18789


def _load_openclaw_config() -> dict[str, Any]:
    """Load the local OpenClaw config file when available."""
    try:
        if OPENCLAW_CONFIG.exists():
            data = json.loads(OPENCLAW_CONFIG.read_text())
            if isinstance(data, dict):
                return data
            logger.warning("Ignoring non-dict OpenClaw config at %s", OPENCLAW_CONFIG)
    except Exception:
        logger.warning("Failed to load OpenClaw config from %s", OPENCLAW_CONFIG, exc_info=True)
    return {}


def get_gw_host() -> str:
    """Return the local host used for dashboard → gateway websocket connections."""
    return DEFAULT_GW_HOST


def get_gw_port() -> int:
    """Return the configured local OpenClaw gateway port."""
    raw_env = os.environ.get("OPENCLAW_GATEWAY_PORT", "").strip()
    if raw_env:
        try:
            port = int(raw_env)
            if 1 <= port <= 65535:
                return port
        except ValueError:
            logger.warning("Ignoring invalid OPENCLAW_GATEWAY_PORT=%r", raw_env)

    cfg = _load_openclaw_config()
    raw_port = cfg.get("gateway", {}).get("port", DEFAULT_GW_PORT) if isinstance(cfg, dict) else DEFAULT_GW_PORT
    try:
        port = int(raw_port)
        if 1 <= port <= 65535:
            return port
    except (TypeError, ValueError):
        logger.warning("Invalid gateway.port in %s: %r", OPENCLAW_CONFIG, raw_port)
    return DEFAULT_GW_PORT


def get_gw_ws_url() -> str:
    """Return the local websocket URL for the OpenClaw gateway."""
    return f"ws://{get_gw_host()}:{get_gw_port()}"


GW_HOST = get_gw_host()
GW_PORT = get_gw_port()
GW_WS_URL = get_gw_ws_url()


def _load_ssot_access_store() -> dict[str, Any]:
    """Load persisted SSoT access rules from disk."""
    try:
        if SSOT_ACCESS_FILE.exists():
            data = json.loads(SSOT_ACCESS_FILE.read_text())
            if isinstance(data, dict):
                return data
            logger.warning("Ignoring non-dict SSoT access store at %s", SSOT_ACCESS_FILE)
    except Exception:
        logger.warning("Failed to load SSoT access store from %s", SSOT_ACCESS_FILE, exc_info=True)
    return {}


def _resolve_env_placeholder(value: str) -> str:
    """Resolve a simple ${VAR_NAME} placeholder from the current environment."""
    if not isinstance(value, str):
        return ""
    stripped = value.strip()
    if stripped.startswith("${") and stripped.endswith("}") and len(stripped) > 3:
        env_name = stripped[2:-1].strip()
        return os.environ.get(env_name, "")
    return value


def _read_gw_token() -> str:
    """Read the gateway auth token from OpenClaw config.

    Parse the configured gateway authentication settings and return the token
    used for the dashboard websocket client. Fall back to an empty string when
    the config file is missing, unreadable, or does not include the token.

    Dependencies:
        OPENCLAW_CONFIG: Path to the OpenClaw configuration file.

    Returns:
        str: The configured gateway token, or an empty string when unavailable.

    Called by:
        Module initialization for `GW_TOKEN`.

    Side effects:
        Reads the OpenClaw configuration file from disk.
    """
    cfg = _load_openclaw_config()
    gateway_cfg = cfg.get("gateway", {}) if isinstance(cfg, dict) else {}
    auth_cfg = gateway_cfg.get("auth", {}) if isinstance(gateway_cfg, dict) else {}
    token = auth_cfg.get("token", "") if isinstance(auth_cfg, dict) else ""
    token = token if isinstance(token, str) else ""
    return _resolve_env_placeholder(token)


GW_TOKEN = _read_gw_token()


def _load_bounties() -> list[dict[str, Any]]:
    """Load bounty records from the dashboard data file.

    Deserialize the stored bounty payload and normalize unexpected content to
    an empty list. Shield callers from file and JSON parsing failures by
    returning a safe default instead of raising.

    Dependencies:
        _BOUNTIES_FILE: Path to the bounty storage file.

    Returns:
        list[dict[str, Any]]: The persisted bounty records, or an empty list.

    Called by:
        Bounty-related routes and helpers that need current persisted data.

    Side effects:
        Reads the bounty storage file from disk.
    """
    try:
        data = json.loads(_BOUNTIES_FILE.read_text())
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_bounties(bounties: list[dict[str, Any]]) -> None:
    """Write bounty records to the dashboard data file.

    Ensure the parent directory exists before serializing the supplied bounty
    list with stable indentation. Persist the provided records exactly as
    passed so route handlers can store updated bounty state.

    Dependencies:
        _BOUNTIES_FILE: Path to the bounty storage file.

    Returns:
        None: This helper only persists data.

    Called by:
        Bounty-related routes and helpers that update stored bounty records.

    Side effects:
        Creates the parent directory when needed and writes JSON to disk.
    """
    _BOUNTIES_FILE.parent.mkdir(parents=True, exist_ok=True)
    _BOUNTIES_FILE.write_text(json.dumps(bounties, indent=2))


def _load_tribes() -> list[dict[str, Any]]:
    """Load tribe records from the dashboard data file.

    Deserialize the stored tribe payload and normalize unexpected content to an
    empty list. Return a safe default when the file is missing or malformed so
    callers can continue operating without extra error handling.

    Dependencies:
        _TRIBES_FILE: Path to the tribe storage file.

    Returns:
        list[dict[str, Any]]: The persisted tribe records, or an empty list.

    Called by:
        Tribe and bounty flows that need the current tribe dataset.

    Side effects:
        Reads the tribe storage file from disk.
    """
    try:
        data = json.loads(_TRIBES_FILE.read_text())
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_tribes(tribes: list[dict[str, Any]]) -> None:
    """Write tribe records to the dashboard data file.

    Ensure the parent directory exists before serializing the supplied tribe
    list with stable indentation. Preserve the provided data structure so route
    handlers can persist updated tribe state without extra transformation.

    Dependencies:
        _TRIBES_FILE: Path to the tribe storage file.

    Returns:
        None: This helper only persists data.

    Called by:
        Tribe and bounty flows that update stored tribe records.

    Side effects:
        Creates the parent directory when needed and writes JSON to disk.
    """
    _TRIBES_FILE.parent.mkdir(parents=True, exist_ok=True)
    _TRIBES_FILE.write_text(json.dumps(tribes, indent=2))


def _load_profiles() -> dict[str, Any]:
    """Load profile records from the dashboard data file.

    Deserialize the stored profile payload and normalize unexpected content to
    an empty mapping. Return a safe default when the file is missing or
    malformed so callers can consume profile data without extra guards.

    Dependencies:
        _PROFILES_FILE: Path to the profile storage file.

    Returns:
        dict[str, Any]: The persisted profile mapping, or an empty dict.

    Called by:
        Profile-related routes and helpers that need current persisted data.

    Side effects:
        Reads the profile storage file from disk.
    """
    try:
        data = json.loads(_PROFILES_FILE.read_text())
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_profiles(profiles: dict[str, Any]) -> None:
    """Write profile records to the dashboard data file.

    Ensure the parent directory exists before serializing the supplied profile
    mapping with stable indentation. Preserve the provided structure so callers
    can store updated profile state without extra transformation.

    Dependencies:
        _PROFILES_FILE: Path to the profile storage file.

    Returns:
        None: This helper only persists data.

    Called by:
        Profile-related routes and helpers that update stored profile data.

    Side effects:
        Creates the parent directory when needed and writes JSON to disk.
    """
    _PROFILES_FILE.parent.mkdir(parents=True, exist_ok=True)
    _PROFILES_FILE.write_text(json.dumps(profiles, indent=2))


def _sync_tribe_bounty_refs(tribes: list[dict[str, Any]], bounties: list[dict[str, Any]]) -> None:
    """Rebuild tribe bounty reference lists from bounty records.

    Reset each tribe's active and completed bounty collections, then repopulate
    them by scanning the current bounty list. Deduplicate and sort the stored
    identifiers so downstream consumers receive stable relationship data.

    Dependencies:
        None.

    Returns:
        None: The provided tribe records are updated in place.

    Called by:
        Tribe and bounty flows that need synchronized relationship metadata.

    Side effects:
        Mutates the supplied tribe dictionaries in place.
    """
    tribe_map = {t.get("id"): t for t in tribes if t.get("id")}
    for tribe in tribe_map.values():
        tribe["activeBounties"] = []
        tribe["completedBounties"] = []
    for bounty in bounties:
        tribe_id = bounty.get("tribeId")
        if not tribe_id or tribe_id not in tribe_map:
            continue
        bucket = "completedBounties" if bounty.get("status") == "rewarded" else "activeBounties"
        tribe_map[tribe_id][bucket].append(bounty.get("id"))
    for tribe in tribe_map.values():
        tribe["activeBounties"] = sorted(set(tribe.get("activeBounties", [])))
        tribe["completedBounties"] = sorted(set(tribe.get("completedBounties", [])))


def _enrich_bounty_with_tribe(bounty: dict[str, Any], tribe_map: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Attach tribe metadata to a bounty payload.

    Copy the supplied bounty record and add a normalized `tribe` object when a
    matching tribe exists in the provided lookup table. Preserve the original
    bounty input so callers receive an enriched payload without in-place edits.

    Dependencies:
        None.

    Returns:
        dict[str, Any]: A copied bounty payload with normalized tribe metadata.

    Called by:
        Bounty routes that need tribe details embedded in API responses.

    Side effects:
        None.
    """
    tribe_id = bounty.get("tribeId")
    tribe = tribe_map.get(tribe_id)
    out = dict(bounty)
    if tribe:
        out["tribe"] = {
            "id": tribe.get("id"),
            "name": tribe.get("name"),
            "category": tribe.get("category"),
            "members": tribe.get("members", []),
        }
    else:
        out["tribe"] = None
    return out


def _now_iso() -> str:
    """Return the current UTC timestamp in dashboard format.

    Generate an ISO 8601 timestamp in UTC with microseconds removed so stored
    values remain consistent across route responses. Normalize the timezone
    suffix to `Z` for compatibility with existing API consumers.

    Dependencies:
        datetime: Standard library UTC timestamp generation.

    Returns:
        str: The current UTC timestamp formatted as an ISO 8601 string.

    Called by:
        Route helpers that need a normalized current timestamp.

    Side effects:
        None.
    """
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class GatewayClient:
    """Persistent WS connection to OpenClaw gateway. Caches latest state."""

    def __init__(self) -> None:
        """Initialize gateway client state for websocket caching.

        Set up the connection flags, cached payload containers, synchronization
        primitives, and pending request registry used by the background
        websocket loop. Start with a disconnected, empty cache so callers can
        inspect state before the first gateway handshake completes.

        Dependencies:
            threading.Lock: Guards shared cached health state.

        Returns:
            None: This initializer only sets up instance state.

        Called by:
            `GatewayClient()` during module initialization.

        Side effects:
            Allocates in-memory synchronization primitives and caches.
        """
        self.connected: bool = False
        self.conn_id: str | None = None
        self.health: dict[str, Any] = {}
        self.features: dict[str, Any] = {}
        self.agents_snapshot: list[dict[str, Any]] = []
        self.sessions_snapshot: list[dict[str, Any]] = []
        self.last_tick: int = 0
        self.last_health_ts: int = 0
        self.error: str | None = None
        self._ws: Any = None
        self._lock = threading.Lock()
        self._msg_id: int = 0
        self._pending: dict[str, tuple[threading.Event, dict[str, Any] | None]] = {}

    def _next_id(self) -> str:
        """Generate the next outbound gateway request identifier.

        Increment the internal message counter and format the result using the
        request id pattern expected by this client. Keep identifier generation
        centralized so all pending-request bookkeeping uses the same scheme.

        Dependencies:
            None.

        Returns:
            str: The next unique request identifier for this client instance.

        Called by:
            `request()` before a websocket request is sent.

        Side effects:
            Increments the internal message counter.
        """
        self._msg_id += 1
        return f"r{self._msg_id}"

    def start(self) -> None:
        """Start the gateway background worker thread.

        Launch a daemon thread that continuously manages the websocket
        connection lifecycle for the dashboard. Return immediately so the app
        can continue booting while gateway connectivity is maintained in the
        background.

        Dependencies:
            threading.Thread: Runs the connection loop asynchronously.

        Returns:
            None: This method only starts background work.

        Called by:
            Application startup code that enables gateway connectivity.

        Side effects:
            Spawns a daemon thread targeting `_run()`.
        """
        t = threading.Thread(target=self._run, daemon=True)
        t.start()

    def _run(self) -> None:
        """Keep the gateway websocket connection alive.

        Repeatedly attempt to connect to the gateway and record any connection
        failure on the client state for later inspection. Sleep between retries
        so repeated failures do not spin the background thread aggressively.

        Dependencies:
            time.sleep: Provides retry backoff between connection attempts.

        Returns:
            None: This loop runs until process exit.

        Called by:
            The background thread started by `start()`.

        Side effects:
            Updates connection state and retries indefinitely in the background.
        """
        while True:
            try:
                self._connect()
            except Exception as e:
                self.connected = False
                self.error = str(e)
            time.sleep(3)

    def _send_connect(self, ws: Any, nonce: str | None = None) -> None:
        """Send the gateway connect request over the websocket.

        Build the operator connection payload expected by OpenClaw and transmit
        it through the active websocket. Use the module-level gateway token and
        fixed protocol metadata so the dashboard can establish admin access.

        Dependencies:
            GW_TOKEN: Shared gateway authentication token.

        Returns:
            None: This helper only transmits the connect payload.

        Called by:
            `_connect()` during the initial gateway handshake.

        Side effects:
            Sends a websocket message to the remote gateway.
        """
        connect_msg = {
            "type": "req",
            "id": "c0",
            "method": "connect",
            "params": {
                "auth": {"token": _read_gw_token()},
                "minProtocol": 3,
                "maxProtocol": 3,
                "role": "operator",
                "scopes": ["operator.admin"],
                "caps": [],
                "client": {"id": "gateway-client", "mode": "backend", "version": "2.0.0", "platform": "darwin"},
            },
        }
        ws.send(json.dumps(connect_msg))

    def _connect(self) -> None:
        """Open and maintain the live gateway websocket connection.

        Establish the websocket, complete the optional challenge handshake, and
        then process incoming messages until the socket becomes unusable. Fall
        back to periodic pings on receive timeouts and reset connection state
        when the loop exits.

        Dependencies:
            websocket: Third-party websocket client library for gateway access.

        Returns:
            None: This method runs until the active connection ends.

        Called by:
            `_run()` for each connection attempt.

        Side effects:
            Opens and closes a network connection and updates cached state.
        """
        if websocket is None:
            self.error = "websocket-client not installed (pip install websocket-client)"
            time.sleep(30)
            return
        ws = websocket.WebSocket()
        ws.settimeout(10)
        ws.connect(get_gw_ws_url())
        self._ws = ws

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
            self._send_connect(ws)

        ws.settimeout(60)
        while True:
            try:
                raw = ws.recv()
                if not raw:
                    break
                msg = json.loads(raw)
                self._handle(msg)
            except websocket.WebSocketTimeoutException:
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

    def _handle(self, msg: dict[str, Any]) -> None:
        """Handle a decoded gateway websocket message.

        Update connection metadata, cached health snapshots, and pending
        request waiters based on the message type and event payload. Centralize
        message routing here so websocket reads stay focused on transport flow.

        Dependencies:
            None.

        Returns:
            None: This helper applies message effects to client state.

        Called by:
            `_connect()` whenever a websocket message is received.

        Side effects:
            Mutates cached client state and may wake pending request waiters.
        """
        mtype = msg.get("type")

        if mtype == "res":
            mid = msg.get("id")
            if mid == "c0":
                if msg.get("ok"):
                    self.connected = True
                    self.error = None
                    payload = msg.get("payload", {})
                    self.conn_id = payload.get("server", {}).get("connId")
                    self.features = payload.get("features", {})
                else:
                    self.error = msg.get("error", {}).get("message", "connect failed")

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
                pass

    def request(self, method: str, params: dict[str, Any] | None = None, timeout: int = 10) -> dict[str, Any]:
        """Send a gateway request and wait for its response.

        Reject requests immediately when the websocket is unavailable, then
        register a pending waiter and transmit the outbound payload over the
        live socket. Return the received response, a timeout error, or a
        transport exception payload using the existing gateway API contract.

        Dependencies:
            threading.Event: Coordinates the synchronous wait for a response.

        Returns:
            dict[str, Any]: The gateway response payload or an error object.

        Called by:
            Route handlers that proxy dashboard requests to the gateway.

        Side effects:
            Sends a websocket request and mutates the pending request registry.
        """
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


gw = GatewayClient()
