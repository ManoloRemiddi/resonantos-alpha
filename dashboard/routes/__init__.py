"""
ResonantOS Dashboard Routes

Route modules:
- docs: Documentation browsing, reading, and searching
- memory: R-Memory, LCM, and Chatbots
- projects: Projects and TODO management
- wallet: Wallet (Solana integration)
- bounty: Bounties and Tribes (full implementation)
- profile: Contributor profiles (full implementation)
- system: Agents, Shield, Logician, and System Info
"""

from .docs import register_docs_routes
from .memory import register_memory_routes
from .projects import register_projects_routes
from .wallet import register_wallet_routes
from .system import register_system_routes

try:
    from .bounty import register_bounty_routes
except ImportError:
    register_bounty_routes = None

try:
    from .profile import register_profile_routes
except ImportError:
    register_profile_routes = None

__all__ = [
    "register_docs_routes",
    "register_memory_routes",
    "register_projects_routes",
    "register_wallet_routes",
    "register_system_routes",
    "register_bounty_routes",
    "register_profile_routes",
]
