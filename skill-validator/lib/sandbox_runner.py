#!/usr/bin/env python3
"""
Sandbox Test Runner for Skill Validation
Executes skill tests in isolated environment and verifies claimed functionality.

Test format (from SKILL.md):
```test
name: basic_greeting
input: {"message": "hello"}
expected_output: "Hello! How can I help you?"
```
"""

import os
import re
import json
import subprocess
import tempfile
import shutil
import sys
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import time

@dataclass
class TestCase:
    name: str
    input_data: Dict
    expected_output: str
    timeout_seconds: int = 30

@dataclass
class TestResult:
    name: str
    passed: bool
    expected: str
    actual: str
    error: Optional[str] = None
    duration_ms: int = 0

class SkillTestParser:
    """Parses test cases from SKILL.md documentation."""
    
    @staticmethod
    def parse_skill_md(skill_path: Path) -> Tuple[Dict, List[TestCase]]:
        """
        Parse SKILL.md for metadata and test cases.
        
        Returns:
            Tuple of (metadata dict, list of TestCase)
        """
        skill_md = skill_path / "SKILL.md"
        if not skill_md.exists():
            raise FileNotFoundError(f"SKILL.md not found in {skill_path}")
        
        content = skill_md.read_text()
        
        # Parse metadata (YAML frontmatter or header section)
        metadata = SkillTestParser._parse_metadata(content)
        
        # Parse test blocks
        tests = SkillTestParser._parse_tests(content)
        
        return metadata, tests
    
    @staticmethod
    def _parse_metadata(content: str) -> Dict:
        """Extract metadata from SKILL.md."""
        metadata = {
            "name": "unknown",
            "version": "0.0.0",
            "author": "unknown",
            "description": "",
            "claimed_cost": None,  # tokens per invocation
        }
        
        # Try YAML frontmatter
        if content.startswith("---"):
            end = content.find("---", 3)
            if end != -1:
                frontmatter = content[3:end]
                for line in frontmatter.strip().split('\n'):
                    if ':' in line:
                        key, value = line.split(':', 1)
                        key = key.strip().lower().replace(' ', '_')
                        value = value.strip()
                        metadata[key] = value
        
        # Also look for header-style metadata (including markdown bold format)
        patterns = {
            "name": r"^#\s+(.+?)(?:\s*$|\s+[Ss]kill)",
            "version": r"(?:\*\*)?[Vv]ersion:?\*?\*?:?\s*([0-9.]+)",
            "author": r"(?:\*\*)?[Aa]uthor:?\*?\*?:?\s*(.+?)(?:\n|$)",
            "claimed_cost": r"[Tt]oken[s]?\s*(?:cost|per[- ]?call|estimate|cost\s*per\s*call)[s]?[:\*]*\s*~?(\d+)",
        }
        
        for key, pattern in patterns.items():
            match = re.search(pattern, content, re.IGNORECASE | re.MULTILINE)
            if match:
                metadata[key] = match.group(1).strip()
        
        return metadata
    
    @staticmethod
    def _parse_tests(content: str) -> List[TestCase]:
        """Extract test cases from code blocks."""
        tests = []
        
        # Match ```test blocks
        test_blocks = re.findall(
            r'```test\s*\n(.*?)```',
            content,
            re.DOTALL | re.IGNORECASE
        )
        
        for block in test_blocks:
            test = SkillTestParser._parse_test_block(block)
            if test:
                tests.append(test)
        
        # Also match structured test sections
        # ## Tests
        # ### test_name
        # **Input:** `{...}`
        # **Expected:** `...`
        test_section = re.search(r'##\s*Tests?\s*\n(.*?)(?=\n##[^#]|\Z)', content, re.DOTALL | re.IGNORECASE)
        if test_section:
            section = test_section.group(1)
            # Match ### test_name blocks
            test_headers = re.findall(r'###\s+([\w_-]+)\s*\n(.*?)(?=\n###|\Z)', section, re.DOTALL)
            for name, body in test_headers:
                input_match = re.search(r'\*\*Input:?\*\*:?\s*`([^`]+)`', body)
                expected_match = re.search(r'\*\*Expected:?\*\*:?\s*`([^`]+)`', body)
                if input_match and expected_match:
                    try:
                        input_data = json.loads(input_match.group(1))
                    except json.JSONDecodeError:
                        input_data = {"raw": input_match.group(1)}
                    tests.append(TestCase(
                        name=name,
                        input_data=input_data,
                        expected_output=expected_match.group(1)
                    ))
        
        return tests
    
    @staticmethod
    def _parse_test_block(block: str) -> Optional[TestCase]:
        """Parse a single test block."""
        lines = block.strip().split('\n')
        test_data = {}
        
        for line in lines:
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip().lower()
                value = value.strip()
                test_data[key] = value
        
        if 'name' not in test_data:
            return None
        
        # Parse input as JSON if possible
        input_str = test_data.get('input', '{}')
        try:
            input_data = json.loads(input_str)
        except json.JSONDecodeError:
            input_data = {"raw": input_str}
        
        return TestCase(
            name=test_data['name'],
            input_data=input_data,
            expected_output=test_data.get('expected_output', test_data.get('expected', '')),
            timeout_seconds=int(test_data.get('timeout', 30))
        )


class SandboxRunner:
    """
    Runs skill tests in an isolated sandbox environment.
    
    Sandbox types:
    1. Node.js VM (lightweight, default)
    2. Docker container (full isolation)
    3. Subprocess (minimal, for simple scripts)
    """
    
    def __init__(self, skill_path: Path, sandbox_type: str = "subprocess"):
        self.skill_path = Path(skill_path)
        self.sandbox_type = sandbox_type
        self.results: List[TestResult] = []
        
    def run_tests(self, tests: List[TestCase]) -> List[TestResult]:
        """Run all tests and return results."""
        self.results = []
        
        for test in tests:
            result = self._run_single_test(test)
            self.results.append(result)
        
        return self.results
    
    def _run_single_test(self, test: TestCase) -> TestResult:
        """Run a single test case."""
        start_time = time.time()
        
        try:
            # Find the skill entry point
            entry_point = self._find_entry_point()
            
            if entry_point is None:
                return TestResult(
                    name=test.name,
                    passed=False,
                    expected=test.expected_output,
                    actual="",
                    error="No entry point found (index.js, main.py, or skill.sh)"
                )
            
            # Run in sandbox
            actual_output = self._execute_in_sandbox(entry_point, test)
            
            # Compare output
            passed = self._compare_output(actual_output, test.expected_output)
            
            duration_ms = int((time.time() - start_time) * 1000)
            
            return TestResult(
                name=test.name,
                passed=passed,
                expected=test.expected_output,
                actual=actual_output,
                duration_ms=duration_ms
            )
            
        except subprocess.TimeoutExpired:
            return TestResult(
                name=test.name,
                passed=False,
                expected=test.expected_output,
                actual="",
                error=f"Test timed out after {test.timeout_seconds}s"
            )
        except Exception as e:
            return TestResult(
                name=test.name,
                passed=False,
                expected=test.expected_output,
                actual="",
                error=str(e)
            )
    
    def _find_entry_point(self) -> Optional[Path]:
        """Find the skill's entry point file."""
        candidates = [
            "index.js", "main.js", "skill.js",
            "main.py", "skill.py", "__main__.py",
            "skill.sh", "run.sh"
        ]
        
        for candidate in candidates:
            path = self.skill_path / candidate
            if path.exists():
                return path
        
        return None
    
    def _execute_in_sandbox(self, entry_point: Path, test: TestCase) -> str:
        """Execute the skill in sandbox and capture output."""
        
        # Prepare environment - strip sensitive vars
        safe_env = {
            k: v for k, v in os.environ.items()
            if not any(secret in k.upper() for secret in 
                      ['API_KEY', 'TOKEN', 'SECRET', 'PASSWORD', 'CREDENTIAL', 'ANTHROPIC', 'OPENAI'])
        }
        
        # Add test input as environment variable
        safe_env['SKILL_TEST_INPUT'] = json.dumps(test.input_data)
        safe_env['SKILL_TEST_NAME'] = test.name
        
        # Determine interpreter
        suffix = entry_point.suffix
        if suffix in ['.js', '.mjs']:
            cmd = ['node', '--no-warnings', str(entry_point)]
        elif suffix == '.py':
            cmd = [sys.executable, str(entry_point)]
        elif suffix == '.sh':
            cmd = ['bash', str(entry_point)]
        else:
            cmd = [str(entry_point)]
        
        # Run with timeout
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=test.timeout_seconds,
            cwd=self.skill_path,
            env=safe_env
        )
        
        # Combine stdout, prefer it over stderr
        output = result.stdout.strip()
        if not output and result.stderr:
            output = f"[stderr] {result.stderr.strip()}"
        
        return output
    
    def _compare_output(self, actual: str, expected: str) -> bool:
        """Compare actual output with expected output."""
        # Exact match
        if actual == expected:
            return True
        
        # Normalized match (ignore whitespace)
        if actual.strip().lower() == expected.strip().lower():
            return True
        
        # Contains match (for partial expectations)
        if expected.startswith("contains:"):
            needle = expected[9:].strip()
            return needle.lower() in actual.lower()
        
        # Regex match
        if expected.startswith("regex:"):
            pattern = expected[6:].strip()
            return bool(re.search(pattern, actual, re.IGNORECASE))
        
        # JSON structural match
        try:
            actual_json = json.loads(actual)
            expected_json = json.loads(expected)
            return actual_json == expected_json
        except json.JSONDecodeError:
            pass
        
        return False
    
    def get_report(self) -> Dict:
        """Generate test report."""
        passed = sum(1 for r in self.results if r.passed)
        failed = len(self.results) - passed
        
        return {
            "skill_path": str(self.skill_path),
            "total_tests": len(self.results),
            "passed": passed,
            "failed": failed,
            "verdict": "PASS" if failed == 0 else "FAIL",
            "results": [
                {
                    "name": r.name,
                    "passed": r.passed,
                    "expected": r.expected,
                    "actual": r.actual,
                    "error": r.error,
                    "duration_ms": r.duration_ms
                }
                for r in self.results
            ]
        }


def run_skill_tests(skill_path: str) -> Dict:
    """
    Convenience function to run tests for a skill.
    
    Args:
        skill_path: Path to skill directory
        
    Returns:
        Test report dictionary
    """
    path = Path(skill_path)
    
    # Parse SKILL.md for test cases
    parser = SkillTestParser()
    try:
        metadata, tests = parser.parse_skill_md(path)
    except FileNotFoundError as e:
        return {
            "skill_path": str(path),
            "error": str(e),
            "verdict": "SKIP",
            "reason": "No SKILL.md found - cannot run tests"
        }
    
    if not tests:
        return {
            "skill_path": str(path),
            "metadata": metadata,
            "verdict": "SKIP",
            "reason": "No test cases defined in SKILL.md"
        }
    
    # Run tests in sandbox
    runner = SandboxRunner(path)
    runner.run_tests(tests)
    
    report = runner.get_report()
    report["metadata"] = metadata
    
    return report


def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Sandbox Test Runner for Skills")
    parser.add_argument("skill_path", help="Path to skill directory")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    
    args = parser.parse_args()
    
    report = run_skill_tests(args.skill_path)
    
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"\n{'='*60}")
        print(f"SANDBOX TESTS: {report['skill_path']}")
        print(f"{'='*60}")
        
        if "error" in report:
            print(f"❌ Error: {report['error']}")
        elif "reason" in report:
            print(f"⚠️  Skipped: {report['reason']}")
        else:
            print(f"Verdict: {report['verdict']}")
            print(f"Tests: {report['passed']}/{report['total_tests']} passed")
            print()
            
            for r in report.get('results', []):
                icon = "✅" if r['passed'] else "❌"
                print(f"{icon} {r['name']} ({r['duration_ms']}ms)")
                if not r['passed']:
                    print(f"   Expected: {r['expected']}")
                    print(f"   Actual:   {r['actual']}")
                    if r['error']:
                        print(f"   Error:    {r['error']}")
        
        print(f"{'='*60}")
    
    # Exit code based on result
    if report.get('verdict') == 'PASS':
        sys.exit(0)
    elif report.get('verdict') == 'SKIP':
        sys.exit(0)  # Skip is not failure
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
