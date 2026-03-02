"""Network tier — cross-machine agent comms via HTTP API.

Three-tier routing hierarchy:
  LOCAL         (.work/minion.db, same repo)
  SYSTEM GLOBAL (~/.minion/coordinator.db, same machine)
  API GLOBAL    (HTTP server, cross-machine)
"""

from .server import serve
from .client import NetworkClient

__all__ = ["serve", "NetworkClient"]
