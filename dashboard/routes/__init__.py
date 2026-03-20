"""
ResonantOS Dashboard Routes

Route modules:
- docs: Documentation browsing, reading, and searching
- memory: R-Memory, LCM, and Chatbots
- projects: Projects and TODO management
- wallet: Wallet, Tribes, and Bounties
- system: Agents, Shield, Logician, and System Info
"""

from .docs import register_docs_routes
from .memory import register_memory_routes
from .projects import register_projects_routes
from .wallet import register_wallet_routes
from .system import register_system_routes

__all__ = [
    "register_docs_routes",
    "register_memory_routes",
    "register_projects_routes",
    "register_wallet_routes",
    "register_system_routes",
]
