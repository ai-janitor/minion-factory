"""Kill, defer, and reopen backlog items — lifecycle boundary operations."""

from __future__ import annotations

import os

from minion.db import get_db
from ._helpers import _get_backlog_path, _now_iso


def _read_readme(file_path: str) -> str:
    """Read the README.md for a backlog item folder."""
    readme_path = os.path.join(file_path, "README.md")
    with open(readme_path) as f:
        return f.read()


def _write_readme(file_path: str, content: str) -> None:
    """Write updated README.md for a backlog item folder."""
    readme_path = os.path.join(file_path, "README.md")
    with open(readme_path, "w") as f:
        f.write(content)


def _append_to_outcome(content: str, entry: str) -> str:
    """Append an entry line under the ## Outcome section.

    If the section exists, appends after it. If not found, adds the section
    at the end of the file.
    """
    section_marker = "## Outcome"
    if section_marker in content:
        # Find the section and append the entry after any existing content there
        idx = content.index(section_marker)
        # Find the end of the section (next ## heading or end of file)
        rest_start = idx + len(section_marker)
        next_section = content.find("\n## ", rest_start)
        if next_section == -1:
            # Append at end of file
            content = content.rstrip() + "\n\n" + entry + "\n"
        else:
            # Insert before the next section
            before = content[:next_section].rstrip()
            after = content[next_section:]
            content = before + "\n\n" + entry + "\n" + after
    else:
        # No Outcome section — append one
        content = content.rstrip() + "\n\n## Outcome\n\n" + entry + "\n"
    return content


def _lookup_item(file_path: str, db_path: str | None) -> dict:
    """Fetch a backlog row by file_path. Raises ValueError if not found."""
    conn = get_db() if db_path is None else _open_db(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM backlog WHERE file_path = ?", (file_path,))
        row = cursor.fetchone()
        if not row:
            raise ValueError(f"Backlog item not found: {file_path}")
        return dict(row)
    finally:
        conn.close()


def _open_db(db_path: str):
    """Open a connection to an explicit DB path (used in tests for isolation)."""
    import sqlite3
    conn = sqlite3.connect(db_path, timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def _update_status(file_path: str, new_status: str, db_path: str | None) -> dict:
    """Update status and updated_at for a backlog item. Returns updated dict."""
    now = _now_iso()
    conn = get_db() if db_path is None else _open_db(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE backlog SET status = ?, updated_at = ? WHERE file_path = ?",
            (new_status, now, file_path),
        )
        conn.commit()
        cursor.execute("SELECT * FROM backlog WHERE file_path = ?", (file_path,))
        row = cursor.fetchone()
        return dict(row)
    finally:
        conn.close()


def kill(file_path: str, reason: str, db: str | None = None) -> dict:
    """Mark a backlog item as killed and record the reason in its README.

    Verifies the item is currently open before transitioning. Appends a
    **Killed** entry to the ## Outcome section of the item's README.md.
    """
    item = _lookup_item(file_path, db)
    if item["status"] != "open":
        raise ValueError(
            f"Cannot kill item with status '{item['status']}' — must be 'open'."
        )

    abs_path = os.path.join(_get_backlog_path(db), file_path)
    content = _read_readme(abs_path)
    date = _now_iso()[:10]  # YYYY-MM-DD
    entry = f"**Killed** on {date}: {reason}"
    content = _append_to_outcome(content, entry)
    _write_readme(abs_path, content)

    return _update_status(file_path, "killed", db)


def defer(file_path: str, until: str, db: str | None = None) -> dict:
    """Mark a backlog item as deferred and record the target date in its README.

    Verifies the item is currently open before transitioning. Appends a
    **Deferred** entry to the ## Outcome section of the item's README.md.
    """
    item = _lookup_item(file_path, db)
    if item["status"] != "open":
        raise ValueError(
            f"Cannot defer item with status '{item['status']}' — must be 'open'."
        )

    abs_path = os.path.join(_get_backlog_path(db), file_path)
    content = _read_readme(abs_path)
    date = _now_iso()[:10]  # YYYY-MM-DD
    entry = f"**Deferred** on {date} until {until}"
    content = _append_to_outcome(content, entry)
    _write_readme(abs_path, content)

    return _update_status(file_path, "deferred", db)


def reopen(file_path: str, db: str | None = None) -> dict:
    """Reopen a killed or deferred backlog item back to open status.

    Verifies the item is in killed or deferred state — open and promoted items
    cannot be reopened. Appends a **Reopened** entry to the ## Outcome section.
    """
    item = _lookup_item(file_path, db)
    if item["status"] not in ("killed", "deferred"):
        raise ValueError(
            f"Cannot reopen item with status '{item['status']}' — "
            f"must be 'killed' or 'deferred'."
        )

    abs_path = os.path.join(_get_backlog_path(db), file_path)
    content = _read_readme(abs_path)
    date = _now_iso()[:10]  # YYYY-MM-DD
    entry = f"**Reopened** on {date}"
    content = _append_to_outcome(content, entry)
    _write_readme(abs_path, content)

    return _update_status(file_path, "open", db)
