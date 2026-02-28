#!/usr/bin/env python3
"""
ResonantOS Shield — Deterministic Data Leak Scanner

Scans outbound content (messages, git diffs, file writes) for private data.
No AI involved — pure regex + pattern matching + Logician query.

Categories:
  1. Credentials: API keys, tokens, passwords, seed phrases, keypairs
  2. Private files: MEMORY.md, USER.md, SOUL.md, auth-profiles, solana keypair
  3. Business data: SSOT L0 docs, business plans, financial data
  4. Personal data: bank details, phone numbers, addresses

Usage:
  python3 data_leak_scanner.py check <text>       # scan text
  python3 data_leak_scanner.py check-file <path>   # scan file content
  python3 data_leak_scanner.py check-diff <repo>    # scan staged git diff
  python3 data_leak_scanner.py pre-push <repo>      # full pre-push gate (queries Logician)

Exit codes: 0 = clean, 1 = leak detected, 2 = Logician denied, 3 = error
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ============================================================
# CONFIGURATION
# ============================================================

_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent

# Logician gRPC endpoint
LOGICIAN_HOST = os.environ.get("LOGICIAN_HOST", "localhost")
LOGICIAN_PORT = int(os.environ.get("LOGICIAN_PORT", "8080"))
GRPCURL = os.path.expanduser(os.environ.get("GRPCURL", "~/go/bin/grpcurl"))
PROTO_DIR = str(_PROJECT_ROOT / "logician" / "poc" / "mangle-service" / "proto")
PROTO_FILE = "mangle.proto"

# ============================================================
# CREDENTIAL PATTERNS (regex)
# ============================================================

CREDENTIAL_PATTERNS: Dict[str, List[re.Pattern]] = {
    "anthropic_api_key": [
        re.compile(r"sk-ant-[a-zA-Z0-9_-]{20,}"),
    ],
    "openai_api_key": [
        re.compile(r"sk-proj-[a-zA-Z0-9_-]{20,}"),
        re.compile(r"sk-[a-zA-Z0-9]{20,}"),  # generic OpenAI
    ],
    "github_token": [
        re.compile(r"ghp_[a-zA-Z0-9]{36,}"),
        re.compile(r"gho_[a-zA-Z0-9]{36,}"),
        re.compile(r"github_pat_[a-zA-Z0-9_]{22,}"),
    ],
    "slack_token": [
        re.compile(r"xox[bprs]-[a-zA-Z0-9\-]+"),
    ],
    "private_key_pem": [
        re.compile(r"-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----"),
        re.compile(r"-----BEGIN\s+EC\s+PRIVATE\s+KEY-----"),
        re.compile(r"-----BEGIN\s+OPENSSH\s+PRIVATE\s+KEY-----"),
    ],
    "solana_keypair": [
        # JSON array of 64 integers (solana keypair format)
        re.compile(r"\[\s*\d{1,3}(?:\s*,\s*\d{1,3}){60,}\s*\]"),
    ],
    "seed_phrase": [
        # 12 or 24 word BIP39 seed phrase (common starting words)
        re.compile(
            r"\b(abandon|ability|able|about|above|absent|absorb|abstract|absurd|abuse)"
            r"(\s+[a-z]{3,8}){11,23}\b",
            re.IGNORECASE,
        ),
    ],
    "generic_secret": [
        re.compile(r"(?i)(password|passwd|pwd)\s*[:=]\s*['\"]?[^\s'\"]{8,}"),
        re.compile(r"(?i)(secret|api_key|apikey|auth_token)\s*[:=]\s*['\"][^\s'\"]{8,}"),
    ],
    "bank_iban": [
        re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{4}\d{7}([A-Z0-9]?){0,16}\b"),
    ],
    "credit_card": [
        re.compile(r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13})\b"),
    ],
}

# ============================================================
# PRIVATE CONTENT FINGERPRINTS
# ============================================================

# Exact strings that should never appear in outbound content.
# These are structural markers from private files — if they appear
# in a git diff or message, something is leaking.

def _m(*parts: str) -> str:
    """Join parts to build marker strings that don't match themselves in source."""
    return "".join(parts)

PRIVATE_MARKERS: List[Tuple[str, str]] = [
    (_m("MEMORY", ".md - Long-Term Memory"), "memory_file"),
    (_m("USER", ".md - About Your Human"), "user_file"),
    (_m("SOUL", ".md - Who You Are"), "soul_file"),
    (_m("auth-profiles", ".json\":{\"type\""), "auth_config"),
    (_m("# MEMORY", ".md"), "memory_file"),
    (_m("Claude", " Max"), "subscription_info"),
    (_m("Cloud", "Max"), "subscription_info"),
]

WARN_MARKERS: List[Tuple[str, str]] = [
    (_m("Cosmo", "destiny"), "philosophy_internal"),
    (_m("Augmentatism", " Manifesto"), "philosophy_public"),
]

# Paths that contain intentional template content (not leaks)
TEMPLATE_PATHS = {"workspace-templates/"}

# File paths that should never be committed or shared
FORBIDDEN_FILE_PATTERNS: List[re.Pattern] = [
    re.compile(r"MEMORY\.md"),
    re.compile(r"USER\.md"),
    re.compile(r"auth-profiles\.json"),
    re.compile(r"\.config/solana/id\.json"),
    re.compile(r"\.ssh/.*(?:id_rsa|id_ed25519|id_ecdsa)(?!\.pub)"),
    re.compile(r"daily_claims\.json"),
    re.compile(r"onboarding\.json"),
    re.compile(r"\.env(?:\.local)?$"),
    re.compile(r"SSOT-L0-BUSINESS-PLAN"),
]

# Business-sensitive content markers
BUSINESS_MARKERS: List[Tuple[str, str]] = [
    (_m("revenue", " model"), "business_plan"),
    (_m("pricing", " strategy"), "business_plan"),
    (_m("financial", " projection"), "business_plan"),
    (_m("investor", " deck"), "business_plan"),
    (_m("token ", "allocation"), "tokenomics_internal"),
    (_m("vesting", " schedule"), "tokenomics_internal"),
]


# ============================================================
# SCANNER
# ============================================================


class ScanResult:
    """Result of a leak scan."""

    def __init__(self):
        self.clean = True
        self.findings: List[Dict] = []

    def add(self, category: str, pattern_name: str, match: str, line_num: int = 0):
        self.clean = False
        # Truncate match to avoid echoing the full secret
        display = match[:20] + "..." if len(match) > 20 else match
        self.findings.append(
            {
                "category": category,
                "pattern": pattern_name,
                "match": display,
                "line": line_num,
            }
        )

    def to_dict(self) -> Dict:
        return {"clean": self.clean, "findings": self.findings}

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    def summary(self) -> str:
        if self.clean:
            return "CLEAN — no leaks detected"
        lines = [f"LEAK DETECTED — {len(self.findings)} finding(s):"]
        for f in self.findings:
            loc = f"line {f['line']}" if f["line"] else "—"
            lines.append(f"  [{f['category']}] {f['pattern']}: {f['match']} ({loc})")
        return "\n".join(lines)


def scan_text(text: str) -> ScanResult:
    """Scan arbitrary text for data leaks."""
    result = ScanResult()

    for line_num, line in enumerate(text.splitlines(), 1):
        # Credential patterns
        for name, patterns in CREDENTIAL_PATTERNS.items():
            for pat in patterns:
                for m in pat.finditer(line):
                    result.add("credential", name, m.group(), line_num)

        # Private content markers (block)
        for marker, cat in PRIVATE_MARKERS:
            if marker.lower() in line.lower():
                result.add("private_content", cat, marker, line_num)

        # Warn-only markers (logged but don't block)
        for marker, cat in WARN_MARKERS:
            if marker.lower() in line.lower():
                result.add("warning", cat, marker, line_num)

        # Business-sensitive markers
        for marker, cat in BUSINESS_MARKERS:
            if marker.lower() in line.lower():
                result.add("business_sensitive", cat, marker, line_num)

    return result


def scan_file(path: str) -> ScanResult:
    """Scan a file for data leaks."""
    p = Path(path)
    if not p.exists():
        result = ScanResult()
        result.add("error", "file_not_found", str(path))
        return result

    # Check if the file itself is forbidden
    result = ScanResult()
    for pat in FORBIDDEN_FILE_PATTERNS:
        if pat.search(str(p)):
            result.add("forbidden_file", pat.pattern, str(p))

    # Scan content (skip binary)
    try:
        content = p.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return result

    text_result = scan_text(content)
    result.findings.extend(text_result.findings)
    if text_result.findings:
        result.clean = False
    return result


def scan_git_diff(repo_path: str, staged: bool = True) -> ScanResult:
    """Scan git diff for data leaks."""
    cmd = ["git", "-C", repo_path, "diff"]
    if staged:
        cmd.append("--cached")
    cmd.append("--no-color")

    try:
        diff = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if diff.returncode != 0:
            result = ScanResult()
            result.add("error", "git_diff_failed", diff.stderr[:100])
            return result
    except Exception as e:
        result = ScanResult()
        result.add("error", "git_error", str(e)[:100])
        return result

    # Also check which files are staged
    result = ScanResult()

    files_cmd = ["git", "-C", repo_path, "diff", "--cached", "--name-only"]
    files = subprocess.run(files_cmd, capture_output=True, text=True, timeout=5)
    for fname in files.stdout.strip().splitlines():
        if any(fname.startswith(tp) for tp in TEMPLATE_PATHS):
            continue
        for pat in FORBIDDEN_FILE_PATTERNS:
            if pat.search(fname):
                result.add("forbidden_file", pat.pattern, fname)

    # Scan only ADDED lines (lines starting with '+', skip diff headers '+++')
    # Exclude Logician rule definitions (they define patterns, not leak them)
    added_lines = "\n".join(
        line[1:] for line in diff.stdout.splitlines()
        if line.startswith("+") and not line.startswith("+++")
        and not line.startswith("+sensitive_pattern(")
    )
    text_result = scan_text(added_lines)
    result.findings.extend(text_result.findings)
    if text_result.findings:
        result.clean = False

    return result


# ============================================================
# LOGICIAN GATE
# ============================================================


def query_logician(query: str) -> Optional[str]:
    """Query the Logician (Mangle) via gRPC. Returns answer or None on failure."""
    if not os.path.exists(GRPCURL):
        return None

    cmd = [
        GRPCURL,
        "-plaintext",
        "-import-path", PROTO_DIR,
        "-proto", PROTO_FILE,
        "-d", json.dumps({"query": query, "program": ""}),
        f"{LOGICIAN_HOST}:{LOGICIAN_PORT}",
        "mangle.Mangle.Query",
    ]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        if proc.returncode == 0 and proc.stdout.strip():
            return proc.stdout.strip()
        return None
    except Exception:
        return None


def logician_approves_push(repo_name: str) -> Tuple[bool, str]:
    """
    Ask the Logician if a git push is allowed.
    Checks: is the path safe? Is push permission granted?
    Returns (approved, reason).
    """
    # Ensure trailing slash to match Mangle facts
    if not repo_name.endswith("/"):
        repo_name = repo_name + "/"
    # Check if Logician is running
    answer = query_logician(f'safe_path("{repo_name}")')
    if answer is None:
        return False, "Logician unreachable — push denied (fail-closed)"

    if "safe_path" not in (answer or ""):
        return False, f"Logician: path '{repo_name}' not in safe_path set"

    # Verify no forbidden output types are being leaked
    # (This is a policy check — the actual content scan is done separately)
    answer2 = query_logician('can_use_tool(/main, /git)')
    if answer2 is None or "can_use_tool" not in answer2:
        return False, "Logician: /main does not have /git permission"

    return True, "Logician approved"


# ============================================================
# PRE-PUSH HOOK INTEGRATION
# ============================================================


def pre_push_check(repo_path: str) -> int:
    """
    Full pre-push gate: scan diff + query Logician.
    Returns exit code (0=ok, 1=leak, 2=logician denied, 3=error).
    """
    print("[Shield] Running pre-push data leak scan...")

    # Step 1: Scan staged diff
    diff_result = scan_git_diff(repo_path, staged=False)

    # Also scan what's about to be pushed (added lines only)
    cmd = ["git", "-C", repo_path, "diff", "HEAD~1..HEAD", "--no-color"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if proc.returncode == 0:
            added_only = "\n".join(
                line[1:] for line in proc.stdout.splitlines()
                if line.startswith("+") and not line.startswith("+++")
                and not line.startswith("+sensitive_pattern(")
            )
            push_result = scan_text(added_only)
            diff_result.findings.extend(push_result.findings)
            if push_result.findings:
                diff_result.clean = False
    except Exception:
        pass

    # Filter: warnings don't block, only hard findings do
    hard_findings = [f for f in diff_result.findings if f["category"] != "warning"]
    if hard_findings:
        diff_result.findings = hard_findings  # show only blockers
        print(f"[Shield] ❌ BLOCKED — {diff_result.summary()}")
        return 1

    # Step 2: Query Logician
    repo_abs = str(Path(repo_path).resolve())
    approved, reason = logician_approves_push(repo_abs)

    if not approved:
        print(f"[Shield] ❌ BLOCKED — {reason}")
        return 2

    print(f"[Shield] ✅ {reason} — push allowed")
    return 0


# ============================================================
# GIT HOOK INSTALLER
# ============================================================


def install_pre_push_hook(repo_path: str) -> bool:
    """Install a pre-push hook that calls this scanner."""
    hook_dir = Path(repo_path) / ".git" / "hooks"
    hook_file = hook_dir / "pre-push"

    if not hook_dir.exists():
        print(f"Not a git repo: {repo_path}")
        return False

    # Backup existing hook
    if hook_file.exists():
        content = hook_file.read_text()
        if "data_leak_scanner" in content:
            print("Hook already installed")
            return True
        backup = hook_file.with_suffix(".pre-shield-backup")
        hook_file.rename(backup)
        print(f"Existing hook backed up to {backup}")

    scanner_path = Path(__file__).resolve()
    hook_content = f"""#!/bin/bash
# ResonantOS Shield — Data Leak Scanner (pre-push gate)
# Installed by data_leak_scanner.py — DO NOT EDIT
# Queries Logician + scans for credential/private data leaks

PYTHON=$(command -v python3 2>/dev/null || command -v python 2>/dev/null || echo python3)
RESULT=$($PYTHON "{scanner_path}" pre-push "$(git rev-parse --show-toplevel)")
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    echo "═══════════════════════════════════════════"
    echo "  Shield blocked this push (exit $EXIT_CODE)"
    echo "  Run: $PYTHON {scanner_path} check-diff ."
    echo "  to see details."
    echo "═══════════════════════════════════════════"
    exit 1
fi

exit 0
"""
    hook_file.write_text(hook_content)
    hook_file.chmod(0o755)
    print(f"Pre-push hook installed at {hook_file}")
    return True


# ============================================================
# CLI
# ============================================================


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "check":
        text = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else sys.stdin.read()
        result = scan_text(text)
        print(result.summary())
        sys.exit(0 if result.clean else 1)

    elif cmd == "check-file":
        if len(sys.argv) < 3:
            print("Usage: data_leak_scanner.py check-file <path>")
            sys.exit(3)
        result = scan_file(sys.argv[2])
        print(result.summary())
        sys.exit(0 if result.clean else 1)

    elif cmd == "check-diff":
        repo = sys.argv[2] if len(sys.argv) > 2 else "."
        result = scan_git_diff(repo)
        print(result.summary())
        sys.exit(0 if result.clean else 1)

    elif cmd == "pre-push":
        repo = sys.argv[2] if len(sys.argv) > 2 else "."
        sys.exit(pre_push_check(repo))

    elif cmd == "install-hook":
        repo = sys.argv[2] if len(sys.argv) > 2 else "."
        ok = install_pre_push_hook(repo)
        sys.exit(0 if ok else 3)

    elif cmd == "logician-status":
        answer = query_logician("agent(/main)")
        if answer:
            print(f"Logician: ONLINE\n{answer}")
        else:
            print("Logician: OFFLINE or unreachable")
        sys.exit(0 if answer else 1)

    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(3)


if __name__ == "__main__":
    main()
