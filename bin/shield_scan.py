#!/usr/bin/env python3
"""Lightweight trustless code scanner (Shield Gate v2).

Scans a target directory for risky patterns and emits JSON report.

Changes from v1: see CHANGELOG_shield_scan.md
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# Directories to skip entirely
# ---------------------------------------------------------------------------
SKIP_DIRS = {
    ".git",
    "node_modules",
    "venv",
    ".venv",
    "__pycache__",
    "dist",
    "build",
    "target",
    ".clawhub",
    ".cache",
    "coverage",
    ".nyc_output",
}

# ---------------------------------------------------------------------------
# File extensions to scan
# ---------------------------------------------------------------------------
TEXT_EXTS = {
    # Scripts / server-side
    ".py", ".rb", ".go", ".rs", ".swift", ".php", ".pl", ".lua",
    ".java", ".c", ".cpp", ".h", ".cs",
    # JavaScript / TypeScript (all variants)
    ".js", ".ts", ".jsx", ".tsx", ".mjs", ".cjs", ".mts", ".cts",
    # Shell
    ".sh", ".bash", ".zsh", ".fish",
    # Windows scripting
    ".ps1", ".bat", ".cmd", ".vbs",
    # Data / config / infra
    ".json", ".yaml", ".yml", ".toml", ".ini", ".env", ".cfg", ".conf",
    # Markup / docs (can contain injected scripts)
    ".md", ".html", ".xml", ".plist",
    # Systemd/launchd units
    ".service", ".timer", ".socket",
}

# Extensionless filenames that should always be scanned
EXTENSIONLESS_NAMES = {"Makefile", "Dockerfile", "Jenkinsfile", "Vagrantfile"}

# ---------------------------------------------------------------------------
# Test-directory heuristics — findings here are downgraded to INFO severity
# ---------------------------------------------------------------------------
TEST_DIR_RE = re.compile(
    r"(^|[/\\])(test|tests|__tests__|spec|specs|fixtures?|mocks?)[/\\]",
    re.I,
)

# ---------------------------------------------------------------------------
# Detection patterns
# ---------------------------------------------------------------------------
PATTERNS = [
    # ── CRITICAL ──────────────────────────────────────────────────────────
    {
        "id": "api_key_exfiltration",
        "severity": "critical",
        "description": "API key / credential collection combined with outbound network call",
        "regex": re.compile(
            r"(OPENAI_API_KEY|ANTHROPIC_API_KEY|AWS_SECRET_ACCESS_KEY|id_rsa|\.ssh/)"
            r".*(requests\.|fetch\(|curl\s+https?://|urllib|axios|http\.)",
            re.I,
        ),
    },
    {
        "id": "curl_pipe_bash",
        "severity": "critical",
        "description": "curl/wget output piped directly to shell execution",
        "regex": re.compile(
            r"(curl|wget)\s+.*(http[s]?://.*\|.*\b(ba?sh|sh|zsh|python|perl|ruby)\b"
            r"|\-[Oo]\s+\S+.*&&.*chmod|--exec)",
            re.I,
        ),
    },
    {
        "id": "base64_shell_exec",
        "severity": "critical",
        "description": "Base64-encoded payload decoded and piped to shell",
        "regex": re.compile(
            r"base64\s+(-d|--decode|/decode).*\|.*(ba?sh|sh|python|perl)",
            re.I,
        ),
    },
    {
        "id": "pickle_rce",
        "severity": "critical",
        "description": "pickle.loads() / pickle.load() — Remote Code Execution risk with untrusted data",
        "regex": re.compile(r"pickle\.(loads|load)\s*\(", re.I),
    },
    # ── HIGH ───────────────────────────────────────────────────────────────
    {
        "id": "destructive_rm",
        "severity": "high",
        "description": "Potentially destructive recursive delete of root, home, or env-derived path",
        # Match: rm -rf / | rm -rf ~ | rm -rf HOME_VAR | rm -rf BRACE_HOME_VAR
        # Do NOT match: rm -rf /var/log/old  (safe cleanup of concrete paths)
        "regex": re.compile(
            r"rm\s+-rf\s+(/\s*$|/\s*[\"'\s]|~/?\s*$|~/?\s*[\"'\s]|[$][{]?HOME[}]?)",
            re.I | re.M,
        ),
    },
    {
        "id": "persistence_modification",
        "severity": "high",
        "description": "Shell profile / service persistence modification",
        # crontab -e/-r/-i are write ops; crontab -l is read-only (excluded)
        "regex": re.compile(
            r"(LaunchAgents|\.bashrc|\.zshrc|\.profile|crontab\s+-[eri\b]|systemctl\s+enable)",
            re.I,
        ),
    },
    {
        "id": "reverse_shell",
        "severity": "high",
        "description": "Reverse shell / bind shell pattern",
        "regex": re.compile(
            r"(bash\s+-i\s+>&|nc\s+-e\s+/bin/(ba?sh|sh)|"
            r"/dev/tcp/\d{1,3}\.\d{1,3}|"
            r"socket\.bind\(\s*\(\s*[\"']\s*[\"']|socket\.bind\(\s*\(\s*[\"']0\.0\.0\.0)",
            re.I,
        ),
    },
    {
        "id": "network_listener",
        "severity": "high",
        "description": "Network listener binding on all interfaces (0.0.0.0)",
        # Only flag explicit 0.0.0.0 bind — not generic 'websocket' usage
        "regex": re.compile(
            r"(0\.0\.0\.0\s*[,)]\s*\d{2,5}|"
            r"listen\s*\(\s*[\"']0\.0\.0\.0[\"']|"
            r"host\s*=\s*[\"']0\.0\.0\.0[\"'])",
            re.I,
        ),
    },
    {
        "id": "subprocess_shell_true",
        "severity": "high",
        "description": "subprocess with shell=True — command injection risk",
        "regex": re.compile(r"subprocess\.(run|Popen|call|check_output)\s*\([^)]*shell\s*=\s*True", re.I),
    },
    {
        "id": "chmod_world_writable",
        "severity": "high",
        "description": "chmod making file world-writable (777 / a+w / o+w)",
        "regex": re.compile(r"(chmod\s+(777|a\+w|o\+w|0777)|os\.chmod\s*\([^,)]+,\s*0o?777)", re.I),
    },
    # ── MEDIUM ─────────────────────────────────────────────────────────────
    {
        "id": "obfuscation_eval",
        "severity": "medium",
        "description": "Dynamic code execution — eval / exec with string arguments",
        # Exclude RegExp.exec() (.exec() method calls) and common DB exec patterns
        # by requiring eval/exec at start of expression, not as method call (.exec)
        "regex": re.compile(
            r"(?<!\.)(?<!\w)(eval|exec)\s*\((?!\s*\))"
            r"|base64\.(b64decode|decode)\s*\((?!.*codec)"
            r"|atob\s*\(",
            re.I,
        ),
    },
    {
        "id": "sensitive_file_access",
        "severity": "medium",
        "description": "Access to sensitive system files (credentials, secrets, history)",
        "regex": re.compile(
            r"(\.aws/credentials|\.ssh/(?:id_rsa|id_ed25519|known_hosts|authorized_keys)"
            r"|/etc/(shadow|passwd|sudoers)"
            r"|keychain|Keychain"
            r"|browser.{0,10}history"
            r"|Contacts\.sqlite"
            r"|LocalStorage|chrome.{0,20}cookies)",
            re.I,
        ),
    },
    {
        "id": "env_credential_exfil",
        "severity": "medium",
        "description": "Environment variable credential access combined with HTTP exfiltration",
        "regex": re.compile(
            r"(os\.environ|process\.env|getenv)\s*[\.\[](.*(?:TOKEN|KEY|SECRET|PASSWORD|PASS|PWD).*)"
            r".*?(requests\.|fetch\(|axios|http\.|urllib)",
            re.I | re.S,
        ),
    },
    {
        "id": "import_obfuscation",
        "severity": "medium",
        "description": "Dynamic import / __import__ obfuscation pattern",
        "regex": re.compile(r"__import__\s*\(|importlib\.import_module\s*\(", re.I),
    },
    {
        "id": "dns_exfil",
        "severity": "medium",
        "description": "Potential DNS exfiltration (secret embedded in hostname lookup)",
        "regex": re.compile(
            r"(socket\.getaddrinfo|gethostbyname|dns\.resolve)\s*\(.*f[\"'].*\{",
            re.I,
        ),
    },
]

SEV_ORDER = {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}

# ---------------------------------------------------------------------------
# Shebang detection for extensionless files
# ---------------------------------------------------------------------------
SHEBANG_RE = re.compile(r"^#!\s*/\S*(python|ruby|perl|node|bash|sh|zsh)\b", re.I)


def has_script_shebang(path: Path) -> bool:
    """Return True if the file starts with a recognised script shebang line."""
    try:
        with path.open("rb") as f:
            header = f.read(128)
        return bool(SHEBANG_RE.match(header.decode("utf-8", errors="replace")))
    except Exception:
        return False


# ---------------------------------------------------------------------------
# File selection
# ---------------------------------------------------------------------------

def is_text_candidate(path: Path) -> bool:
    suffix = path.suffix.lower()
    if suffix in TEXT_EXTS:
        return True
    # env variants: .env.local, .env.production, .env.test, etc.
    if path.name.startswith(".env"):
        return True
    # Extensionless well-known files
    if not suffix and path.name in EXTENSIONLESS_NAMES:
        return True
    # Extensionless files with a script shebang
    if not suffix:
        return has_script_shebang(path)
    return False


def walk_files(root: Path):
    for cur, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for fn in files:
            p = Path(cur) / fn
            if is_text_candidate(p):
                yield p


# ---------------------------------------------------------------------------
# Core scanning
# ---------------------------------------------------------------------------

def _is_in_test_dir(path: Path) -> bool:
    return bool(TEST_DIR_RE.search(str(path)))


def scan_file(path: Path) -> List[Dict]:
    findings = []
    in_test = _is_in_test_dir(path)
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            for i, line in enumerate(f, 1):
                s = line.strip()
                if not s or s.startswith("#"):
                    # Skip pure comment lines to reduce comment-triggered FPs
                    # (only single-line # comments; /* */ not handled here)
                    continue
                for pat in PATTERNS:
                    if pat["regex"].search(s):
                        severity = pat["severity"]
                        # Downgrade findings in test directories to "info"
                        if in_test and severity in ("high", "medium"):
                            severity = "info"
                        findings.append(
                            {
                                "file": str(path),
                                "line": i,
                                "pattern": pat["id"],
                                "severity": severity,
                                "description": pat["description"],
                                "in_test_dir": in_test,
                                "code_snippet": s[:300],
                            }
                        )
    except Exception:
        pass
    return findings


def summarize(findings: List[Dict]) -> Dict[str, int]:
    out: Dict[str, int] = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
    for f in findings:
        sev = f["severity"]
        out[sev] = out.get(sev, 0) + 1
    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(
        description="Shield Gate v2 — trustless static code scanner for OpenClaw skills/plugins."
    )
    ap.add_argument("target", help="Directory to scan")
    ap.add_argument("--out", help="Write JSON report to this file path")
    ap.add_argument(
        "--min-severity",
        choices=["critical", "high", "medium", "low", "info"],
        default="info",
        help="Only report findings at or above this severity (default: info)",
    )
    ap.add_argument(
        "--no-test-downgrade",
        action="store_true",
        help="Disable severity downgrade for findings inside test directories",
    )
    args = ap.parse_args()

    root = Path(args.target).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        print(json.dumps({"status": "error", "error": f"target not found: {root}"}))
        return 2

    min_sev = SEV_ORDER.get(args.min_severity, 0)

    scanned_files = 0
    all_findings: List[Dict] = []
    for p in walk_files(root):
        scanned_files += 1
        file_findings = scan_file(p)
        # Re-apply test downgrade if disabled
        if args.no_test_downgrade:
            for finding in file_findings:
                if finding["in_test_dir"]:
                    # Restore original severity from pattern definition
                    for pat in PATTERNS:
                        if pat["id"] == finding["pattern"]:
                            finding["severity"] = pat["severity"]
                            break
        all_findings.extend(file_findings)

    # Filter by min severity
    findings = [f for f in all_findings if SEV_ORDER.get(f["severity"], 0) >= min_sev]

    sev = summarize(findings)
    status = "clean"
    if sev["critical"] > 0 or sev["high"] > 0:
        status = "flagged"
    elif sev["medium"] > 0:
        status = "warning"

    report = {
        "status": status,
        "scanner": "shield_scan",
        "version": "2.0.0",
        "target": str(root),
        "scanned_files": scanned_files,
        "total_findings": len(all_findings),
        "shown_findings": len(findings),
        "summary": sev,
        "findings": sorted(
            findings,
            key=lambda f: (-SEV_ORDER.get(f["severity"], 0), f["file"], f["line"]),
        ),
    }

    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        out_path = Path(args.out).expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload, encoding="utf-8")

    print(payload)
    return 0 if status == "clean" else 1


if __name__ == "__main__":
    sys.exit(main())
