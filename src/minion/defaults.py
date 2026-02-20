"""Shared constants — env var names, default paths, resolvers.

Single source of truth for path resolution across all minion subsystems.
Merges commsv2/defaults.py + swarm/config.py path logic.
"""

from __future__ import annotations

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Env var names
# ---------------------------------------------------------------------------

ENV_DB_PATH = "MINION_DB_PATH"
ENV_DOCS_DIR = "MINION_DOCS_DIR"
ENV_PROJECT = "MINION_PROJECT"
ENV_CLASS = "MINION_CLASS"

# ---------------------------------------------------------------------------
# Default paths
# ---------------------------------------------------------------------------

WORK_ROOT = "~/.minion_work"
DEFAULT_DOCS_DIR = "~/.minion_work/docs"

# Project-local directory for intel, traps, code maps
COMMS_DIR_NAME = ".minion-comms"

# Project-local runtime directory for daemon logs, pids, state
SWARM_DIR_NAME = ".minion-swarm"


# ---------------------------------------------------------------------------
# Resolvers
# ---------------------------------------------------------------------------


def resolve_db_path() -> str:
    """Resolve DB path: ENV_DB_PATH > project-derived default."""
    explicit = os.getenv(ENV_DB_PATH)
    if explicit:
        return explicit
    project = os.getenv(ENV_PROJECT) or os.path.basename(os.getcwd())
    return os.path.expanduser(f"{WORK_ROOT}/{project}/minion.db")


def resolve_docs_dir() -> str:
    """Resolve docs dir: ENV_DOCS_DIR > default."""
    return os.getenv(ENV_DOCS_DIR, os.path.expanduser(DEFAULT_DOCS_DIR))


def resolve_comms_dir(project_dir: str | Path | None = None) -> Path:
    """Resolve the project-local .minion-comms directory."""
    base = Path(project_dir) if project_dir else Path.cwd()
    return base / COMMS_DIR_NAME


def resolve_swarm_runtime_dir(project_dir: str | Path | None = None) -> Path:
    """Resolve the project-local .minion-swarm runtime directory."""
    base = Path(project_dir) if project_dir else Path.cwd()
    return base / SWARM_DIR_NAME


def resolve_path(raw_value: str, base: Path) -> Path:
    """Resolve a possibly-relative path against a base directory."""
    path = Path(raw_value).expanduser()
    if not path.is_absolute():
        path = (base / path).resolve()
    return path
