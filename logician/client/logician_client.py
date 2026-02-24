#!/usr/bin/env python3
"""
Logician Client — Python wrapper for the Mangle gRPC service.

Allows agents and scripts to query the Logician for provable policy checks.

Usage:
    from logician_client import LogicianClient
    
    client = LogicianClient()
    
    # Check if an agent can spawn another
    can = client.can_do("spawn_allowed(/orchestrator, /coder)")
    
    # List all agents
    agents = client.query("agent(X)")
    
    # Prove a statement
    proof = client.prove("can_use_dangerous(/coder, /exec)")
"""

import subprocess
import json
import re
import shutil
from pathlib import Path
from typing import List, Optional


class LogicianClient:
    """Client for the Mangle Logician gRPC service."""
    
    def __init__(self, sock_path: str = "/tmp/mangle.sock", 
                 proto_dir: Optional[str] = None):
        self.sock_path = sock_path
        
        # Find proto directory
        if proto_dir:
            self.proto_dir = Path(proto_dir)
        else:
            # Look relative to this file
            self.proto_dir = Path(__file__).resolve().parent.parent / "mangle-service" / "proto"
        
        # Find grpcurl
        self.grpcurl = self._find_grpcurl()
    
    def _find_grpcurl(self) -> Optional[str]:
        """Find grpcurl binary."""
        # Check PATH
        path = shutil.which("grpcurl")
        if path:
            return path
        
        # Check common locations
        for candidate in [
            Path.home() / "go" / "bin" / "grpcurl",
            Path("/usr/local/bin/grpcurl"),
        ]:
            if candidate.exists():
                return str(candidate)
        
        return None
    
    def query(self, query_str: str, program: str = "") -> List[str]:
        """
        Send a query to the Logician.
        
        Args:
            query_str: Mangle query like "agent(X)" or "spawn_allowed(/orchestrator, X)"
            program: Optional additional rules to evaluate with the query
            
        Returns:
            List of answer strings
        """
        if not self.grpcurl:
            raise RuntimeError(
                "grpcurl not found. Install: "
                "go install github.com/fullstorydev/grpcurl/cmd/grpcurl@latest"
            )
        
        cmd = [
            self.grpcurl,
            "-plaintext",
            "-import-path", str(self.proto_dir),
            "-proto", "mangle.proto",
            "-d", json.dumps({"query": query_str, "program": program}),
            "-unix", self.sock_path,
            "mangle.Mangle.Query"
        ]
        
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=5
        )
        
        if result.returncode != 0:
            raise Exception(f"Query failed: {result.stderr}")
        
        # Parse JSON objects from streaming response
        answers = []
        for obj_str in re.findall(r'\{[^}]+\}', result.stdout):
            try:
                data = json.loads(obj_str)
                if 'answer' in data:
                    answers.append(data['answer'])
            except json.JSONDecodeError:
                pass
        
        return answers
    
    def can_do(self, query_str: str) -> bool:
        """Check if a query has results (authorization check)."""
        try:
            results = self.query(query_str)
            return len(results) > 0
        except Exception:
            return False
    
    def prove(self, statement: str) -> dict:
        """
        Attempt to prove a statement.
        
        Returns:
            {"proven": bool, "results": list}
        """
        try:
            results = self.query(statement)
            return {"proven": len(results) > 0, "results": results}
        except Exception as e:
            return {"proven": False, "results": [], "error": str(e)}


def demo():
    """Interactive demo of the Logician client."""
    client = LogicianClient()
    
    print("=" * 50)
    print("  Logician — Deterministic Policy Engine")
    print("=" * 50)
    
    tests = [
        ("📋 All agents", "agent(X)"),
        ("🔐 Who can orchestrator spawn?", "spawn_allowed(/orchestrator, X)"),
        ("✅ Can orchestrator spawn coder?", "spawn_allowed(/orchestrator, /coder)"),
        ("❌ Can coder spawn orchestrator?", "spawn_allowed(/coder, /orchestrator)"),
        ("🔧 Coder's tools", "can_use_tool(/coder, X)"),
        ("⚠️  Dangerous tool access", "can_use_dangerous(X, Y)"),
    ]
    
    for label, query in tests:
        print(f"\n{label}")
        print(f"   Query: {query}")
        try:
            results = client.query(query)
            if results:
                for r in results:
                    print(f"   → {r}")
            else:
                print("   → (no results)")
        except Exception as e:
            print(f"   ⚠️  {e}")
    
    print(f"\n{'=' * 50}")
    print("  ✅ Demo complete")
    print(f"{'=' * 50}")


if __name__ == "__main__":
    demo()
