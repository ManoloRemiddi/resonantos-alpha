#!/usr/bin/env python3
"""
ResonantOS Watchdog Service v2
Monitors OpenClaw gateway, dashboard, logician, and shield-gate services.
Uses launchctl kickstart for reliable restarts (not subprocess.Popen).
Cleans stale ports/locks before restart attempts.
Logs all actions to watchdog.log.
Runs continuously via launchd (com.resonantos.watchdog).
"""

import json
import subprocess
import time
import os
import signal
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
LOG_FILE = BASE_DIR / "watchdog.log"
MAX_RESTART_ATTEMPTS = 3
CHECK_INTERVAL = 120
UID = str(os.getuid())
DEFAULT_GATEWAY_PORT = 18789
OPENCLAW_CONFIG = Path(os.environ.get("OPENCLAW_CONFIG_PATH", str(Path.home() / '.openclaw' / "openclaw.json")))

SERVICES = {
    "gateway": {
        "port": DEFAULT_GATEWAY_PORT,
        "health_url": f"http://localhost:{DEFAULT_GATEWAY_PORT}/health",
        "launchd_label": "ai.openclaw.gateway",
    },
    "dashboard": {
        "port": 19100,
        "health_url": "http://localhost:19100/",
        "launchd_label": "com.resonantos.dashboard",
    },
    "logician": {
        "port": None,
        "socket_path": "/tmp/mangle.sock",
        "launchd_label": "com.resonantos.logician",
    },
    "shield": {
        "port": 9999,
        "health_url": "http://localhost:9999/health",
        "launchd_label": "com.resonantos.shield",
    }
}

def log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {message}\n"
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(log_entry)
    print(log_entry.strip())


def get_gateway_port() -> int:
    raw_env = os.environ.get("OPENCLAW_GATEWAY_PORT", "").strip()
    if raw_env:
        try:
            port = int(raw_env)
            if 1 <= port <= 65535:
                return port
        except ValueError:
            pass

    try:
        if OPENCLAW_CONFIG.exists():
            cfg = json.loads(OPENCLAW_CONFIG.read_text())
            raw_port = cfg.get("gateway", {}).get("port", DEFAULT_GATEWAY_PORT)
            port = int(raw_port)
            if 1 <= port <= 65535:
                return port
    except Exception:
        pass

    return DEFAULT_GATEWAY_PORT


def refresh_gateway_service_config() -> int:
    port = get_gateway_port()
    SERVICES["gateway"]["port"] = port
    SERVICES["gateway"]["health_url"] = f"http://localhost:{port}/health"
    return port


def check_http(url):
    try:
        import urllib.request
        req = urllib.request.Request(url, method="GET")
        resp = urllib.request.urlopen(req, timeout=5)
        return resp.status < 500
    except Exception:
        return False

def check_socket(socket_path):
    if not socket_path:
        return False
    try:
        import socket
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(3)
        s.connect(socket_path)
        s.close()
        return True
    except Exception:
        return False

def check_service(name):
    if name == "gateway":
        refresh_gateway_service_config()
    svc = SERVICES[name]
    if svc.get("socket_path") and check_socket(svc["socket_path"]):
        return True
    if svc.get("health_url") and check_http(svc["health_url"]):
        return True
    return False

def kill_stale_port(port):
    if not port:
        return
    try:
        result = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0 and result.stdout.strip():
            for pid in result.stdout.strip().split("\n"):
                pid = pid.strip()
                if pid:
                    log(f"Killing stale process {pid} on port {port}")
                    try:
                        os.kill(int(pid), signal.SIGTERM)
                    except ProcessLookupError:
                        pass
            time.sleep(2)
            for pid in result.stdout.strip().split("\n"):
                pid = pid.strip()
                if pid:
                    try:
                        os.kill(int(pid), signal.SIGKILL)
                    except ProcessLookupError:
                        pass
    except Exception as e:
        log(f"Error killing stale port {port}: {e}")

def restart_service(name):
    if name == "gateway":
        refresh_gateway_service_config()
    svc = SERVICES[name]
    label = svc["launchd_label"]
    target = f"gui/{UID}/{label}"

    for attempt in range(1, MAX_RESTART_ATTEMPTS + 1):
        log(f"Restarting {name} via launchctl (attempt {attempt}/{MAX_RESTART_ATTEMPTS})")
        try:
            # Clean stale port holders first
            if svc.get("port"):
                kill_stale_port(svc["port"])

            # kickstart -k = kill existing + restart, -p = print PID
            result = subprocess.run(
                ["launchctl", "kickstart", "-kp", target],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode != 0:
                log(f"kickstart failed: {result.stderr.strip()}")
                # Fallback: bootout + bootstrap
                subprocess.run(["launchctl", "bootout", target],
                    capture_output=True, timeout=10)
                time.sleep(2)
                plist = os.path.expanduser(f"~/Library/LaunchAgents/{label}.plist")
                if os.path.exists(plist):
                    subprocess.run(["launchctl", "bootstrap", f"gui/{UID}", plist],
                        capture_output=True, timeout=10)
                else:
                    log(f"Plist missing: {plist}")
                    continue
            else:
                log(f"kickstart OK: {result.stdout.strip()}")

            time.sleep(8)

            if check_service(name):
                log(f"Successfully restarted {name}")
                return True
            else:
                log(f"{name} still not responding after attempt {attempt}")

        except Exception as e:
            log(f"Error restarting {name}: {e}")
        time.sleep(3)

    log(f"FAILED to restart {name} after {MAX_RESTART_ATTEMPTS} attempts")
    return False

def main():
    log("=" * 50)
    log("Watchdog v2 started")
    log(f"Gateway port: {refresh_gateway_service_config()}")
    log("=" * 50)

    while True:
        try:
            for name in SERVICES:
                if not check_service(name):
                    log(f"Service {name} is DOWN")
                    restart_service(name)
                else:
                    log(f"Service {name} is UP")
            time.sleep(CHECK_INTERVAL)
        except KeyboardInterrupt:
            log("Watchdog stopped by user")
            break
        except Exception as e:
            log(f"Watchdog error: {e}")
            time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
