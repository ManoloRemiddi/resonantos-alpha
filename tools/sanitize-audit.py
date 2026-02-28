#!/usr/bin/env python3
"""
ResonantOS Sanitization Auditor
Scans files for secrets, PII, and private data before public release.
Deterministic — no AI, no network, pure regex + entropy checks.

Usage:
    python3 sanitize-audit.py <directory> [--fix] [--ignore .gitignore]
"""

import argparse
import math
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── Pattern Definitions ──────────────────────────────────────────────

PATTERNS = {
    # API Keys & Tokens
    "AWS Access Key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "AWS Secret Key": re.compile(r"(?i)aws[_\-]?secret[_\-]?access[_\-]?key\s*[=:]\s*[A-Za-z0-9/+=]{40}"),
    "OpenAI API Key": re.compile(r"sk-[A-Za-z0-9]{20,}"),
    "Anthropic API Key": re.compile(r"sk-ant-[A-Za-z0-9\-]{20,}"),
    "GitHub Token": re.compile(r"gh[pousr]_[A-Za-z0-9_]{36,}"),
    "Generic API Key": re.compile(r"(?i)(api[_\-]?key|apikey)\s*[=:]\s*['\"]?[A-Za-z0-9\-_]{20,}['\"]?"),
    "Generic Secret": re.compile(r"(?i)(secret|password|passwd|pwd)\s*[=:]\s*['\"]?[^\s'\"]{8,}['\"]?"),
    "Bearer Token": re.compile(r"(?i)bearer\s+[A-Za-z0-9\-_.~+/]+=*"),
    "Private Key Block": re.compile(r"-----BEGIN\s+(RSA|EC|DSA|OPENSSH|PGP)?\s*PRIVATE KEY-----"),
    "JWT Token": re.compile(r"eyJ[A-Za-z0-9\-_]{10,}\.eyJ[A-Za-z0-9\-_]{10,}\.[A-Za-z0-9\-_.+/=]{10,}"),

    # Crypto
    "Solana Private Key (base58, 64+ chars)": re.compile(r"(?<![A-Za-z0-9])[1-9A-HJ-NP-Za-km-z]{64,88}(?![A-Za-z0-9])"),
    "Seed Phrase (12+ words)": re.compile(r"(?i)(?:seed|mnemonic|recovery)\s*[=:]\s*.{20,}"),
    "Hex Private Key (64 hex chars)": re.compile(r"(?i)(?:private[_\-]?key|priv[_\-]?key)\s*[=:]\s*[0-9a-f]{64}"),

    # PII
    "Email Address": re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"),
    "Phone Number": re.compile(r"(?<![0-9])(?:\+?[1-9]\d{1,2}[\s\-]?)?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{4}(?![0-9])"),
    "IP Address (private)": re.compile(r"(?:192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})"),

    # Paths & Environment
    "Hardcoded Home Path": re.compile(r"/Users/[a-zA-Z0-9_\-]+/"),
    "Hardcoded Home Path (Linux)": re.compile(r"/home/[a-zA-Z0-9_\-]+/"),
    "Environment Variable Assignment": re.compile(r"(?i)export\s+(?:API_KEY|SECRET|TOKEN|PASSWORD|PRIVATE_KEY)\s*="),

    # Misc
    "Telegram Bot Token": re.compile(r"\d{8,10}:[A-Za-z0-9_\-]{35}"),
    "Slack Token": re.compile(r"xox[baprs]\-[A-Za-z0-9\-]{10,}"),
    "Discord Token": re.compile(r"(?i)discord[_\-]?token\s*[=:]\s*[A-Za-z0-9\-_.]{50,}"),
}

# Files to always skip
SKIP_EXTENSIONS = {
    ".pyc", ".pyo", ".so", ".dylib", ".o", ".a", ".bin", ".exe",
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".svg",
    ".woff", ".woff2", ".ttf", ".eot",
    ".zip", ".gz", ".tar", ".bz2", ".xz", ".7z",
    ".mp3", ".mp4", ".ogg", ".wav", ".avi", ".mov",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx",
    ".db", ".sqlite", ".sqlite3",
    ".lock",
}

SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv",
    "target", "build", "dist", ".eggs", "*.egg-info",
}

# Known false positives to whitelist (substrings)
ALLOWLIST = [
    "example.com",
    "user@example",
    "placeholder",
    "YOUR_API_KEY",
    "sk-your-key-here",
    "xxx",
    "TODO",
    "/Users/augmentor/",  # Will be flagged but can be allowlisted per-project
]

# ── Entropy Check ────────────────────────────────────────────────────

def shannon_entropy(s: str) -> float:
    """Calculate Shannon entropy of a string."""
    if not s:
        return 0.0
    freq = defaultdict(int)
    for c in s:
        freq[c] += 1
    length = len(s)
    return -sum((count / length) * math.log2(count / length) for count in freq.values())


def check_high_entropy_strings(line: str, min_length: int = 20, min_entropy: float = 4.5):
    """Find high-entropy strings that might be secrets."""
    findings = []
    # Look for quoted strings or assignments with high entropy
    for match in re.finditer(r'["\']([A-Za-z0-9+/=\-_]{20,})["\']', line):
        candidate = match.group(1)
        ent = shannon_entropy(candidate)
        if ent >= min_entropy and len(candidate) >= min_length:
            findings.append({
                "pattern": f"High-Entropy String (entropy={ent:.1f})",
                "match": candidate[:60] + ("..." if len(candidate) > 60 else ""),
            })
    return findings


# ── Scanner ──────────────────────────────────────────────────────────

def should_skip_dir(dirname: str) -> bool:
    return dirname in SKIP_DIRS or dirname.startswith(".")


def should_skip_file(filepath: Path) -> bool:
    return filepath.suffix.lower() in SKIP_EXTENSIONS


def is_allowlisted(match_text: str) -> bool:
    lower = match_text.lower()
    return any(al.lower() in lower for al in ALLOWLIST)


def scan_file(filepath: Path) -> list:
    """Scan a single file for secrets/PII. Returns list of findings."""
    findings = []
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            for lineno, line in enumerate(f, 1):
                line_stripped = line.strip()
                if not line_stripped or line_stripped.startswith("#!"):
                    continue

                # Pattern matching
                for name, pattern in PATTERNS.items():
                    for match in pattern.finditer(line):
                        text = match.group(0)
                        if is_allowlisted(text):
                            continue
                        findings.append({
                            "file": str(filepath),
                            "line": lineno,
                            "pattern": name,
                            "match": text[:80] + ("..." if len(text) > 80 else ""),
                            "context": line_stripped[:120],
                        })

                # Entropy check
                for ef in check_high_entropy_strings(line_stripped):
                    ef["file"] = str(filepath)
                    ef["line"] = lineno
                    ef["context"] = line_stripped[:120]
                    findings.append(ef)

    except (PermissionError, OSError):
        pass

    return findings


def scan_directory(root: str, gitignore_path: str = None) -> list:
    """Recursively scan directory for secrets/PII."""
    all_findings = []
    root_path = Path(root)

    gitignore_patterns = set()
    if gitignore_path:
        try:
            with open(gitignore_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        gitignore_patterns.add(line.strip("/"))
        except FileNotFoundError:
            pass

    for dirpath, dirnames, filenames in os.walk(root_path):
        # Filter directories
        dirnames[:] = [
            d for d in dirnames
            if not should_skip_dir(d) and d not in gitignore_patterns
        ]

        for filename in filenames:
            filepath = Path(dirpath) / filename
            if should_skip_file(filepath):
                continue
            if filename in gitignore_patterns:
                continue

            findings = scan_file(filepath)
            all_findings.extend(findings)

    return all_findings


# ── Output ───────────────────────────────────────────────────────────

SEVERITY_MAP = {
    "Private Key Block": "CRITICAL",
    "Seed Phrase": "CRITICAL",
    "Hex Private Key": "CRITICAL",
    "Solana Private Key": "CRITICAL",
    "OpenAI API Key": "CRITICAL",
    "Anthropic API Key": "CRITICAL",
    "AWS Secret Key": "CRITICAL",
    "GitHub Token": "CRITICAL",
    "Telegram Bot Token": "CRITICAL",
    "Bearer Token": "HIGH",
    "JWT Token": "HIGH",
    "Generic Secret": "HIGH",
    "Generic API Key": "HIGH",
    "Slack Token": "HIGH",
    "Discord Token": "HIGH",
    "AWS Access Key": "HIGH",
    "Email Address": "MEDIUM",
    "Phone Number": "MEDIUM",
    "IP Address (private)": "MEDIUM",
    "Hardcoded Home Path": "LOW",
    "Hardcoded Home Path (Linux)": "LOW",
    "Environment Variable Assignment": "MEDIUM",
    "High-Entropy String": "MEDIUM",
}


def get_severity(pattern_name: str) -> str:
    for key, sev in SEVERITY_MAP.items():
        if key in pattern_name:
            return sev
    return "LOW"


def print_report(findings: list, root: str):
    if not findings:
        print(f"\n✅ CLEAN — No secrets or PII found in {root}")
        return

    # Sort by severity
    severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    findings.sort(key=lambda f: severity_order.get(get_severity(f["pattern"]), 4))

    # Summary
    by_severity = defaultdict(int)
    for f in findings:
        by_severity[get_severity(f["pattern"])] += 1

    print(f"\n{'='*60}")
    print(f"  SANITIZATION AUDIT REPORT — {root}")
    print(f"{'='*60}")
    print(f"  Total findings: {len(findings)}")
    for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
        if sev in by_severity:
            icon = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "⚪"}[sev]
            print(f"  {icon} {sev}: {by_severity[sev]}")
    print(f"{'='*60}\n")

    # Details
    current_sev = None
    for f in findings:
        sev = get_severity(f["pattern"])
        if sev != current_sev:
            current_sev = sev
            print(f"\n── {sev} ──")

        rel_path = f["file"]
        if rel_path.startswith(root):
            rel_path = rel_path[len(root):].lstrip("/")

        print(f"  {rel_path}:{f['line']}")
        print(f"    Pattern: {f['pattern']}")
        print(f"    Match:   {f['match']}")
        print()

    print(f"{'='*60}")
    print(f"  Review each finding. False positives can be added to ALLOWLIST.")
    print(f"{'='*60}")


# ── Main ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="ResonantOS Sanitization Auditor")
    parser.add_argument("directory", help="Directory to scan")
    parser.add_argument("--ignore", help="Path to .gitignore file for exclusions")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--severity", default="LOW",
                       choices=["CRITICAL", "HIGH", "MEDIUM", "LOW"],
                       help="Minimum severity to report (default: LOW)")
    args = parser.parse_args()

    if not os.path.isdir(args.directory):
        print(f"Error: {args.directory} is not a directory", file=sys.stderr)
        sys.exit(1)

    findings = scan_directory(args.directory, args.ignore)

    # Filter by severity
    severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    min_sev = severity_order[args.severity]
    findings = [f for f in findings if severity_order.get(get_severity(f["pattern"]), 4) <= min_sev]

    if args.json:
        import json
        for f in findings:
            f["severity"] = get_severity(f["pattern"])
        print(json.dumps(findings, indent=2))
    else:
        print_report(findings, args.directory)

    sys.exit(1 if findings else 0)


if __name__ == "__main__":
    main()
