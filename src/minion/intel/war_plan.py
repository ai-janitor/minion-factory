"""Show, set, and append the persistent project war plan doc.

Purpose: Show, set, and append the persistent project war plan doc.
Rationale: Extracted into own module for single-responsibility intel management.
Responsibility: Show, set, and append the persistent project war plan doc. NOT responsible for unrelated concerns.
Organization: Standalone functions and/or a single class. See source."""

from __future__ import annotations

import os

from minion.db import get_db
from minion.fs import atomic_write_file, MAX_DOC_SIZE


def _war_plan_path() -> str:
    """Resolve WAR_PLAN.md path lazily — never at import time."""
    from minion.db import RUNTIME_DIR
    return os.path.join(RUNTIME_DIR, "intel", "WAR_PLAN.md")


def show_war_plan() -> dict[str, object]:
    """Read and return the current war plan content."""
    path = _war_plan_path()
    if not os.path.exists(path):
        return {"content": "", "path": path, "note": "No war plan set."}
    size = os.path.getsize(path)
    if size > MAX_DOC_SIZE:
        return {"error": f"War plan too large to read ({size} bytes > {MAX_DOC_SIZE})", "path": path}
    with open(path, encoding="utf-8") as fh:
        content = fh.read()
    return {"content": content, "path": path}


def set_war_plan(agent_name: str, content: str) -> dict[str, object]:
    """Overwrite the war plan atomically. Lead-only."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT agent_class FROM agents WHERE name = ?", (agent_name,))
        row = cursor.fetchone()
        if not row:
            return {"error": f"BLOCKED: Agent '{agent_name}' not registered."}
        if row["agent_class"] != "lead":
            return {"error": f"BLOCKED: Only lead-class agents can set the war plan. '{agent_name}' is '{row['agent_class']}'."}
    finally:
        conn.close()

    path = _war_plan_path()
    try:
        atomic_write_file(path, content)
    except OSError as exc:
        return {"error": f"BLOCKED: Failed to write war plan: {exc}"}
    return {"status": "set", "path": path, "agent": agent_name}


def append_war_plan(agent_name: str, text: str) -> dict[str, object]:
    """Append text to the war plan. Lead-only."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT agent_class FROM agents WHERE name = ?", (agent_name,))
        row = cursor.fetchone()
        if not row:
            return {"error": f"BLOCKED: Agent '{agent_name}' not registered."}
        if row["agent_class"] != "lead":
            return {"error": f"BLOCKED: Only lead-class agents can append to the war plan. '{agent_name}' is '{row['agent_class']}'."}
    finally:
        conn.close()

    path = _war_plan_path()
    existing = ""
    if os.path.exists(path):
        size = os.path.getsize(path)
        if size > MAX_DOC_SIZE:
            return {"error": f"War plan too large to append ({size} bytes > {MAX_DOC_SIZE})", "path": path, "agent": agent_name}
        with open(path, encoding="utf-8") as fh:
            existing = fh.read()

    try:
        atomic_write_file(path, existing + text + "\n")
    except OSError as exc:
        return {"error": f"BLOCKED: Failed to append to war plan: {exc}"}
    return {"status": "appended", "path": path, "agent": agent_name}
