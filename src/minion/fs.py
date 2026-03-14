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

from minion.db import RUNTIME_DIR
from minion.defaults import MAX_DOC_SIZE  # noqa: F401 — re-exported for callers

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Base directories
# ---------------------------------------------------------------------------

INBOX_DIR = os.path.join(RUNTIME_DIR, "inbox")
BATTLE_PLAN_DIR = os.path.join(RUNTIME_DIR, "battle-plans")
RAID_LOG_DIR = os.path.join(RUNTIME_DIR, "raid-log")


def ensure_dirs() -> None:
    """Create all required filesystem directories."""
    for d in (INBOX_DIR, BATTLE_PLAN_DIR, RAID_LOG_DIR):
        os.makedirs(d, exist_ok=True)


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

    p = os.path.join(INBOX_DIR, agent_name)
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

    os.makedirs(BATTLE_PLAN_DIR, exist_ok=True)
    fname = f"{_timestamp()}-{_slugify(agent_name, 20)}-plan.md"
    return os.path.join(BATTLE_PLAN_DIR, fname)


def raid_log_file_path(agent_name: str, priority: str) -> str:
    """Build path: raid-log/<ts>-<agent>-<priority>.md"""
    # Precondition assertions — backlog #63
    assert agent_name, "agent_name must not be empty"
    assert priority, "priority must not be empty"
    assert priority in ("low", "normal", "high", "critical"), (
        f"Invalid priority '{priority}'. Must be low/normal/high/critical."
    )

    os.makedirs(RAID_LOG_DIR, exist_ok=True)
    fname = f"{_timestamp()}-{_slugify(agent_name, 20)}-{priority}.md"
    return os.path.join(RAID_LOG_DIR, fname)


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
