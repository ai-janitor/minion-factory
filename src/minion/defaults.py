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

# Project-local work directory for DB, intel, traps, inbox, battle plans
WORK_DIR_NAME = ".work"

# Project-local runtime directory for daemon logs, pids, state
SWARM_DIR_NAME = ".minion-swarm"


# ---------------------------------------------------------------------------
# Resolvers
# ---------------------------------------------------------------------------


def resolve_db_path() -> str:
    """Resolve DB path: ENV_DB_PATH > project-local .work/minion.db."""
    explicit = os.getenv(ENV_DB_PATH)
    if explicit:
        return explicit
    # Explicit project name = legacy ~/.minion_work/ path
    project = os.getenv(ENV_PROJECT)
    if project:
        return os.path.expanduser(f"{WORK_ROOT}/{project}/minion.db")
    # Default: project-local .work/minion.db
    return os.path.join(os.getcwd(), WORK_DIR_NAME, "minion.db")


def resolve_docs_dir() -> str:
    """Resolve docs dir: ENV_DOCS_DIR > default."""
    return os.getenv(ENV_DOCS_DIR, os.path.expanduser(DEFAULT_DOCS_DIR))


def resolve_work_dir(project_dir: str | Path | None = None) -> Path:
    """Resolve the project-local .work directory."""
    base = Path(project_dir) if project_dir else Path.cwd()
    return base / WORK_DIR_NAME


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
