"""
Startup validation for ResonantOS Dashboard.
Reports issues gracefully at boot — warnings for optional systems, errors for required ones.
"""

import importlib.util
import json
import os
import sys
from pathlib import Path
from dataclasses import dataclass
from enum import Enum


class Severity(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class ValidationResult:
    name: str
    severity: Severity
    message: str
    fix: str | None = None


def _try_import(module_name: str) -> bool:
    spec = importlib.util.find_spec(module_name)
    return spec is not None


def _check_openclaw_config() -> ValidationResult:
    openclaw_json = Path.home() / ".openclaw" / "openclaw.json"
    if openclaw_json.exists():
        try:
            with open(openclaw_json) as f:
                json.load(f)
            return ValidationResult("openclaw_config", Severity.INFO, "OpenClaw config found")
        except Exception:
            return ValidationResult(
                "openclaw_config", Severity.WARNING,
                "OpenClaw config is malformed", "Run: openclaw gateway init"
            )
    return ValidationResult(
        "openclaw_config", Severity.WARNING,
        "OpenClaw config not found — some features may be unavailable",
        "Run: openclaw gateway init"
    )


def _check_solana_keypair() -> ValidationResult:
    keypair_path = Path.home() / ".config" / "solana" / "id.json"
    if keypair_path.exists():
        return ValidationResult("solana_keypair", Severity.INFO, "Solana keypair found")
    return ValidationResult(
        "solana_keypair", Severity.WARNING,
        "Solana keypair not found — wallet features disabled",
        "Create keypair at ~/.config/solana/id.json or use solana-keygen"
    )


def _check_optional_python_packages() -> list[ValidationResult]:
    results = []
    optional = {
        "solana": "solana",
        "solders": "solders",
        "anchorpy": "anchorpy",
    }
    all_ok = True
    missing = []
    for pkg, import_name in optional.items():
        if _try_import(import_name):
            results.append(ValidationResult(f"pkg_{pkg}", Severity.INFO, f"{pkg} installed"))
        else:
            missing.append(pkg)
            all_ok = False

    if missing:
        results.append(ValidationResult(
            "optional_packages", Severity.WARNING,
            f"Optional packages not installed: {', '.join(missing)}",
            "Install with: pip install " + " ".join(missing)
        ))
    return results


def _check_workspace_dirs() -> list[ValidationResult]:
    results = []
    workspace = Path.home() / ".openclaw" / "workspace"
    required = ["agents", "skills"]
    optional_workspace = ["r-memory", "r-awareness", "ssot"]

    for name in required:
        path = workspace / name
        if path.exists():
            results.append(ValidationResult(f"workspace_{name}", Severity.INFO, f"Workspace/{name} exists"))
        else:
            results.append(ValidationResult(
                f"workspace_{name}", Severity.ERROR,
                f"Required workspace directory missing: {path}",
                "Run: node install.js"
            ))

    for name in optional_workspace:
        path = workspace / name
        if path.exists():
            results.append(ValidationResult(f"workspace_{name}", Severity.INFO, f"{name} exists"))
        else:
            results.append(ValidationResult(
                f"workspace_{name}", Severity.WARNING,
                f"Optional workspace not found: {name}",
                None
            ))

    return results


def _check_dashboard_config() -> ValidationResult:
    dashboard_dir = Path(__file__).resolve().parent
    config_path = dashboard_dir / "config.json"
    if config_path.exists():
        try:
            with open(config_path) as f:
                json.load(f)
            return ValidationResult("dashboard_config", Severity.INFO, "Dashboard config found")
        except Exception:
            return ValidationResult(
                "dashboard_config", Severity.WARNING,
                "Dashboard config is malformed", "Fix or remove dashboard/config.json"
            )
    example_path = dashboard_dir / "config.example.json"
    if example_path.exists():
        return ValidationResult(
            "dashboard_config", Severity.WARNING,
            "Dashboard config.json not found — using defaults",
            f"Copy {example_path} to {config_path}"
        )
    return ValidationResult(
        "dashboard_config", Severity.INFO,
        "No dashboard config — using all defaults"
    )


def _check_repo_dir() -> ValidationResult | None:
    repo_dir_env = os.environ.get("RESONANTOS_REPO_DIR")
    if repo_dir_env:
        path = Path(repo_dir_env)
        if path.exists() and (path / "AGENTS.md").exists():
            return ValidationResult("repo_dir", Severity.INFO, f"RESONANTOS_REPO_DIR set: {repo_dir_env}")
        else:
            return ValidationResult(
                "repo_dir", Severity.WARNING,
                f"RESONANTOS_REPO_DIR set but path not found or invalid: {repo_dir_env}",
                None
            )
    return None


def run_startup_validation() -> list[ValidationResult]:
    results = []

    results.append(_check_openclaw_config())
    results.append(_check_dashboard_config())

    repo_check = _check_repo_dir()
    if repo_check:
        results.append(repo_check)

    results.extend(_check_workspace_dirs())
    results.extend(_check_optional_python_packages())
    results.append(_check_solana_keypair())

    return results


def print_validation_report(results: list[ValidationResult], verbose: bool = False) -> None:
    errors = [r for r in results if r.severity == Severity.ERROR]
    warnings = [r for r in results if r.severity == Severity.WARNING]
    infos = [r for r in results if r.severity == Severity.INFO]

    if errors:
        print("\n[ERROR] Startup validation failed:")
        for r in errors:
            print(f"  ✗ {r.message}")
            if r.fix:
                print(f"    Fix: {r.fix}")

    if warnings:
        print("\n[WARNING] Some features may be unavailable:")
        for r in warnings:
            print(f"  ⚠ {r.message}")
            if r.fix:
                print(f"    Fix: {r.fix}")

    if infos and verbose:
        print("\n[INFO] Startup checks passed:")
        for r in infos:
            print(f"  ✓ {r.message}")

    if not errors:
        print("\n[OK] Dashboard starting...")


if __name__ == "__main__":
    results = run_startup_validation()
    print_validation_report(results, verbose=True)
