#!/usr/bin/env python3
"""
Diagnosis Gate — Enforces evidence before diagnostic claims on issues.

Part of ResonantOS Shield. Prevents closing GitHub issues or posting
diagnostic comments without deterministic evidence.

Failure mode this prevents:
  "Root cause is X" without actually testing X.
  Example: Issue #6 was labeled "on-chain program issue, needs redeployment"
  without testing the program. The program was fine. The real bug was a
  1-line commitment parameter. (2026-03-01)

Rules:
  1. Every `gh issue close` comment must contain at least one evidence marker
  2. Evidence markers: verification lines, code blocks with output, test results
  3. Diagnostic claims without evidence are blocked
  4. "Needs investigation" / "cannot reproduce" are allowed (honest uncertainty)

Evidence markers (at least ONE required):
  - Lines starting with: checkmark, Verified:, Evidence:, Test:, Output:, Result:
  - Code blocks containing test output
  - Transaction signatures, HTTP status codes, command output
  - "confirmed", "reproduced", "tested" with surrounding context

Diagnostic claim markers (trigger enforcement):
  - "root cause", "the issue is", "the bug is", "the problem is"
  - "caused by", "due to", "because of", "this is a"
  - "needs redeployment", "needs rebuild", "program issue"

Usage:
    python3 diagnosis_gate.py check "<comment_text>"
    python3 diagnosis_gate.py test
    
Exit codes:
    0 = passed (has evidence or no diagnostic claim)
    1 = blocked (diagnostic claim without evidence)
    2 = error/usage
"""

import re
import sys

# --- Patterns ---

EVIDENCE_MARKERS = [
    r'^\s*✅',                          # Checkmark lines
    r'(?i)^.*\bverified?\b.*:',         # "Verified:" or "Verify:"
    r'(?i)^.*\bevidence\b.*:',          # "Evidence:"
    r'(?i)^.*\btest(?:ed|ing)?\b.*:',   # "Test:", "Tested:", "Testing:"
    r'(?i)^.*\boutput\b.*:',            # "Output:"
    r'(?i)^.*\bresult\b.*:',            # "Result:"
    r'```[\s\S]*?```',                  # Code blocks (multi-line)
    r'`[^`]{10,}`',                     # Inline code with substance (>10 chars)
    r'(?i)\breproduced\b',             # "reproduced"
    r'(?i)\bconfirmed\b.*\b(?:by|via|with|through)\b',  # "confirmed by/via/with"
    r'HTTP\s*\d{3}',                    # HTTP status codes
    r'[0-9a-fA-F]{7,}',                # Hashes, signatures, commit SHAs
    r'(?i)\bcurl\b.*\d{3}',            # curl + status
    r'(?i)returns?\s+\d+\s+\w+',       # "returns 13 agents"
    r'(?i)(?:import|syntax)\s+(?:ok|pass|clean)', # "import OK", "syntax pass"
]

DIAGNOSTIC_CLAIMS = [
    r'(?i)\broot\s+cause\b',
    r'(?i)\bthe\s+(?:issue|bug|problem)\s+(?:is|was)\b',
    r'(?i)\bcaused?\s+by\b',
    r'(?i)\bdue\s+to\b',
    r'(?i)\bbecause\s+of\b',
    r'(?i)\bthis\s+is\s+(?:a|an)\s+[\w-]+\s+(?:issue|bug|problem|error)\b',
    r'(?i)\bneeds?\s+(?:re)?deploy',
    r'(?i)\bneeds?\s+rebuild',
    r'(?i)\bprogram\s+(?:issue|bug|error)\b',
    r'(?i)\bthe\s+fix\s+is\b',
    r'(?i)\bfixed\s+(?:in|by|via)\b',
    r'(?i)\brequires?\s+(?:modif|fix|chang|rebuild|redeploy)',  # "requires modifying/redeploying"
    r'(?i)\bneeds?\s+to\s+(?:be\s+)?(?:fix|modif|chang|rebuild|redeploy|updat)',  # "needs to be fixed"
]

UNCERTAINTY_MARKERS = [
    r'(?i)\bneeds?\s+investigation\b',
    r'(?i)\bcannot\s+reproduce\b',
    r'(?i)\bunable\s+to\s+reproduce\b',
    r'(?i)\bpossible\s+cause',
    r'(?i)\bmight\s+be\b',
    r'(?i)\bcould\s+be\b',
    r'(?i)\bby[\s-]+design\b',
    r'(?i)\bnot\s+a\s+bug\b',
    r'(?i)\bworking\s+as\s+(?:designed|intended|expected)\b',
]


def has_evidence(text):
    found = []
    for pattern in EVIDENCE_MARKERS:
        matches = re.findall(pattern, text, re.MULTILINE)
        if matches:
            found.append(pattern)
    return len(found) >= 1, found


def has_diagnostic_claim(text):
    found = []
    for pattern in DIAGNOSTIC_CLAIMS:
        matches = re.findall(pattern, text)
        if matches:
            found.append(matches[0])
    return len(found) > 0, found


def has_uncertainty(text):
    for pattern in UNCERTAINTY_MARKERS:
        if re.search(pattern, text):
            return True
    return False


def check_comment(text):
    claims_found, claims = has_diagnostic_claim(text)
    evidence_found, evidence = has_evidence(text)
    is_uncertain = has_uncertainty(text)
    
    if not claims_found:
        return {
            "passed": True,
            "level": "ok",
            "reason": "No diagnostic claim — no evidence required.",
            "diagnostic_claims": [],
            "evidence_found": evidence,
        }
    
    if is_uncertain:
        return {
            "passed": True,
            "level": "ok",
            "reason": "Diagnostic uses uncertainty language — honest assessment.",
            "diagnostic_claims": claims,
            "evidence_found": evidence,
        }
    
    if evidence_found:
        return {
            "passed": True,
            "level": "ok",
            "reason": f"Diagnostic backed by {len(evidence)} evidence marker(s).",
            "diagnostic_claims": claims,
            "evidence_found": evidence,
        }
    
    return {
        "passed": False,
        "level": "blocked",
        "reason": (
            "BLOCKED: Diagnostic claim without evidence.\n"
            f"  Claims: {claims}\n"
            "  No evidence markers found.\n"
            "\n"
            "  Required (at least one):\n"
            "    - Verification line (checkmark + description)\n"
            "    - Code block with test output\n"
            "    - 'Verified:', 'Evidence:', 'Test:' prefix\n"
            "    - Specific data (hashes, HTTP codes, counts)\n"
            "\n"
            "  Or use uncertainty language if unverified:\n"
            "    - 'Possible cause:', 'Might be', 'Needs investigation'"
        ),
        "diagnostic_claims": claims,
        "evidence_found": [],
    }


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 diagnosis_gate.py check '<comment>'")
        print("       python3 diagnosis_gate.py test")
        sys.exit(2)
    
    action = sys.argv[1]
    
    if action == "check":
        if len(sys.argv) < 3:
            # Read from stdin
            text = sys.stdin.read()
        else:
            text = sys.argv[2]
        result = check_comment(text)
        if result["passed"]:
            print(f"PASSED: {result['reason']}")
            sys.exit(0)
        else:
            print(f"BLOCKED: {result['reason']}")
            sys.exit(1)
    
    elif action == "test":
        tests = [
            ("No diagnostic claim", "Updated the readme with new instructions.", True),
            ("Claim + checkmark", "Root cause: the API returns finalized.\n✅ Tested on DevNet, PDA exists.", True),
            ("Claim + code block", "The bug is in the query.\n```\ncurl ... returned 200\n```", True),
            ("Claim + uncertainty", "This might be caused by a race condition. Needs investigation.", True),
            ("Claim WITHOUT evidence", "Root cause is the Anchor program. Needs redeployment.", False),
            ("Claim WITHOUT evidence 2", "The issue is a PDA space allocation bug.", False),
            ("By-design closure", "This is by-design behavior, not a bug.", True),
            ("Claim + hash", "Fixed in dba85f4. The bug was caused by finalized commitment.", True),
            ("Claim + test output", "The problem is commitment mismatch. Test: returns 93 bytes.", True),
            ("Claim + HTTP code", "The fix is working. API returns HTTP 200 on all endpoints.", True),
        ]
        
        passed = 0
        failed = 0
        for desc, text, expected in tests:
            result = check_comment(text)
            ok = result["passed"] == expected
            status = "PASS" if ok else "FAIL"
            if ok:
                passed += 1
            else:
                failed += 1
            print(f"{'✅' if ok else '❌'} {desc}: {'PASS' if result['passed'] else 'BLOCK'} (expected {'PASS' if expected else 'BLOCK'})")
            if not ok:
                print(f"   Reason: {result['reason']}")
                print(f"   Claims: {result['diagnostic_claims']}")
                print(f"   Evidence: {result['evidence_found']}")
        
        print(f"\n{passed}/{passed+failed} tests passed")
        sys.exit(0 if failed == 0 else 1)
    
    else:
        print(f"Unknown action: {action}")
        sys.exit(2)


if __name__ == "__main__":
    main()
