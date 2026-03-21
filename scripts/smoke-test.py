#!/usr/bin/env python3
"""
ResonantOS Dashboard Smoke Tests
Validates dashboard boot and core pages on a fresh clone.
Run: python3 scripts/smoke-test.py
"""

import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen


SCRIPT_DIR = Path(__file__).resolve().parent.parent
DASHBOARD_DIR = SCRIPT_DIR / "dashboard"
SYS_PLATFORM = sys.platform


def find_free_port() -> int:
    with socket.socket() as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def wait_for_url(url: str, timeout: float = 15.0) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        try:
            urlopen(url, timeout=3.0)
            return True
        except URLError:
            time.sleep(0.5)
    return False


def check(name: str, condition: bool, detail: str = "") -> bool:
    status = "PASS" if condition else "FAIL"
    detail_str = f" — {detail}" if detail else ""
    print(f"  [{status}] {name}{detail_str}")
    return condition


class SmokeTest:
    def __init__(self, test_port: int, verbose: bool = False, json_output: bool = False):
        self.test_port = test_port
        self.verbose = verbose
        self.json_output = json_output
        self.results: list[dict] = []
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        self.dashboard_proc: subprocess.Popen | None = None

    def record(self, name: str, passed: bool, detail: str = ""):
        self.results.append({"name": name, "passed": passed, "detail": detail})
        if passed:
            self.passed += 1
        else:
            self.failed += 1

    def run(self) -> int:
        print(f"\nResonantOS Dashboard Smoke Tests")
        print(f"{'=' * 50}")
        print(f"Platform: {SYS_PLATFORM}")
        print(f"Test port: {self.test_port}")
        print(f"Dashboard: {DASHBOARD_DIR}")
        print()

        try:
            self._test_config_files()
            self._test_import_server()
            self._test_dashboard_boot()
            self._test_core_routes()
        finally:
            self._stop_dashboard()

        self._report()
        return 0 if self.failed == 0 else 1

    def _test_config_files(self):
        print("1. Config File Validation")
        config_path = DASHBOARD_DIR / "config.json"
        example_path = DASHBOARD_DIR / "config.example.json"

        valid_config = True
        if config_path.exists():
            try:
                with open(config_path) as f:
                    json.load(f)
                valid_config = self.record("dashboard/config.json is valid JSON", True)
            except Exception as e:
                valid_config = self.record("dashboard/config.json is valid JSON", False, str(e))
        else:
            if example_path.exists():
                self.record("dashboard/config.json exists", False, "using config.example.json as fallback")
            else:
                self.record("dashboard/config.json exists", True, "no config needed — using defaults")

        if valid_config:
            self.record("Dashboard config: OK", True)

    def _test_import_server(self):
        print("\n2. Server Import")
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        proc = subprocess.run(
            [sys.executable, "-c", "import sys; sys.path.insert(0, '..'); import dashboard.server_v2"],
            cwd=DASHBOARD_DIR,
            capture_output=True,
            text=True,
            env=env,
            timeout=15,
        )
        if proc.returncode == 0:
            self.record("import dashboard.server_v2", True)
        else:
            stderr = proc.stderr.strip()
            self.record("import dashboard.server_v2", False, stderr[:200])

    def _start_dashboard(self) -> bool:
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        self.dashboard_proc = subprocess.Popen(
            [sys.executable, "server_v2.py", "--port", str(self.test_port)],
            cwd=DASHBOARD_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
        )
        dashboard_url = f"http://127.0.0.1:{self.test_port}/"
        started = wait_for_url(dashboard_url, timeout=20.0)
        if not started:
            if self.dashboard_proc.poll() is not None:
                stdout = self.dashboard_proc.stdout.read() if self.dashboard_proc.stdout else ""
                self.record("Dashboard boot", False, f"crashed: {stdout[:300]}")
            else:
                self.record("Dashboard boot", False, "timed out after 20s")
            self._stop_dashboard()
        return started

    def _test_dashboard_boot(self):
        print("\n3. Dashboard Boot")
        started = self._start_dashboard()
        if started:
            self.record("Dashboard responds on port", True)
            startup_output = ""
            if self.dashboard_proc and self.dashboard_proc.stdout:
                self.dashboard_proc.stdout.flush()
        else:
            self.record("Dashboard responds on port", False, "see above")

    def _test_core_routes(self):
        print("\n4. Core Routes")
        base = f"http://127.0.0.1:{self.test_port}/"
        routes = [
            ("", "Home page /"),
            ("agents", "Agents page"),
            ("chatbots", "Chatbots page"),
            ("docs", "Docs page"),
            ("settings", "Settings page"),
        ]

        if not self.dashboard_proc or self.dashboard_proc.poll() is not None:
            print("  SKIP — dashboard not running")
            for _, name in routes:
                self.record(f"Route: {name}", False, "dashboard not running")
                self.skipped += 1
            return

        for path, name in routes:
            url = base + path
            try:
                resp = urlopen(url, timeout=5.0)
                code = resp.getcode()
                passed = code == 200
                self.record(f"Route {path}: {name}", passed, f"HTTP {code}")
            except URLError as e:
                self.record(f"Route {path}: {name}", False, str(e)[:100])

    def _stop_dashboard(self):
        if self.dashboard_proc:
            try:
                if SYS_PLATFORM == "win32":
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(self.dashboard_proc.pid)],
                                   capture_output=True, timeout=5)
                else:
                    os.killpg(os.getpgid(self.dashboard_proc.pid), signal.SIGTERM)
                    self.dashboard_proc.wait(timeout=5)
            except (OSError, subprocess.TimeoutExpired):
                try:
                    if SYS_PLATFORM != "win32":
                        os.killpg(os.getpgid(self.dashboard_proc.pid), signal.SIGKILL)
                except OSError:
                    pass
            self.dashboard_proc = None

    def _report(self):
        total = self.passed + self.failed + self.skipped
        print(f"\n{'=' * 50}")
        print(f"Results: {self.passed} passed, {self.failed} failed, {self.skipped} skipped ({total} total)")

        if self.json_output:
            print(json.dumps({
                "passed": self.passed,
                "failed": self.failed,
                "skipped": self.skipped,
                "total": total,
                "results": self.results,
                "exit_code": 0 if self.failed == 0 else 1,
            }, indent=2))

        if self.failed > 0:
            print(f"\nFailed tests:")
            for r in self.results:
                if not r["passed"]:
                    print(f"  FAIL: {r['name']} — {r['detail']}")

        print()


def main():
    parser = argparse.ArgumentParser(description="ResonantOS Dashboard Smoke Tests")
    parser.add_argument("--port", type=int, default=0,
                        help="Port to run dashboard on (default: auto-select free port)")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    args = parser.parse_args()

    port = args.port if args.port else find_free_port()
    tester = SmokeTest(port, verbose=args.verbose, json_output=args.json)
    try:
        exit_code = tester.run()
    except KeyboardInterrupt:
        tester._stop_dashboard()
        print("\nInterrupted")
        exit_code = 130
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
