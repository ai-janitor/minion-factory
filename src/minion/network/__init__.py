"""Network tier — cross-machine agent comms via HTTP API.
Three-tier routing hierarchy:
  LOCAL         (.work/minion.db, same repo)
  SYSTEM GLOBAL (~/.minion/coordinator.db, same machine)
  API GLOBAL    (HTTP server, cross-machine)
Modules:
  server.py      — HTTP server entry point (delegates to router + handlers)
  client.py      — HTTP client for API consumers
  router.py      — URL dispatch table + path pattern matching
  auth.py        — Bearer token validation (extracted from server.py)
  db_schema.py   — Network DB schema SQL + migration for expanded agent columns
  project_db.py  — LRU connection cache for per-project read-only DBs
  discovery.py   — Project discovery from network DB agent project_paths
  outbox.py      — Outbound message queue (unchanged)
  dashboard.py   — Inline HTML dashboard (unchanged)
  handlers/      — Endpoint handler modules (core, projects, flows, etc.)

Purpose: Network tier — cross-machine agent comms via HTTP API.
Rationale: Extracted into own module following single-responsibility principle.
Responsibility: Network tier — cross-machine agent comms via HTTP API. NOT responsible for unrelated concerns.
Organization: Re-exports public API symbols. Imports only, no logic."""

from .server import serve
from .client import NetworkClient
from .project_db import get_project_db
from .discovery import discover_projects

__all__ = ["serve", "NetworkClient", "get_project_db", "discover_projects"]
