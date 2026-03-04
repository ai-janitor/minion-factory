"""API server daemon lifecycle — start/stop/status/restart.

Wraps network/server.py serve() in a proper daemon managed by minion CLI.
State tracked in ~/.minion/api-server.json (not an agent — infrastructure).
"""
