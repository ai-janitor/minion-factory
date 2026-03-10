"""API server daemon lifecycle — start/stop/status/restart.
Wraps network/server.py serve() in a proper daemon managed by minion CLI.
State tracked in ~/.minion/api-server.json (not an agent — infrastructure).

Purpose: API server daemon lifecycle — start/stop/status/restart.
Rationale: Extracted into own module following single-responsibility principle.
Responsibility: API server daemon lifecycle — start/stop/status/restart. NOT responsible for unrelated concerns.
Organization: Re-exports public API symbols. Imports only, no logic."""
