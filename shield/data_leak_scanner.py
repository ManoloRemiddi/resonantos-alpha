#!/usr/bin/env python3
"""
Shield data leak scanner.

Scans git-added lines for secrets and other sensitive material. Intended for use
from the repo pre-push hook, but can also be run manually.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path


SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}

PATTERNS = {
    "OpenAI API Key": (
        re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
        "CRITICAL",
    ),
    "Anthropic API Key": (
        re.compile(r"\bsk-ant-[A-Za-z0-9\-]{20,}\b"),
        "CRITICAL",
    ),
    "GitHub Token": (
        re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"),
        "CRITICAL",
    ),
    "AWS Access Key": (
        re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
        "HIGH",
    ),
    "AWS Secret Key": (
        re.compile(r"(?i)aws[_\- ]?secret[_\- ]?access[_\- ]?key\s*[:=]\s*[A-Za-z0-9/+=]{40}"),
        "CRITICAL",
    ),
    "OpenClawGatewayTokenRule": (
        re.compile(r"Gateway[_\- ]?Token\b"),
        "HIGH",
    ),
    "BearerTokenRule": (
        re.compile(r"(?i)(?<![A-Za-z0-9])bearer\s+[A-Za-z0-9\-_.~+/]+=*"),
        "HIGH",
    ),
    "Private Key Block": (
        re.compile(r"-----BEGIN\s+(?:RSA|EC|DSA|OPENSSH|PGP)?\s*PRIVATE KEY-----"),
        "CRITICAL",
    ),
    "JWT Token": (
        re.compile(r"\beyJ[A-Za-z0-9\-_]{10,}\.eyJ[A-Za-z0-9\-_]{10,}\.[A-Za-z0-9\-_.+/=]{10,}\b"),
        "HIGH",
    ),
    "Slack Token": (
        re.compile(r"\bxox[baprs]\-[A-Za-z0-9\-]{10,}\b"),
        "HIGH",
    ),
    "Telegram Bot Token": (
        re.compile(r"\b\d{8,10}:[A-Za-z0-9_\-]{35}\b"),
        "HIGH",
    ),
    "Generic API Key Assignment": (
        re.compile(r"(?i)\b(?:api[_\- ]?key|token|secret|password|passwd|pwd)\b\s*[:=]\s*['\"]?[^\s'\"`]{8,}"),
        "HIGH",
    ),
    "Solana Secret Key": (
        re.compile(r"(?<![A-Za-z0-9])[1-9A-HJ-NP-Za-km-z]{64,88}(?![A-Za-z0-9])"),
        "HIGH",
    ),
    "Seed Phrase Assignment": (
        re.compile(r"(?i)\b(?:seed|mnemonic|recovery)\b\s*[:=]\s*.{20,}"),
        "HIGH",
    ),
    "Sensitive Memory Marker": (
        re.compile(r"(?i)\b(?:SOUL\.md|USER\.md|MEMORY\.md|auth-profiles\.json|id\.json)\b"),
        "MEDIUM",
    ),
}

ALLOWLIST_SUBSTRINGS = (
    "example.com",
    "example.org",
    "placeholder",
    "your_api_key",
    "sk-your-key-here",
    "dummy",
    "sample",
    "fake",
    "test-token",
    "changeme",
    "xxxxx",
    "00000000",
)


def run_git(repo_root: Path, args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=check,
    )


def repo_root_from(path: str | None) -> Path:
    base = Path(path or ".").resolve()
    result = run_git(base, ["rev-parse", "--show-toplevel"])
    return Path(result.stdout.strip())


def pick_diff_range(repo_root: Path, cli_range: str | None) -> tuple[str, str]:
    if cli_range:
        return cli_range, f"git diff {cli_range}"

    upstream = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    if upstream.returncode == 0 and upstream.stdout.strip():
        return "@{upstream}..HEAD", "git diff @{upstream}..HEAD"

    cached = run_git(repo_root, ["diff", "--cached", "--name-only"], check=False)
    if cached.returncode == 0 and cached.stdout.strip():
        return "--cached", "git diff --cached"

    prior = run_git(repo_root, ["rev-parse", "--verify", "HEAD~1"], check=False)
    if prior.returncode == 0:
        return "HEAD~1..HEAD", "git diff HEAD~1..HEAD"

    return "EMPTY_TREE", "git diff --cached"


def diff_text(repo_root: Path, diff_range: str) -> str:
    if diff_range == "--cached":
        result = run_git(repo_root, ["diff", "--cached", "--no-color", "--unified=0"], check=False)
        return result.stdout
    if diff_range == "EMPTY_TREE":
        empty_tree = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
        result = run_git(repo_root, ["diff", "--cached", "--no-color", "--unified=0", empty_tree], check=False)
        return result.stdout
    result = run_git(repo_root, ["diff", "--no-color", "--unified=0", diff_range], check=False)
    return result.stdout


def is_allowlisted(text: str) -> bool:
    lower = text.lower()
    return any(item in lower for item in ALLOWLIST_SUBSTRINGS)


def shannon_entropy(text: str) -> float:
    if not text:
        return 0.0
    counts = Counter(text)
    length = len(text)
    return -sum((count / length) * math.log2(count / length) for count in counts.values())


def high_entropy_match(line: str) -> dict | None:
    for match in re.finditer(r'["\']([A-Za-z0-9+/=_\-]{20,})["\']', line):
        candidate = match.group(1)
        if is_allowlisted(candidate):
            continue
        entropy = shannon_entropy(candidate)
        if entropy >= 4.5:
            return {
                "pattern": f"High-Entropy String ({entropy:.1f})",
                "severity": "MEDIUM",
                "match": candidate[:80] + ("..." if len(candidate) > 80 else ""),
            }
    return None


def scan_added_lines(diff: str) -> list[dict]:
    """Extract added diff lines and flag sensitive matches in those additions."""
    findings: list[dict] = []
    current_file = None
    current_line = 0

    for raw_line in diff.splitlines():
        if raw_line.startswith("+++ b/"):
            current_file = raw_line[6:]
            continue
        if raw_line.startswith("@@"):
            match = re.search(r"\+(\d+)", raw_line)
            if match:
                current_line = int(match.group(1))
            continue
        if raw_line.startswith("--- "):
            continue
        if raw_line.startswith("+") and not raw_line.startswith("+++"):
            line = raw_line[1:]
            line_no = current_line
            current_line += 1
            if not line.strip():
                continue

            for pattern_name, (pattern, severity) in PATTERNS.items():
                matched = pattern.search(line)
                if not matched:
                    continue
                match_text = matched.group(0)
                if is_allowlisted(match_text):
                    continue
                findings.append(
                    {
                        "file": current_file or "<unknown>",
                        "line": line_no,
                        "pattern": pattern_name,
                        "severity": severity,
                        "match": match_text[:120] + ("..." if len(match_text) > 120 else ""),
                    }
                )

            entropy_finding = high_entropy_match(line)
            if entropy_finding:
                findings.append(
                    {
                        "file": current_file or "<unknown>",
                        "line": line_no,
                        **entropy_finding,
                    }
                )
            continue
        if raw_line.startswith(" "):
            current_line += 1

    return findings


def filter_findings(findings: list[dict], minimum: str) -> list[dict]:
    cutoff = SEVERITY_ORDER[minimum]
    return [item for item in findings if SEVERITY_ORDER[item["severity"]] <= cutoff]


def print_report(findings: list[dict], source_label: str) -> None:
    if not findings:
        print(f"Shield data leak scan passed: no findings in {source_label}.")
        return

    findings = sorted(findings, key=lambda item: (SEVERITY_ORDER[item["severity"]], item["file"], item["line"]))
    print("Shield data leak scan blocked this push.\n")
    print(f"Source: {source_label}")
    print(f"Findings: {len(findings)}\n")
    for finding in findings:
        print(f"[{finding['severity']}] {finding['file']}:{finding['line']}")
        print(f"  Pattern: {finding['pattern']}")
        print(f"  Match:   {finding['match']}")


def main() -> int:
    """Parse CLI args, scan the selected git diff, and return a shell exit code."""
    parser = argparse.ArgumentParser(description="Scan git diffs for leaked secrets and sensitive content.")
    parser.add_argument("--repo", default=".", help="Repo path to scan")
    parser.add_argument("--diff-range", help="Explicit git diff range, for example origin/main..HEAD")
    parser.add_argument(
        "--min-severity",
        default="MEDIUM",
        choices=["CRITICAL", "HIGH", "MEDIUM", "LOW"],
        help="Lowest severity that should fail the scan",
    )
    parser.add_argument("--json", action="store_true", help="Emit findings as JSON")
    args = parser.parse_args()

    repo_root = repo_root_from(args.repo)
    diff_range, source_label = pick_diff_range(repo_root, args.diff_range)
    findings = scan_added_lines(diff_text(repo_root, diff_range))
    findings = filter_findings(findings, args.min_severity)

    if args.json:
        print(json.dumps({"repo": str(repo_root), "source": source_label, "findings": findings}, indent=2))
    else:
        print_report(findings, source_label)

    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
