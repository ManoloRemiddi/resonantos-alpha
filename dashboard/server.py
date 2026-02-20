#!/usr/bin/env python3
"""
DEPRECATED — Use server_v2.py instead.

This file exists only for backward compatibility. It launches server_v2.py.
"""
import os
import sys

print("⚠️  server.py is deprecated. Launching server_v2.py instead...")
print("   Next time, run: python3 dashboard/server_v2.py\n")

# Re-exec server_v2.py
here = os.path.dirname(os.path.abspath(__file__))
os.execv(sys.executable, [sys.executable, os.path.join(here, "server_v2.py")] + sys.argv[1:])
