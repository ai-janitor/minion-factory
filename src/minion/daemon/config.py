"""Daemon config loader — thin re-export from crew/config.py (DRY).
AgentConfig, SwarmConfig, and load_config are defined once in crew/config.py.
Daemon re-exports them — no duplicate logic, no concrete coupling.

Purpose: Daemon config re-export layer — delegates to crew/config.py.
Rationale: Eliminates duplicate load_config between daemon and crew modules.
Responsibility: Re-export config symbols so existing daemon consumers keep working. NOT responsible for config parsing (that lives in crew/config.py).
Organization: Pure re-export module. See crew/config.py for implementation."""
from __future__ import annotations

# DRY: re-export everything from crew/config — single source of truth.
# Existing consumers (cli/daemon_cmds.py) that import from minion.daemon.config
# continue to work without changes.
from minion.crew.config import AgentConfig, SwarmConfig, load_config  # noqa: F401
