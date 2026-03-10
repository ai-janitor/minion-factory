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

# Global coordinator DB — cross-repo agent registry
COORDINATOR_DIR = "~/.minion"
COORDINATOR_DB_NAME = "coordinator.db"

# Project-local work directory for DB, intel, traps, inbox, battle plans
WORK_DIR_NAME = ".work"

# Project-local runtime directory for daemon logs, pids, state
SWARM_DIR_NAME = ".minion-swarm"


# ---------------------------------------------------------------------------
# Resolvers
# ---------------------------------------------------------------------------


def resolve_db_path() -> str:
    """Resolve DB path: ENV_DB_PATH > walk-up .work/minion.db > cwd fallback.

    Walk-up logic: starting from cwd, walk up parent directories looking for
    .work/minion.db. This lets agents launched from subdirectories (or parent
    dirs with -C pointing nearby) find the project DB without explicit -C.
    """
    explicit = os.getenv(ENV_DB_PATH)
    if explicit:
        return explicit
    # Explicit project name = legacy ~/.minion_work/ path
    project = os.getenv(ENV_PROJECT)
    if project:
        return os.path.expanduser(f"{WORK_ROOT}/{project}/minion.db")
    # Walk up from cwd looking for .work/minion.db
    current = Path.cwd().resolve()
    while True:
        candidate = current / WORK_DIR_NAME / "minion.db"
        if candidate.exists():
            return str(candidate)
        parent = current.parent
        if parent == current:
            break  # reached filesystem root
        current = parent
    # Fallback: project-local .work/minion.db (will be created on init)
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


# ---------------------------------------------------------------------------
# Staleness thresholds (seconds) — enforced on send() and enrichment
# ---------------------------------------------------------------------------
# Canonical source for class-based staleness checking. Both db/agents.py
# and auth.py reference these. Placed here to break the db→auth dependency.

CLASS_STALENESS_SECONDS: dict[str, int] = {
    "coder": 5 * 60,
    "builder": 5 * 60,
    "recon": 5 * 60,
    "lead": 15 * 60,
    "oracle": 30 * 60,
    "planner": 15 * 60,
    "auditor": 5 * 60,
}

# ---------------------------------------------------------------------------
# Trigger words (brevity codes) — used by db/messages.py and auth.py
# ---------------------------------------------------------------------------
# Canonical source for trigger word definitions. Placed here to break
# the db→auth dependency.

TRIGGER_WORDS: dict[str, str] = {
    "fenix_down": "Dump all knowledge to disk before context death. Revival protocol.",
    "moon_crash": "Emergency shutdown. Everyone fenix_down NOW. No new task assignments.",
    "halt": "Finish current work, save state (fenix_down), stand down. Graceful pause — not an emergency. You will be resumed later.",
    "sitrep": "Request status report from target agent.",
    "rally": "All agents focus on the specified target/zone.",
    "retreat": "Pull back from current approach, reassess.",
    "hot_zone": "Area is dangerous/complex, proceed with caution.",
    "stand_down": "Stop work, prepare to deregister.",
    "recon": "Investigate before acting. Gather intel first.",
}


ENV_COORDINATOR_DB_PATH = "MINION_COORDINATOR_DB_PATH"


def resolve_coordinator_db_path() -> str:
    """Resolve coordinator DB path: MINION_COORDINATOR_DB_PATH env > ~/.minion/coordinator.db."""
    explicit = os.getenv(ENV_COORDINATOR_DB_PATH)
    if explicit:
        return explicit
    return os.path.join(os.path.expanduser(COORDINATOR_DIR), COORDINATOR_DB_NAME)


def resolve_path(raw_value: str, base: Path) -> Path:
    """Resolve a possibly-relative path against a base directory."""
    path = Path(raw_value).expanduser()
    if not path.is_absolute():
        path = (base / path).resolve()
    return path
