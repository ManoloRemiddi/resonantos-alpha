#!/usr/bin/env python3
"""
Security Scanner for Skill Validation
Detects dangerous patterns in skill code before approval.

Patterns detected:
- API key theft (env var access for sensitive keys)
- File system attacks (deletion, sensitive path access)
- Network exfiltration (unauthorized external calls)
- Code injection (eval, exec)
- Credential harvesting
"""

import re
import os
import json
import sys
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, asdict
from enum import Enum

class Severity(Enum):
    CRITICAL = "critical"  # Auto-reject, likely malicious
    HIGH = "high"          # Requires manual review
    MEDIUM = "medium"      # Warning, may be legitimate
    LOW = "low"            # Informational

@dataclass
class SecurityFinding:
    rule_id: str
    severity: Severity
    message: str
    file_path: str
    line_number: int
    line_content: str
    recommendation: str

# =============================================================================
# SECURITY PATTERNS
# =============================================================================

DANGEROUS_PATTERNS = [
    # API Key Theft
    {
        "id": "SEC001",
        "name": "API Key Environment Access",
        "severity": Severity.CRITICAL,
        "patterns": [
            r"process\.env\.(ANTHROPIC|OPENAI|CLAUDE|API)_?(KEY|TOKEN|SECRET)",
            r"os\.environ\.get\(['\"]?(ANTHROPIC|OPENAI|CLAUDE|API)",
            r"os\.getenv\(['\"]?(ANTHROPIC|OPENAI|CLAUDE|API)",
            r"\$\{?(ANTHROPIC|OPENAI|CLAUDE)_?(KEY|TOKEN|SECRET)\}?",
        ],
        "recommendation": "Skills should never access API keys directly. Use sandbox credentials."
    },
    {
        "id": "SEC002",
        "name": "Generic Secret Access",
        "severity": Severity.HIGH,
        "patterns": [
            r"process\.env\.(SECRET|PASSWORD|CREDENTIAL|PRIVATE)",
            r"os\.environ\.get\(['\"]?(SECRET|PASSWORD|CREDENTIAL|PRIVATE)",
            r"\.env\s+file",
            r"dotenv",
        ],
        "recommendation": "Avoid accessing secrets. Request specific permissions if needed."
    },
    
    # File System Attacks
    {
        "id": "SEC003",
        "name": "Sensitive Path Access",
        "severity": Severity.CRITICAL,
        "patterns": [
            r"(/etc/passwd|/etc/shadow|~/.ssh|\.ssh/|id_rsa|authorized_keys)",
            r"(\.clawdbot/|clawdbot\.json|\.env$)",
            r"(/root/|/home/\w+/\.)",
            r"(~/.gnupg|\.gnupg/|\.aws/credentials|\.kube/config)",
        ],
        "recommendation": "Access to sensitive system paths is forbidden."
    },
    {
        "id": "SEC004",
        "name": "File Deletion Operations",
        "severity": Severity.HIGH,
        "patterns": [
            r"(rm\s+-rf|rmdir|unlink|os\.remove|os\.unlink|fs\.unlink|fs\.rm)",
            r"(shutil\.rmtree|pathlib.*\.unlink|rimraf)",
            r"(del\s+/[sq]|Remove-Item.*-Recurse)",
        ],
        "recommendation": "File deletion requires explicit approval. Document why it's needed."
    },
    {
        "id": "SEC005",
        "name": "File System Traversal",
        "severity": Severity.MEDIUM,
        "patterns": [
            r"\.\.\/|\.\.\\",
            r"path\.join\(.*\.\.",
            r"os\.path\.join\(.*\.\.",
        ],
        "recommendation": "Path traversal detected. Ensure paths are properly sanitized."
    },
    
    # Network Exfiltration
    {
        "id": "SEC006",
        "name": "External Network Calls",
        "severity": Severity.MEDIUM,
        "patterns": [
            r"(fetch|axios|request|http\.get|https\.get|urllib|requests\.)\s*\(",
            r"(WebSocket|new\s+WebSocket|socket\.connect)",
            r"(curl|wget)\s+",
        ],
        "recommendation": "Network calls must be to approved endpoints. Document all external APIs."
    },
    {
        "id": "SEC007",
        "name": "Data Exfiltration URLs",
        "severity": Severity.CRITICAL,
        "patterns": [
            r"(webhook\.site|requestbin|pipedream|ngrok\.io|localtunnel)",
            r"(pastebin\.com|hastebin|ghostbin|dpaste)",
            r"(discord\.com/api/webhooks|slack\.com/api)",
        ],
        "recommendation": "Suspicious exfiltration endpoint detected. This skill will be rejected."
    },
    
    # Code Injection
    {
        "id": "SEC008",
        "name": "Dynamic Code Execution",
        "severity": Severity.CRITICAL,
        "patterns": [
            r"\beval\s*\(",
            r"\bexec\s*\(",
            r"Function\s*\(",
            r"new\s+Function\s*\(",
            r"__import__\s*\(",
            r"importlib\.import_module",
        ],
        "recommendation": "Dynamic code execution is forbidden. Refactor to static imports."
    },
    {
        "id": "SEC009",
        "name": "Shell Command Injection",
        "severity": Severity.HIGH,
        "patterns": [
            r"(subprocess|os\.system|os\.popen|child_process)\s*[\.\(]",
            r"(exec|spawn|fork)\s*\(",
            r"\$\(.*\)",  # Command substitution
            r"`.*`",       # Backtick execution
        ],
        "recommendation": "Shell execution must use parameterized commands, not string interpolation."
    },
    
    # Credential Harvesting
    {
        "id": "SEC010",
        "name": "Keylogger Patterns",
        "severity": Severity.CRITICAL,
        "patterns": [
            r"(keylog|keyboard\.on_press|pynput|keyboard\.add_hotkey)",
            r"(GetAsyncKeyState|GetKeyState|SetWindowsHookEx)",
        ],
        "recommendation": "Keylogger functionality detected. This skill will be rejected."
    },
    {
        "id": "SEC011",
        "name": "Screen Capture",
        "severity": Severity.HIGH,
        "patterns": [
            r"(screenshot|pyautogui\.screenshot|mss\.mss|ImageGrab)",
            r"(screen\.capture|desktopCapturer)",
        ],
        "recommendation": "Screen capture requires explicit user permission. Document use case."
    },
    
    # Persistence Mechanisms
    {
        "id": "SEC012",
        "name": "Startup Persistence",
        "severity": Severity.CRITICAL,
        "patterns": [
            r"(crontab|launchd|systemd|rc\.local|init\.d)",
            r"(HKEY.*Run|CurrentVersion\\Run|Startup)",
            r"(\.bashrc|\.zshrc|\.profile|\.bash_profile)",
        ],
        "recommendation": "Persistence mechanisms are forbidden in skills."
    },
    
    # Obfuscation
    {
        "id": "SEC013",
        "name": "Code Obfuscation",
        "severity": Severity.HIGH,
        "patterns": [
            r"(base64\.b64decode|atob|Buffer\.from.*base64)",
            r"\\x[0-9a-fA-F]{2}",  # Hex-encoded strings
            r"String\.fromCharCode",
            r"chr\(\d+\)",
        ],
        "recommendation": "Obfuscated code detected. Provide readable source or this will be flagged."
    },
]

# Files to always scan
SCANNABLE_EXTENSIONS = {
    '.js', '.ts', '.mjs', '.cjs',  # JavaScript/TypeScript
    '.py', '.pyw',                  # Python
    '.sh', '.bash', '.zsh',         # Shell
    '.rb',                          # Ruby
    '.go',                          # Go
    '.rs',                          # Rust
    '.json', '.yaml', '.yml',       # Config
    '.md',                          # Documentation (for embedded code)
}

# Files to skip
SKIP_PATTERNS = {
    'node_modules', '.git', '__pycache__', '.venv', 'venv',
    'dist', 'build', '.cache', 'coverage'
}


class SecurityScanner:
    """Scans skill code for security vulnerabilities."""
    
    def __init__(self, skill_path: str, verbose: bool = False):
        self.skill_path = Path(skill_path)
        self.verbose = verbose
        self.findings: List[SecurityFinding] = []
        
    def scan(self) -> Tuple[bool, List[SecurityFinding]]:
        """
        Scan the skill directory for security issues.
        
        Returns:
            Tuple of (passed: bool, findings: List[SecurityFinding])
        """
        if not self.skill_path.exists():
            raise FileNotFoundError(f"Skill path not found: {self.skill_path}")
        
        if self.skill_path.is_file():
            self._scan_file(self.skill_path)
        else:
            self._scan_directory(self.skill_path)
        
        # Check for critical findings
        has_critical = any(f.severity == Severity.CRITICAL for f in self.findings)
        has_high = any(f.severity == Severity.HIGH for f in self.findings)
        
        # Auto-fail on critical, warn on high
        passed = not has_critical
        
        return passed, self.findings
    
    def _scan_directory(self, dir_path: Path):
        """Recursively scan a directory."""
        for item in dir_path.iterdir():
            if item.name in SKIP_PATTERNS:
                continue
            if item.is_dir():
                self._scan_directory(item)
            elif item.is_file() and item.suffix in SCANNABLE_EXTENSIONS:
                self._scan_file(item)
    
    def _scan_file(self, file_path: Path):
        """Scan a single file for dangerous patterns."""
        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
        except Exception as e:
            if self.verbose:
                print(f"Warning: Could not read {file_path}: {e}", file=sys.stderr)
            return
        
        lines = content.split('\n')
        
        for pattern_def in DANGEROUS_PATTERNS:
            for pattern in pattern_def["patterns"]:
                for line_num, line in enumerate(lines, 1):
                    if re.search(pattern, line, re.IGNORECASE):
                        finding = SecurityFinding(
                            rule_id=pattern_def["id"],
                            severity=pattern_def["severity"],
                            message=pattern_def["name"],
                            file_path=str(file_path.relative_to(self.skill_path) if file_path.is_relative_to(self.skill_path) else file_path),
                            line_number=line_num,
                            line_content=line.strip()[:100],  # Truncate long lines
                            recommendation=pattern_def["recommendation"]
                        )
                        self.findings.append(finding)
                        if self.verbose:
                            print(f"[{pattern_def['severity'].value.upper()}] {finding.file_path}:{line_num} - {pattern_def['name']}")
    
    def get_report(self) -> Dict:
        """Generate a structured report."""
        summary = {
            "critical": len([f for f in self.findings if f.severity == Severity.CRITICAL]),
            "high": len([f for f in self.findings if f.severity == Severity.HIGH]),
            "medium": len([f for f in self.findings if f.severity == Severity.MEDIUM]),
            "low": len([f for f in self.findings if f.severity == Severity.LOW]),
        }
        
        passed = summary["critical"] == 0
        
        return {
            "skill_path": str(self.skill_path),
            "passed": passed,
            "verdict": "PASS" if passed else "FAIL",
            "summary": summary,
            "findings": [
                {
                    "rule_id": f.rule_id,
                    "severity": f.severity.value,
                    "message": f.message,
                    "file": f.file_path,
                    "line": f.line_number,
                    "content": f.line_content,
                    "recommendation": f.recommendation
                }
                for f in sorted(self.findings, key=lambda x: (
                    {"critical": 0, "high": 1, "medium": 2, "low": 3}[x.severity.value],
                    x.file_path,
                    x.line_number
                ))
            ]
        }


def scan_skill(skill_path: str, verbose: bool = False) -> Dict:
    """
    Convenience function to scan a skill and return a report.
    
    Args:
        skill_path: Path to skill directory or file
        verbose: Print findings as they're discovered
        
    Returns:
        Report dictionary with passed, verdict, summary, and findings
    """
    scanner = SecurityScanner(skill_path, verbose=verbose)
    scanner.scan()
    return scanner.get_report()


def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Security Scanner for Skills")
    parser.add_argument("skill_path", help="Path to skill directory or file")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    
    args = parser.parse_args()
    
    try:
        report = scan_skill(args.skill_path, verbose=args.verbose)
        
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            # Human-readable output
            print(f"\n{'='*60}")
            print(f"SECURITY SCAN: {report['skill_path']}")
            print(f"{'='*60}")
            print(f"Verdict: {report['verdict']}")
            print(f"Summary: {report['summary']['critical']} critical, {report['summary']['high']} high, {report['summary']['medium']} medium, {report['summary']['low']} low")
            print()
            
            if report['findings']:
                print("FINDINGS:")
                print("-" * 60)
                for f in report['findings']:
                    icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵"}[f['severity']]
                    print(f"{icon} [{f['severity'].upper()}] {f['rule_id']}: {f['message']}")
                    print(f"   File: {f['file']}:{f['line']}")
                    print(f"   Code: {f['content']}")
                    print(f"   Fix:  {f['recommendation']}")
                    print()
            else:
                print("✅ No security issues found!")
            
            print(f"{'='*60}")
        
        sys.exit(0 if report['passed'] else 1)
        
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
