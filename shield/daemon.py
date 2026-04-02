#!/usr/bin/env python3
"""
Shield Daemon - 24/7 Security Monitoring Service

Provides:
- HTTP health check endpoint on localhost:9999
- Alert directory monitoring (polling-based, no external watchdog dependency)
- Graceful shutdown handling
- Comprehensive logging
- Linux-safe runtime paths
"""

from __future__ import annotations

import json
import logging
import os
import signal
import sys
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = Path(os.environ.get("SHIELD_CONFIG_PATH", str(REPO_ROOT / "shield" / "config.yaml"))).expanduser()
STATE_DIR = Path(os.environ.get("SHIELD_STATE_DIR", str(Path.home() / ".openclaw" / "shield"))).expanduser()


def _load_config() -> dict:
    try:
        if CONFIG_PATH.exists():
            data = yaml.safe_load(CONFIG_PATH.read_text())
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


CONFIG = _load_config()
HEALTH_PORT = int(os.environ.get("SHIELD_HEALTH_PORT", CONFIG.get("health_port", 9999)))
HEALTH_HOST = str(os.environ.get("SHIELD_HEALTH_HOST", CONFIG.get("health_host", "127.0.0.1")))
ALERTS_DIR = Path(
    os.path.expanduser(
        os.environ.get(
            "SHIELD_ALERTS_DIR",
            str(CONFIG.get("log_dir") or (STATE_DIR / "alerts")),
        )
    )
)
LOGS_DIR = Path(os.environ.get("SHIELD_LOG_DIR", str(STATE_DIR / "logs"))).expanduser()
LOG_FILE = LOGS_DIR / "shield_daemon.log"
PID_FILE = Path(os.environ.get("SHIELD_PID_FILE", str(STATE_DIR / "shield.pid"))).expanduser()

ALERTS_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)
PID_FILE.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("shield")


class ShieldState:
    """Global state for the Shield daemon."""

    def __init__(self):
        self.start_time = datetime.now()
        self.alerts_processed = 0
        self.last_alert_time = None
        self.running = True
        self.health_server: HTTPServer | None = None


state = ShieldState()


class HealthHandler(BaseHTTPRequestHandler):
    """HTTP handler for health check endpoint."""

    def log_message(self, format, *args):
        logger.debug("Health check: %s", args[0] if args else format)

    def do_GET(self):
        if self.path in {"/health", "/"}:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()

            uptime = (datetime.now() - state.start_time).total_seconds()
            response = {
                "status": "healthy",
                "service": "shield-daemon",
                "uptime_seconds": int(uptime),
                "alerts_processed": state.alerts_processed,
                "last_alert": state.last_alert_time.isoformat() if state.last_alert_time else None,
                "alerts_dir": str(ALERTS_DIR),
                "log_file": str(LOG_FILE),
                "pid_file": str(PID_FILE),
                "timestamp": datetime.now().isoformat(),
            }
            self.wfile.write(json.dumps(response, indent=2).encode())
            return

        if self.path == "/stats":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()

            alert_files = list(ALERTS_DIR.glob("*.json"))
            response = {
                "pending_alerts": len(alert_files),
                "alerts_processed": state.alerts_processed,
                "alerts_dir": str(ALERTS_DIR),
                "log_file": str(LOG_FILE),
                "config_path": str(CONFIG_PATH),
            }
            self.wfile.write(json.dumps(response, indent=2).encode())
            return

        self.send_response(404)
        self.end_headers()


class AlertProcessor:
    """Polling-based alert processor for new JSON alert files."""

    def process_alert(self, filepath: Path):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                alert = json.load(f)

            state.alerts_processed += 1
            state.last_alert_time = datetime.now()

            severity = alert.get("severity", "UNKNOWN")
            alert_type = alert.get("type", "UNKNOWN")
            logger.warning("🚨 ALERT [%s] %s: %s", severity, alert_type, alert.get("message", "No message"))

            archive_dir = ALERTS_DIR / "processed"
            archive_dir.mkdir(exist_ok=True)
            archive_path = archive_dir / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filepath.name}"
            filepath.rename(archive_path)
            logger.info("Alert archived to %s", archive_path)
        except Exception as e:
            logger.error("Error processing alert %s: %s", filepath, e)

    def process_pending(self):
        for alert_file in sorted(ALERTS_DIR.glob("*.json")):
            self.process_alert(alert_file)


processor = AlertProcessor()


def run_daemon_loop():
    """Run the health server and alert polling loop."""
    server = HTTPServer((HEALTH_HOST, HEALTH_PORT), HealthHandler)
    server.timeout = 1
    state.health_server = server
    logger.info("Health endpoint listening on http://%s:%s/health", HEALTH_HOST, HEALTH_PORT)
    try:
        while state.running:
            server.handle_request()
            processor.process_pending()
    finally:
        server.server_close()



def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    sig_name = signal.Signals(signum).name
    logger.info("Received %s, shutting down gracefully...", sig_name)
    state.running = False



def write_pid():
    """Write PID file for process tracking."""
    with open(PID_FILE, "w", encoding="utf-8") as f:
        f.write(str(os.getpid()))



def main():
    """Main entry point for Shield daemon."""
    logger.info("=" * 50)
    logger.info("🛡️  Shield Daemon Starting")
    logger.info("=" * 50)
    logger.info("Config: %s", CONFIG_PATH)
    logger.info("Alerts dir: %s", ALERTS_DIR)
    logger.info("Log file: %s", LOG_FILE)

    write_pid()
    logger.info("PID: %s", os.getpid())

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    existing_alerts = list(ALERTS_DIR.glob("*.json"))
    if existing_alerts:
        logger.info("Processing %s existing alerts...", len(existing_alerts))
        processor.process_pending()

    logger.info("Shield daemon is now running.")
    try:
        run_daemon_loop()
    finally:
        if PID_FILE.exists():
            PID_FILE.unlink()
        logger.info("Shield daemon stopped.")


if __name__ == "__main__":
    main()
