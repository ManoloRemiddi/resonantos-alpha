#!/usr/bin/env python3
"""
ResonantOS Logician Client

Simple Python wrapper for the Mangle gRPC service.
Allows agents to query the Logician for provable reasoning.
"""

import subprocess
import json
from pathlib import Path
from typing import List, Optional

# Paths
GRPCURL = Path.home() / "go" / "bin" / "grpcurl"
MANGLE_SERVICE = Path.home() / "clawd" / "projects" / "logician" / "poc" / "mangle-service"
PROTO_PATH = MANGLE_SERVICE / "proto"

class LogicianClient:
    """Client for the Mangle Logician service."""
    
    def __init__(self, host: str = "localhost", port: int = 8080):
        self.host = host
        self.port = port
        self.endpoint = f"{host}:{port}"
    
    def query(self, query_str: str) -> List[str]:
        """
        Send a query to the Logician and return results.
        
        Args:
            query_str: Mangle query like "agent(X)" or "can_spawn(/strategist, X)"
            
        Returns:
            List of answers as strings
        """
        cmd = [
            str(GRPCURL),
            "-plaintext",
            "-import-path", str(PROTO_PATH),
            "-proto", "mangle.proto",
            "-d", json.dumps({"query": query_str, "program": ""}),
            self.endpoint,
            "mangle.Mangle.Query"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(MANGLE_SERVICE))
        
        if result.returncode != 0:
            raise Exception(f"Query failed: {result.stderr}")
        
        # Parse JSON objects from output (each result is a separate JSON object)
        answers = []
        # The output contains multiple JSON objects, one per result
        # They're formatted with newlines between braces
        import re
        json_objects = re.findall(r'\{[^}]+\}', result.stdout)
        for obj_str in json_objects:
            try:
                data = json.loads(obj_str)
                if 'answer' in data:
                    answers.append(data['answer'])
            except json.JSONDecodeError:
                pass
        
        return answers
    
    def can_do(self, query_str: str) -> bool:
        """Check if a query has any results (authorization check)."""
        results = self.query(query_str)
        return len(results) > 0
    
    def prove(self, statement: str) -> dict:
        """
        Attempt to prove a statement.
        
        Returns:
            {
                "proven": bool,
                "results": list of matching facts
            }
        """
        results = self.query(statement)
        return {
            "proven": len(results) > 0,
            "results": results
        }


def demo():
    """Run a demo of the Logician client."""
    client = LogicianClient()
    
    print("=" * 60)
    print("ResonantOS Logician - Proof of Concept Demo")
    print("=" * 60)
    
    # Demo 1: List all agents
    print("\n📋 Query: agent(X)")
    print("   Who are all the agents?")
    results = client.query("agent(X)")
    for r in results:
        print(f"   → {r}")
    
    # Demo 2: Check spawn permissions
    print("\n🔐 Query: can_spawn(/strategist, X)")
    print("   Who can Strategist spawn?")
    results = client.query("can_spawn(/strategist, X)")
    for r in results:
        print(f"   → {r}")
    
    # Demo 3: Authorization check
    print("\n✅ Authorization Check: Can Strategist spawn Coder?")
    can = client.can_do("can_spawn(/strategist, /coder)")
    print(f"   → {'YES - Authorized' if can else 'NO - Not authorized'}")
    
    print("\n❌ Authorization Check: Can Coder spawn Designer?")
    can = client.can_do("can_spawn(/coder, /designer)")
    print(f"   → {'YES - Authorized' if can else 'NO - Not authorized'}")
    
    # Demo 4: Which actions need verification
    print("\n⚠️  Query: requires_verification(X)")
    print("   Which actions require verification?")
    results = client.query("requires_verification(X)")
    for r in results:
        print(f"   → {r}")
    
    # Demo 5: Prove admin status
    print("\n👤 Prove: is_admin(/user1)")
    proof = client.prove("is_admin(/user1)")
    print(f"   Proven: {proof['proven']}")
    print(f"   Evidence: {proof['results']}")
    
    print("\n" + "=" * 60)
    print("✅ Logician POC Complete - Deductive reasoning working!")
    print("=" * 60)


if __name__ == "__main__":
    demo()
