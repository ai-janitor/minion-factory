"""Filesystem helpers — path builders, atomic writes, directory setup.
Content lives on disk following the Vercel pattern:
  <timestamp>-<agent>-<slug>.md
SQLite stores the path; agents read the file directly.

Purpose: Filesystem helpers — path builders, atomic writes, directory setup.
Rationale: Extracted into own module following single-responsibility principle.
Responsibility: Filesystem helpers — path builders, atomic writes, directory setup. NOT responsible for unrelated concerns.
Organization: Standalone functions and/or a single class. See source."""

from __future__ import annotations

import logging
import os
import re
import tempfile
from datetime import datetime

from minion.defaults import MAX_DOC_SIZE  # noqa: F401 — re-exported for callers

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Base directories — LAZY (backlog #311)
#
# These were previously computed at import time as `os.path.join(RUNTIME_DIR, ...)`
# which froze the value to whatever the runtime dir was when fs.py was first
# imported. The CLI's -C flag changes the runtime dir AFTER imports complete,
# so cached constants caused war/inbox/raid-log writes to land in the wrong
# project. Resolve on every access via module-level __getattr__ instead.
# ---------------------------------------------------------------------------

_LAZY_DIRS = {
    "INBOX_DIR": "inbox",
    "BATTLE_PLAN_DIR": "battle-plans",
    "RAID_LOG_DIR": "raid-log",
    "AGENT_ACTIVITY_DIR": "agent-activity",
}


def _runtime_subdir(name: str) -> str:
    """Resolve a runtime subdirectory at call time, honoring -C / MINION_DB_PATH."""
    from minion.db import get_runtime_dir
    return os.path.join(get_runtime_dir(), name)


def __getattr__(name: str):
    if name in _LAZY_DIRS:
        return _runtime_subdir(_LAZY_DIRS[name])
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def ensure_dirs() -> None:
    """Create all required filesystem directories (resolved lazily)."""
    for sub in _LAZY_DIRS.values():
        os.makedirs(_runtime_subdir(sub), exist_ok=True)


# ---------------------------------------------------------------------------
# Slug helpers
# ---------------------------------------------------------------------------

def _slugify(text: str, max_len: int = 40) -> str:
    """Convert text to a filesystem-safe slug."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:max_len]


def _timestamp() -> str:
    """Compact ISO timestamp for filenames: 20260219T143022."""
    return datetime.now().strftime("%Y%m%dT%H%M%S")


# ---------------------------------------------------------------------------
# Path builders
# ---------------------------------------------------------------------------

def inbox_path(agent_name: str) -> str:
    """Return the inbox directory for an agent, creating it if needed."""
    # Precondition assertions — backlog #63
    assert agent_name, "agent_name must not be empty"
    assert "/" not in agent_name and "\\" not in agent_name, (
        f"agent_name must not contain path separators: '{agent_name}'"
    )

    p = os.path.join(_runtime_subdir("inbox"), agent_name)
    os.makedirs(p, exist_ok=True)
    return p


def message_file_path(to_agent: str, from_agent: str, slug: str = "msg") -> str:
    """Build path: inbox/<to>/<ts>-<from>-<slug>.md"""
    # Precondition assertions — backlog #63
    assert to_agent, "to_agent must not be empty"
    assert from_agent, "from_agent must not be empty"

    d = inbox_path(to_agent)
    fname = f"{_timestamp()}-{_slugify(from_agent, 20)}-{_slugify(slug, 20)}.md"
    return os.path.join(d, fname)


def battle_plan_file_path(agent_name: str) -> str:
    """Build path: battle-plans/<ts>-<agent>-plan.md"""
    # Precondition assertions — backlog #63
    assert agent_name, "agent_name must not be empty"

    plan_dir = _runtime_subdir("battle-plans")
    os.makedirs(plan_dir, exist_ok=True)
    fname = f"{_timestamp()}-{_slugify(agent_name, 20)}-plan.md"
    return os.path.join(plan_dir, fname)


def raid_log_file_path(agent_name: str, priority: str) -> str:
    """Build path: raid-log/<ts>-<agent>-<priority>.md"""
    # Precondition assertions — backlog #63
    assert agent_name, "agent_name must not be empty"
    assert priority, "priority must not be empty"
    assert priority in ("low", "normal", "high", "critical"), (
        f"Invalid priority '{priority}'. Must be low/normal/high/critical."
    )

    log_dir = _runtime_subdir("raid-log")
    os.makedirs(log_dir, exist_ok=True)
    fname = f"{_timestamp()}-{_slugify(agent_name, 20)}-{priority}.md"
    return os.path.join(log_dir, fname)


# ---------------------------------------------------------------------------
# Atomic file write
# ---------------------------------------------------------------------------

def atomic_write_file(path: str, content: str) -> str:
    """Write content to path atomically (write-to-temp, then rename).

    Returns the final path.
    """
    # Precondition assertions — backlog #63
    if not isinstance(path, str):
        raise TypeError(f"path must be str, got {type(path).__name__}")
    if not path:
        raise ValueError("path must not be empty")
    if not isinstance(content, str):
        raise TypeError(f"content must be str, got {type(content).__name__}")

    d = os.path.dirname(path)
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(content)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError as e:
            log.error("Failed to clean up temp file %s: %s", tmp, e)
        raise
    return path


def read_content_file(path: str | None) -> str:
    """Read a content file, returning empty string if missing, None, or too large."""
    if not path or not os.path.exists(path):
        return ""
    size = os.path.getsize(path)
    if size > MAX_DOC_SIZE:
        log.warning("read_content_file: skipping %s — file too large (%d bytes > %d)", path, size, MAX_DOC_SIZE)
        return ""
    with open(path) as f:
        return f.read()
