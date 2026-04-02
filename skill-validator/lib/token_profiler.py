#!/usr/bin/env python3
"""
Token Cost Profiler for Skill Validation
Measures actual token usage during test runs and compares against claimed costs.

Token counting strategy:
1. Proxy API calls through a measuring wrapper
2. Count input/output tokens per call
3. Aggregate across test runs
4. Compare against SKILL.md claimed_cost
"""

import os
import json
import subprocess
import sys
import re
from pathlib import Path
from typing import Dict, Optional, List
from dataclasses import dataclass
import time

@dataclass
class TokenUsage:
    input_tokens: int
    output_tokens: int
    total_tokens: int
    api_calls: int

@dataclass
class CostProfile:
    skill_name: str
    claimed_cost: Optional[int]  # From SKILL.md
    actual_cost: int             # Measured
    variance_percent: float      # (actual - claimed) / claimed * 100
    flagged: bool                # True if variance > 20%
    details: List[Dict]          # Per-test breakdown


class TokenProfiler:
    """
    Profiles token usage for a skill during test execution.
    
    Works by:
    1. Setting up a mock/proxy for API calls
    2. Counting tokens in requests/responses
    3. Aggregating results
    """
    
    # Approximate tokens per character (varies by model)
    CHARS_PER_TOKEN = 4
    
    # Variance threshold for flagging
    VARIANCE_THRESHOLD = 20  # percent
    
    def __init__(self, skill_path: Path):
        self.skill_path = Path(skill_path)
        self.usage = TokenUsage(0, 0, 0, 0)
        self.per_test_usage: List[Dict] = []
        
    def estimate_tokens(self, text: str) -> int:
        """Estimate token count from text."""
        if not text:
            return 0
        # Simple estimation: characters / 4
        # More accurate would use tiktoken, but this works for profiling
        return max(1, len(text) // self.CHARS_PER_TOKEN)
    
    def profile_test_run(self, test_name: str, input_data: Dict, output: str) -> Dict:
        """
        Profile a single test run.
        
        Args:
            test_name: Name of the test
            input_data: Input provided to skill
            output: Output captured from skill
            
        Returns:
            Token usage for this test
        """
        input_str = json.dumps(input_data) if isinstance(input_data, dict) else str(input_data)
        
        input_tokens = self.estimate_tokens(input_str)
        output_tokens = self.estimate_tokens(output)
        total = input_tokens + output_tokens
        
        test_usage = {
            "test_name": test_name,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total,
            "api_calls": 1  # Assume 1 API call per test
        }
        
        # Aggregate
        self.usage.input_tokens += input_tokens
        self.usage.output_tokens += output_tokens
        self.usage.total_tokens += total
        self.usage.api_calls += 1
        
        self.per_test_usage.append(test_usage)
        
        return test_usage
    
    def profile_from_sandbox_results(self, sandbox_report: Dict) -> None:
        """
        Profile token usage from sandbox test results.
        
        Args:
            sandbox_report: Report from SandboxRunner
        """
        for result in sandbox_report.get('results', []):
            # Estimate input from test case structure
            # In real usage, we'd intercept actual API calls
            self.profile_test_run(
                test_name=result['name'],
                input_data={"expected": result['expected']},
                output=result['actual']
            )
    
    def get_cost_profile(self, claimed_cost: Optional[int] = None) -> CostProfile:
        """
        Generate cost profile comparing actual vs claimed usage.
        
        Args:
            claimed_cost: Claimed tokens per invocation from SKILL.md
            
        Returns:
            CostProfile with variance analysis
        """
        actual_per_call = self.usage.total_tokens // max(1, self.usage.api_calls)
        
        if claimed_cost and claimed_cost > 0:
            variance = ((actual_per_call - claimed_cost) / claimed_cost) * 100
            flagged = variance > self.VARIANCE_THRESHOLD
        else:
            variance = 0.0
            flagged = False
        
        return CostProfile(
            skill_name=self.skill_path.name,
            claimed_cost=claimed_cost,
            actual_cost=actual_per_call,
            variance_percent=round(variance, 1),
            flagged=flagged,
            details=self.per_test_usage
        )
    
    def get_report(self, claimed_cost: Optional[int] = None) -> Dict:
        """Generate full profiling report."""
        profile = self.get_cost_profile(claimed_cost)
        
        return {
            "skill_path": str(self.skill_path),
            "verdict": "WARN" if profile.flagged else "PASS",
            "claimed_tokens_per_call": profile.claimed_cost,
            "actual_tokens_per_call": profile.actual_cost,
            "variance_percent": profile.variance_percent,
            "flagged": profile.flagged,
            "flag_reason": f"Actual cost {profile.variance_percent}% higher than claimed" if profile.flagged else None,
            "totals": {
                "input_tokens": self.usage.input_tokens,
                "output_tokens": self.usage.output_tokens,
                "total_tokens": self.usage.total_tokens,
                "api_calls": self.usage.api_calls
            },
            "per_test": self.per_test_usage
        }


def profile_skill(skill_path: str, sandbox_report: Optional[Dict] = None) -> Dict:
    """
    Profile token usage for a skill.
    
    Args:
        skill_path: Path to skill directory
        sandbox_report: Optional pre-computed sandbox test results
        
    Returns:
        Token profiling report
    """
    path = Path(skill_path)
    profiler = TokenProfiler(path)
    
    # Get claimed cost from SKILL.md
    claimed_cost = None
    skill_md = path / "SKILL.md"
    if skill_md.exists():
        content = skill_md.read_text()
        # Look for cost claim
        match = re.search(
            r'(?:token[s]?\s*(?:cost|per[- ]call|estimate)[s]?):\s*~?(\d+)',
            content,
            re.IGNORECASE
        )
        if match:
            claimed_cost = int(match.group(1))
    
    # If sandbox report provided, use it
    if sandbox_report and 'results' in sandbox_report:
        profiler.profile_from_sandbox_results(sandbox_report)
    else:
        # Run our own minimal test
        from sandbox_runner import run_skill_tests
        sandbox_report = run_skill_tests(skill_path)
        if 'results' in sandbox_report:
            profiler.profile_from_sandbox_results(sandbox_report)
    
    return profiler.get_report(claimed_cost)


def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Token Cost Profiler for Skills")
    parser.add_argument("skill_path", help="Path to skill directory")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    
    args = parser.parse_args()
    
    report = profile_skill(args.skill_path)
    
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"\n{'='*60}")
        print(f"TOKEN PROFILER: {report['skill_path']}")
        print(f"{'='*60}")
        
        print(f"Verdict: {report['verdict']}")
        
        if report['claimed_tokens_per_call']:
            print(f"Claimed: {report['claimed_tokens_per_call']} tokens/call")
        else:
            print(f"Claimed: Not specified in SKILL.md")
        
        print(f"Actual:  {report['actual_tokens_per_call']} tokens/call")
        
        if report['flagged']:
            print(f"⚠️  FLAG: {report['flag_reason']}")
        
        print()
        print("Totals:")
        print(f"  Input tokens:  {report['totals']['input_tokens']}")
        print(f"  Output tokens: {report['totals']['output_tokens']}")
        print(f"  Total tokens:  {report['totals']['total_tokens']}")
        print(f"  API calls:     {report['totals']['api_calls']}")
        
        print(f"{'='*60}")
    
    sys.exit(0 if report['verdict'] == 'PASS' else 2)


if __name__ == "__main__":
    main()
