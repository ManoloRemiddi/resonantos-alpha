#!/usr/bin/env python3
"""
Logician Client — Python wrapper for the Logician HTTP proxy.

Allows agents and scripts to query the Logician for provable policy checks
without depending on a host-specific grpcurl unix-socket invocation.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import List, Optional


class LogicianClient:
    """Client for the Logician HTTP proxy service."""

    def __init__(self, base_url: str = "http://127.0.0.1:8081"):
        self.base_url = base_url.rstrip("/")

    def query(self, query_str: str, program: str = "") -> List[str]:
        """Send a query to the Logician proxy and return answer strings."""
        payload = json.dumps({"query": query_str, "program": program}).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/query",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")
            raise RuntimeError(f"Query failed: HTTP {e.code}: {body}") from e
        except Exception as e:
            raise RuntimeError(f"Query failed: {e}") from e
        return data.get("answers", []) if isinstance(data, dict) else []

    def can_do(self, query_str: str) -> bool:
        """Check if a query has results (authorization check)."""
        try:
            return len(self.query(query_str)) > 0
        except Exception:
            return False

    def prove(self, statement: str) -> dict:
        """Attempt to prove a statement and return the evidence payload."""
        try:
            results = self.query(statement)
            return {"proven": len(results) > 0, "results": results}
        except Exception as e:
            return {"proven": False, "results": [], "error": str(e)}


def demo() -> None:
    """Interactive demo of the Logician client."""
    client = LogicianClient()

    print("=" * 50)
    print("  Logician — Deterministic Policy Engine")
    print("=" * 50)

    tests = [
        ("📋 All agents", "agent(X)"),
        ("🔐 Who can main spawn?", "spawn_allowed(/main, X)"),
        ("✅ Can main spawn deputy?", "spawn_allowed(/main, /deputy)"),
        ("❌ Can deputy spawn main?", "spawn_allowed(/deputy, /main)"),
        ("🔧 Deputy's tools", "can_use_tool(/deputy, X)"),
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
