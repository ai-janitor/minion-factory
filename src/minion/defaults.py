"""Shared constants — env var names, default paths, resolvers.
Single source of truth for path resolution across all minion subsystems.
Merges commsv2/defaults.py + swarm/config.py path logic.

Purpose: Shared constants — env var names, default paths, resolvers.
Rationale: Extracted into own module following single-responsibility principle.
Responsibility: Shared constants — env var names, default paths, resolvers. NOT responsible for unrelated concerns.
Organization: Standalone functions and/or a single class. See source.

ASSUMPTIONS:
- resolve_db_path() uses Path.cwd() at call time. If the process cwd changes after
  import, the resolved path changes too. The db/connection.py module caches the first
  resolution — so cwd at first DB access determines the project for the entire process.
- Walk-up DB discovery stops at git repo boundaries. This assumes every project is
  inside a git repo. Non-git projects must set MINION_DB_PATH explicitly or the
  walk-up falls through to cwd fallback.
- MINION_PROJECTS uses colon (:) as separator, Unix-style. This will break on Windows
  paths containing drive letters (C:). Not currently a supported platform.
- CLASS_STALENESS_SECONDS values are hardcoded here, not in the YAML agent-classes
  config. If new agent classes are added to YAML without updating this dict, staleness
  checks will KeyError. The dict.get() callers in db/agents.py handle this gracefully
  but auth.py does not.
- All paths returned by resolvers use os.path or pathlib — they are platform-native.
  Callers storing paths in SQLite must be aware that paths are not portable across
  OS boundaries (forward vs back slashes, case sensitivity).
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

# Network tier env vars — API GLOBAL coordinator
ENV_NETWORK_URL = "MINION_NETWORK_URL"
ENV_CLUSTER_TOKEN = "MINION_CLUSTER_TOKEN"
ENV_NETWORK_INSECURE = "MINION_NETWORK_INSECURE"
ENV_NETWORK_NO_AUTH = "MINION_NETWORK_NO_AUTH"
ENV_MAX_AGENTS = "MINION_MAX_AGENTS"

# Project directory env var — used by network handlers for context switching
ENV_PROJECT_DIR = "MINION_PROJECT_DIR"

# Compat layer env var — auto-project for React frontend bridge
ENV_COMPAT_PROJECT = "MINION_COMPAT_PROJECT"

# Missions directory override
ENV_MISSIONS_DIR = "MINION_MISSIONS_DIR"

# Task flows directory override
ENV_FLOWS_DIR = "MINION_FLOWS_DIR"
ENV_TASKS_FLOWS_DIR = "MINION_TASKS_FLOWS_DIR"

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
# File size limits
# ---------------------------------------------------------------------------

# Maximum file size for unbounded reads — guard against memory exhaustion.
# Applies to intel docs, task specs, backlog READMEs, message files.
# ASSUMPTION: 10 MB is generous for any text artifact. Most are <100 KB.
# Increase if agents start writing large spec documents or concatenated logs.
MAX_DOC_SIZE = 10 * 1024 * 1024  # 10 MB


# ---------------------------------------------------------------------------
# Resolvers
# ---------------------------------------------------------------------------


def _find_git_root(path: Path) -> Path | None:
    """Walk up from *path* to find the nearest directory containing .git.

    Returns the git root Path, or None if no .git is found before filesystem root.
    Handles both regular repos (.git is a directory) and worktrees (.git is a file).
    """
    current = path.resolve()
    while True:
        if (current / ".git").exists():
            return current
        parent = current.parent
        if parent == current:
            return None
        current = parent


def resolve_db_path() -> str:
    """Resolve DB path: ENV_DB_PATH > walk-up .work/minion.db > cwd fallback.

    Walk-up logic: starting from cwd, walk up parent directories looking for
    .work/minion.db. This lets agents launched from subdirectories (or parent
    dirs with -C pointing nearby) find the project DB without explicit -C.

    GUARD: The walk-up will NOT cross git repo boundaries. If a candidate
    .work/minion.db is found in a directory whose git root differs from cwd's
    git root, the candidate is skipped. This prevents silently operating on
    a parent project's DB when running from a child repo or worktree.
    """
    explicit = os.getenv(ENV_DB_PATH)
    if explicit:
        return explicit
    # Explicit project name = legacy ~/.minion_work/ path
    project = os.getenv(ENV_PROJECT)
    if project:
        return os.path.expanduser(f"{WORK_ROOT}/{project}/minion.db")
    # Walk up from cwd looking for .work/minion.db
    cwd = Path.cwd().resolve()
    cwd_git_root = _find_git_root(cwd)
    current = cwd
    while True:
        candidate = current / WORK_DIR_NAME / "minion.db"
        if candidate.exists():
            # Guard: check if this candidate is in the same git repo as cwd.
            # The project root is the parent of .work/ (i.e. `current`).
            candidate_git_root = _find_git_root(current)
            if cwd_git_root is not None and candidate_git_root != cwd_git_root:
                # Crossed a git repo boundary — do NOT use this DB.
                # Stop walking; anything higher is even further away.
                break
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

# ---------------------------------------------------------------------------
# Battle plan / raid log enums — used by warroom.py
# ---------------------------------------------------------------------------
# Canonical source for status/priority validation sets. Placed here to keep
# auth.py free of non-auth constants (same pattern as staleness/triggers above).

BATTLE_PLAN_STATUSES: set[str] = {"active", "superseded", "completed", "abandoned", "obsolete"}

RAID_LOG_PRIORITIES: set[str] = {"low", "normal", "high", "critical"}


# Cross-project coordination — colon-separated list of project paths
ENV_PROJECTS = "MINION_PROJECTS"

ENV_COORDINATOR_DB_PATH = "MINION_COORDINATOR_DB_PATH"


def resolve_coordinator_db_path() -> str:
    """Resolve coordinator DB path: MINION_COORDINATOR_DB_PATH env > ~/.minion/coordinator.db."""
    explicit = os.getenv(ENV_COORDINATOR_DB_PATH)
    if explicit:
        return explicit
    return os.path.join(os.path.expanduser(COORDINATOR_DIR), COORDINATOR_DB_NAME)


def resolve_path(raw_value: str, base: Path) -> Path:
    """Resolve a possibly-relative path against a base directory."""
    # Precondition assertions — backlog #63
    if not isinstance(raw_value, str):
        raise TypeError(f"raw_value must be str, got {type(raw_value).__name__}")
    if not raw_value:
        raise ValueError("raw_value must not be empty")
    if not isinstance(base, Path):
        raise TypeError(f"base must be Path, got {type(base).__name__}")

    path = Path(raw_value).expanduser()
    if not path.is_absolute():
        path = (base / path).resolve()
    return path


# ---------------------------------------------------------------------------
# Network tier resolvers
# ---------------------------------------------------------------------------


def resolve_network_url() -> str:
    """Resolve network URL from env. Empty string means tier disabled."""
    return os.getenv(ENV_NETWORK_URL, "")


def resolve_cluster_token() -> str:
    """Resolve cluster auth token from env. Empty string means no auth."""
    return os.getenv(ENV_CLUSTER_TOKEN, "")


def resolve_network_insecure() -> bool:
    """Resolve whether to skip TLS verification. Default: False (verify)."""
    return os.getenv(ENV_NETWORK_INSECURE, "") == "1"


def resolve_network_no_auth() -> bool:
    """Resolve whether auth is disabled for network server. Default: False (auth required)."""
    return os.getenv(ENV_NETWORK_NO_AUTH, "") == "1"


def resolve_max_agents() -> int:
    """Resolve max concurrent agents per machine. Default: 5."""
    return int(os.getenv(ENV_MAX_AGENTS, "5"))


def resolve_compat_project() -> str:
    """Resolve preferred project name for /api/* compat routes."""
    return os.getenv(ENV_COMPAT_PROJECT, "")


def resolve_missions_dir() -> str | None:
    """Resolve missions directory override from env. None means use defaults."""
    return os.getenv(ENV_MISSIONS_DIR)


def resolve_flows_dir() -> str | None:
    """Resolve task flows directory override from env. None means use defaults."""
    return os.getenv(ENV_FLOWS_DIR) or os.getenv(ENV_TASKS_FLOWS_DIR)


def get_project_paths() -> list[str]:
    """Get list of known project paths from MINION_PROJECTS env var.

    MINION_PROJECTS is a colon-separated list of absolute paths to project roots.
    If not set, returns empty list — caller falls back to coordinator DB.

    SU-19: Used by multi_project_poll for cross-project coordination.
    """
    raw = os.getenv(ENV_PROJECTS, "")
    if not raw:
        return []
    return [p.strip() for p in raw.split(":") if p.strip()]
