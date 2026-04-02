#!/usr/bin/env python3
"""
Skill Validator - Main CLI Tool
Orchestrates security scan, sandbox tests, token profiling, and Logician approval.

Usage:
    ./skill_validator.py validate /path/to/skill
    ./skill_validator.py approve skill-name
    ./skill_validator.py list
    ./skill_validator.py check skill-name

Phases:
1. Security Scan (auto-reject dangerous code)
2. Sandbox Test (verify claimed functionality)
3. Token Profiling (measure actual usage)
4. Logician Approval (block unapproved skills)
"""

import os
import sys
import json
import argparse
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, Tuple

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent / "lib"))

from security_scanner import scan_skill
from sandbox_runner import run_skill_tests, SkillTestParser
from token_profiler import TokenProfiler

# =============================================================================
# CONFIGURATION
# =============================================================================

LOGICIAN_RULES_PATH = Path.home() / "clawd/projects/logician/poc/production_rules.mg"
APPROVED_SKILLS_SECTION = "# APPROVED SKILLS"

# =============================================================================
# LOGICIAN INTEGRATION
# =============================================================================

def get_approved_skills() -> list:
    """Read approved skills from Logician production_rules.mg."""
    if not LOGICIAN_RULES_PATH.exists():
        return []
    
    content = LOGICIAN_RULES_PATH.read_text()
    
    # Find approved_skill facts - only match concrete facts (lowercase names, not variables)
    # Variables in Mangle start with uppercase (e.g., SkillName)
    import re
    skills = re.findall(r'approved_skill\(/([a-z][a-z0-9_-]*)\)\.', content)
    
    return list(set(skills))  # Deduplicate


def add_approved_skill(skill_name: str, metadata: Dict) -> bool:
    """Add a skill to the approved list in Logician rules."""
    if not LOGICIAN_RULES_PATH.exists():
        print(f"Error: Logician rules not found at {LOGICIAN_RULES_PATH}", file=sys.stderr)
        return False
    
    content = LOGICIAN_RULES_PATH.read_text()
    
    # Check if already approved
    if f'approved_skill(/{skill_name})' in content:
        print(f"Skill '{skill_name}' is already approved.")
        return True
    
    # Add the approval fact
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
    new_facts = f"""
# Skill: {skill_name} (approved {timestamp})
approved_skill(/{skill_name}).
skill_version(/{skill_name}, "{metadata.get('version', '0.0.0')}").
skill_author(/{skill_name}, "{metadata.get('author', 'unknown')}").
"""
    
    # Find or create the APPROVED SKILLS section
    if APPROVED_SKILLS_SECTION in content:
        # Insert after the section header
        idx = content.find(APPROVED_SKILLS_SECTION)
        end_of_line = content.find('\n', idx)
        content = content[:end_of_line+1] + new_facts + content[end_of_line+1:]
    else:
        # Append new section
        content += f"\n{APPROVED_SKILLS_SECTION}\n{new_facts}"
    
    LOGICIAN_RULES_PATH.write_text(content)
    print(f"✅ Added '{skill_name}' to approved skills in {LOGICIAN_RULES_PATH}")
    return True


def remove_approved_skill(skill_name: str) -> bool:
    """Remove a skill from the approved list."""
    if not LOGICIAN_RULES_PATH.exists():
        return False
    
    content = LOGICIAN_RULES_PATH.read_text()
    
    # Remove all facts about this skill
    import re
    patterns = [
        rf'# Skill: {skill_name}[^\n]*\n',
        rf'approved_skill\(/{skill_name}\)\.\n?',
        rf'skill_version\(/{skill_name}[^)]*\)\.\n?',
        rf'skill_author\(/{skill_name}[^)]*\)\.\n?',
    ]
    
    for pattern in patterns:
        content = re.sub(pattern, '', content)
    
    LOGICIAN_RULES_PATH.write_text(content)
    print(f"❌ Removed '{skill_name}' from approved skills")
    return True


def is_skill_approved(skill_name: str) -> bool:
    """Check if a skill is approved in Logician."""
    approved = get_approved_skills()
    return skill_name in approved


# =============================================================================
# VALIDATION PIPELINE
# =============================================================================

def validate_skill(skill_path: str, auto_approve: bool = False, verbose: bool = False) -> Tuple[bool, Dict]:
    """
    Run full validation pipeline on a skill.
    
    Phases:
    1. Security Scan
    2. Sandbox Tests
    3. Token Profiling
    4. (Optional) Auto-approve
    
    Args:
        skill_path: Path to skill directory
        auto_approve: If True, auto-approve if all phases pass
        verbose: Verbose output
        
    Returns:
        Tuple of (passed: bool, full_report: Dict)
    """
    path = Path(skill_path).resolve()
    skill_name = path.name
    
    report = {
        "skill_name": skill_name,
        "skill_path": str(path),
        "timestamp": datetime.now().isoformat(),
        "phases": {},
        "verdict": None,
        "approved": False
    }
    
    print(f"\n{'='*70}")
    print(f"🔍 SKILL VALIDATION: {skill_name}")
    print(f"   Path: {path}")
    print(f"{'='*70}\n")
    
    # -------------------------------------------------------------------------
    # Phase 1: Security Scan
    # -------------------------------------------------------------------------
    print("📋 Phase 1: Security Scan")
    print("-" * 40)
    
    security_report = scan_skill(str(path), verbose=verbose)
    report["phases"]["security"] = security_report
    
    if security_report["verdict"] == "FAIL":
        print(f"   🔴 FAILED: {security_report['summary']['critical']} critical issues found")
        for f in security_report['findings'][:3]:  # Show first 3
            print(f"      • [{f['severity'].upper()}] {f['message']} ({f['file']}:{f['line']})")
        
        report["verdict"] = "REJECTED"
        report["reject_reason"] = "Security scan failed"
        
        print(f"\n❌ VALIDATION FAILED at Phase 1 (Security)")
        print(f"   This skill has been AUTO-REJECTED due to security concerns.")
        return False, report
    else:
        print(f"   ✅ PASSED ({security_report['summary']['high']} warnings)")
    
    print()
    
    # -------------------------------------------------------------------------
    # Phase 2: Sandbox Tests
    # -------------------------------------------------------------------------
    print("🧪 Phase 2: Sandbox Tests")
    print("-" * 40)
    
    sandbox_report = run_skill_tests(str(path))
    report["phases"]["sandbox"] = sandbox_report
    
    if sandbox_report.get("verdict") == "FAIL":
        passed = sandbox_report.get('passed', 0)
        total = sandbox_report.get('total_tests', 0)
        print(f"   🔴 FAILED: {passed}/{total} tests passed")
        for r in sandbox_report.get('results', []):
            icon = "✅" if r['passed'] else "❌"
            print(f"      {icon} {r['name']}")
        
        report["verdict"] = "REJECTED"
        report["reject_reason"] = "Sandbox tests failed"
        
        print(f"\n❌ VALIDATION FAILED at Phase 2 (Tests)")
        return False, report
    elif sandbox_report.get("verdict") == "SKIP":
        print(f"   ⚠️  SKIPPED: {sandbox_report.get('reason', 'No tests defined')}")
    else:
        passed = sandbox_report.get('passed', 0)
        total = sandbox_report.get('total_tests', 0)
        print(f"   ✅ PASSED: {passed}/{total} tests")
    
    print()
    
    # -------------------------------------------------------------------------
    # Phase 3: Token Profiling
    # -------------------------------------------------------------------------
    print("💰 Phase 3: Token Profiling")
    print("-" * 40)
    
    profiler = TokenProfiler(path)
    
    # Get claimed cost from metadata
    claimed_cost = None
    if 'metadata' in sandbox_report:
        claimed_str = sandbox_report['metadata'].get('claimed_cost')
        if claimed_str:
            try:
                claimed_cost = int(claimed_str)
            except (ValueError, TypeError):
                pass
    
    # Profile from sandbox results
    if 'results' in sandbox_report:
        profiler.profile_from_sandbox_results(sandbox_report)
    
    token_report = profiler.get_report(claimed_cost)
    report["phases"]["tokens"] = token_report
    
    if token_report["flagged"]:
        print(f"   ⚠️  WARNING: {token_report['flag_reason']}")
        print(f"      Claimed: {token_report['claimed_tokens_per_call']} tokens/call")
        print(f"      Actual:  {token_report['actual_tokens_per_call']} tokens/call")
    else:
        print(f"   ✅ PASSED: ~{token_report['actual_tokens_per_call']} tokens/call")
        if token_report['claimed_tokens_per_call']:
            print(f"      (Claimed: {token_report['claimed_tokens_per_call']}, variance: {token_report['variance_percent']}%)")
    
    print()
    
    # -------------------------------------------------------------------------
    # Phase 4: Approval
    # -------------------------------------------------------------------------
    print("🔐 Phase 4: Logician Approval")
    print("-" * 40)
    
    if is_skill_approved(skill_name):
        print(f"   ✅ Already approved in Logician")
        report["approved"] = True
    elif auto_approve:
        metadata = sandbox_report.get('metadata', {})
        if add_approved_skill(skill_name, metadata):
            print(f"   ✅ Auto-approved and added to Logician")
            report["approved"] = True
        else:
            print(f"   ⚠️  Could not auto-approve (Logician rules not found)")
    else:
        print(f"   ⏳ Not yet approved")
        print(f"      Run: skill_validator.py approve {skill_name}")
    
    print()
    
    # -------------------------------------------------------------------------
    # Final Verdict
    # -------------------------------------------------------------------------
    report["verdict"] = "PASS"
    
    print(f"{'='*70}")
    print(f"✅ VALIDATION PASSED: {skill_name}")
    print(f"{'='*70}")
    
    if not report["approved"]:
        print(f"\n⚠️  Note: Skill passed validation but is NOT yet approved.")
        print(f"   To approve: ./skill_validator.py approve {skill_name}")
    
    return True, report


# =============================================================================
# CLI COMMANDS
# =============================================================================

def cmd_validate(args):
    """Validate a skill."""
    passed, report = validate_skill(
        args.skill_path,
        auto_approve=args.approve,
        verbose=args.verbose
    )
    
    if args.json:
        print(json.dumps(report, indent=2))
    
    sys.exit(0 if passed else 1)


def cmd_approve(args):
    """Manually approve a skill."""
    skill_name = args.skill_name
    
    if is_skill_approved(skill_name):
        print(f"✅ Skill '{skill_name}' is already approved.")
        return
    
    # Add with minimal metadata
    metadata = {
        "version": "1.0.0",
        "author": "manual-approval"
    }
    
    if add_approved_skill(skill_name, metadata):
        print(f"✅ Skill '{skill_name}' approved.")
    else:
        print(f"❌ Failed to approve skill.")
        sys.exit(1)


def cmd_revoke(args):
    """Revoke approval for a skill."""
    if remove_approved_skill(args.skill_name):
        print(f"✅ Approval revoked for '{args.skill_name}'")
    else:
        print(f"❌ Skill '{args.skill_name}' was not approved")
        sys.exit(1)


def cmd_list(args):
    """List approved skills."""
    skills = get_approved_skills()
    
    if args.json:
        print(json.dumps({"approved_skills": skills}, indent=2))
    else:
        print(f"\n📋 APPROVED SKILLS ({len(skills)} total)")
        print("-" * 40)
        if skills:
            for s in sorted(skills):
                print(f"  ✅ {s}")
        else:
            print("  (none)")
        print()


def cmd_check(args):
    """Check if a skill is approved."""
    approved = is_skill_approved(args.skill_name)
    
    if args.json:
        print(json.dumps({
            "skill": args.skill_name,
            "approved": approved
        }))
    else:
        if approved:
            print(f"✅ Skill '{args.skill_name}' is APPROVED")
        else:
            print(f"❌ Skill '{args.skill_name}' is NOT APPROVED")
            print(f"   This skill cannot be used until approved.")
            sys.exit(1)


def cmd_scan(args):
    """Run security scan only."""
    report = scan_skill(args.skill_path, verbose=args.verbose)
    
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"\nSecurity Scan: {report['verdict']}")
        print(f"Critical: {report['summary']['critical']}, High: {report['summary']['high']}")
    
    sys.exit(0 if report['passed'] else 1)


def cmd_test(args):
    """Run sandbox tests only."""
    report = run_skill_tests(args.skill_path)
    
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"\nSandbox Tests: {report.get('verdict', 'UNKNOWN')}")
    
    sys.exit(0 if report.get('verdict') in ['PASS', 'SKIP'] else 1)


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Skill Validator - Security, Testing, and Approval Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s validate /path/to/skill          Full validation pipeline
  %(prog)s validate /path/to/skill --approve  Validate and auto-approve if passing
  %(prog)s scan /path/to/skill              Security scan only
  %(prog)s test /path/to/skill              Sandbox tests only
  %(prog)s approve my-skill                 Manually approve a skill
  %(prog)s revoke my-skill                  Revoke approval
  %(prog)s list                             List approved skills
  %(prog)s check my-skill                   Check if skill is approved
"""
    )
    
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # validate
    p_validate = subparsers.add_parser("validate", help="Run full validation pipeline")
    p_validate.add_argument("skill_path", help="Path to skill directory")
    p_validate.add_argument("--approve", action="store_true", help="Auto-approve if validation passes")
    p_validate.set_defaults(func=cmd_validate)
    
    # approve
    p_approve = subparsers.add_parser("approve", help="Manually approve a skill")
    p_approve.add_argument("skill_name", help="Name of skill to approve")
    p_approve.set_defaults(func=cmd_approve)
    
    # revoke
    p_revoke = subparsers.add_parser("revoke", help="Revoke approval for a skill")
    p_revoke.add_argument("skill_name", help="Name of skill to revoke")
    p_revoke.set_defaults(func=cmd_revoke)
    
    # list
    p_list = subparsers.add_parser("list", help="List approved skills")
    p_list.set_defaults(func=cmd_list)
    
    # check
    p_check = subparsers.add_parser("check", help="Check if a skill is approved")
    p_check.add_argument("skill_name", help="Name of skill to check")
    p_check.set_defaults(func=cmd_check)
    
    # scan
    p_scan = subparsers.add_parser("scan", help="Run security scan only")
    p_scan.add_argument("skill_path", help="Path to skill directory")
    p_scan.set_defaults(func=cmd_scan)
    
    # test
    p_test = subparsers.add_parser("test", help="Run sandbox tests only")
    p_test.add_argument("skill_path", help="Path to skill directory")
    p_test.set_defaults(func=cmd_test)
    
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
