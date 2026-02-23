"""Shared helpers for backlog CRUD operations."""

from __future__ import annotations

import datetime
import os
import re

from minion.db import _get_db_path

# ---------------------------------------------------------------------------
# Vocabulary constants
# ---------------------------------------------------------------------------

VALID_TYPES = {"idea", "bug", "request", "smell", "debt"}
VALID_STATUSES = {"open", "promoted", "killed", "deferred"}
VALID_PRIORITIES = {"unset", "low", "medium", "high", "critical"}

# Each item type lives under its plural folder name inside .work/backlog/
TYPE_TO_FOLDER: dict[str, str] = {
    "idea": "ideas",
    "bug": "bugs",
    "request": "requests",
    "smell": "smells",
    "debt": "debt",
}

# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------


def _get_backlog_path(db: str | None = None) -> str:
    """Resolve .work/backlog/ from the DB location.

    Derives path from the DB file so both stay in the same .work/ tree.
    Accepts an explicit db path override for test isolation.
    """
    db_path = db or _get_db_path()
    work_dir = os.path.dirname(db_path)
    return os.path.join(work_dir, "backlog")


# ---------------------------------------------------------------------------
# README parsing
# ---------------------------------------------------------------------------


def _parse_readme(path: str) -> dict[str, str | None]:
    """Extract structured fields from a backlog item README.md.

    Reads: title (from `# <title>`), type (from `**Type:**`),
    source (from `**Source:**`), date (from `**Date:**`).
    Returns None for any field not found.
    """
    result: dict[str, str | None] = {
        "title": None,
        "type": None,
        "source": None,
        "date": None,
    }

    if not os.path.exists(path):
        return result

    with open(path) as f:
        for line in f:
            line = line.rstrip()

            if result["title"] is None and line.startswith("# "):
                result["title"] = line[2:].strip()
                continue

            m = re.search(r"\*\*Type:\*\*\s*(.+)", line)
            if m and result["type"] is None:
                result["type"] = m.group(1).strip()
                continue

            m = re.search(r"\*\*Source:\*\*\s*(.+)", line)
            if m and result["source"] is None:
                result["source"] = m.group(1).strip()
                continue

            m = re.search(r"\*\*Date:\*\*\s*(.+)", line)
            if m and result["date"] is None:
                result["date"] = m.group(1).strip()
                continue

    return result


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    """Current timestamp in ISO 8601 format."""
    return datetime.datetime.now().isoformat()


def _slugify(title: str) -> str:
    """Convert a title to a URL-safe slug.

    Lowercases, replaces whitespace with hyphens, strips non-alphanumeric
    characters (except hyphens), and collapses repeated hyphens.
    """
    slug = title.lower()
    slug = re.sub(r"\s+", "-", slug)
    slug = re.sub(r"[^a-z0-9\-]", "", slug)
    slug = re.sub(r"-{2,}", "-", slug)
    return slug.strip("-")
