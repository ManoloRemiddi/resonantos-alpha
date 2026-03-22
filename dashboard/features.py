import json
from pathlib import Path

FEATURES = {}
_FEATURES_LOADED = False

DEFAULT_FEATURES = {
    "wallet": False,
    "tribes": False,
    "bounties": False,
    "protocol_store": False,
    "logician": False,
    "mcp": False,
}


def _load_features() -> dict:
    dashboard_dir = Path(__file__).resolve().parent
    config_path = dashboard_dir / "config.json"
    config_example = dashboard_dir / "config.example.json"

    loaded = {}
    if config_path.exists():
        try:
            with open(config_path) as f:
                cfg = json.load(f)
            features_cfg = cfg.get("features", {})
            for key, default in DEFAULT_FEATURES.items():
                loaded[key] = features_cfg.get(key, default)
        except Exception:
            loaded = dict(DEFAULT_FEATURES)
    elif config_example.exists():
        try:
            with open(config_example) as f:
                cfg = json.load(f)
            features_cfg = cfg.get("features", {})
            for key, default in DEFAULT_FEATURES.items():
                loaded[key] = features_cfg.get(key, default)
        except Exception:
            loaded = dict(DEFAULT_FEATURES)
    else:
        loaded = dict(DEFAULT_FEATURES)

    return loaded


def init_features():
    global FEATURES, _FEATURES_LOADED
    if not _FEATURES_LOADED:
        FEATURES = _load_features()
        _FEATURES_LOADED = True


def is_enabled(flag: str) -> bool:
    init_features()
    return FEATURES.get(flag, False)


def get_all_flags() -> dict:
    init_features()
    return dict(FEATURES)


def get_context():
    from pathlib import Path
    openclaw_cfg = Path.home() / ".openclaw" / "openclaw.json"
    gw_url = "ws://127.0.0.1:18789"
    if openclaw_cfg.exists():
        try:
            import json
            cfg = json.loads(openclaw_cfg.read_text())
            gw_url = cfg.get("gateway", {}).get("wsUrl", gw_url)
        except Exception:
            pass
    return {"features": get_all_flags(), "gateway_ws_url": gw_url}
