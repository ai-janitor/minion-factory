"""War Room — battle plans and raid log."""

from __future__ import annotations

import json
import os

from minion.auth import BATTLE_PLAN_STATUSES, RAID_LOG_PRIORITIES
from minion.db import get_db, now_iso
from minion.fs import (
    atomic_write_file,
    battle_plan_file_path,
    raid_log_file_path,
    read_content_file,
)


def create_battle_plan(
    set_by: str,
    plan_file: str,
    status: str = "active",
    supersede: bool = True,
) -> dict[str, object]:
    """Insert a battle_plan row without filesystem side effects.

    Pure DB operation — no agent class check, no file writes.
    Intended for test fixtures and programmatic seeding where callers
    manage their own file paths (e.g., tmp_path in tests).

    If supersede=True (default), marks any existing 'active' plans as
    'superseded' before inserting, matching set_battle_plan() semantics.
    """
    conn = get_db()
    cursor = conn.cursor()
    now = now_iso()
    try:
        if supersede and status == "active":
            cursor.execute(
                "UPDATE battle_plan SET status = 'superseded', updated_at = ? WHERE status = 'active'",
                (now,),
            )
        cursor.execute(
            """INSERT INTO battle_plan (set_by, plan_file, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?)""",
            (set_by, plan_file, status, now, now),
        )
        plan_id = cursor.lastrowid
        conn.commit()
        return {"status": status, "plan_id": plan_id, "set_by": set_by, "plan_file": plan_file}
    finally:
        conn.close()


def make_test_battle_plan(
    set_by: str = "lead",
    plan_file: str = "/tmp/test-plan.md",
    status: str = "active",
) -> dict[str, object]:
    """Create a minimal battle_plan row for test fixtures.

    Wraps create_battle_plan() with test-friendly defaults so fixtures
    can seed the table in one line without constructing arguments.
    """
    return create_battle_plan(set_by=set_by, plan_file=plan_file, status=status)


def set_battle_plan(agent_name: str, plan: str) -> dict[str, object]:
    conn = get_db()
    cursor = conn.cursor()
    now = now_iso()
    try:
        cursor.execute("SELECT agent_class FROM agents WHERE name = ?", (agent_name,))
        row = cursor.fetchone()
        if not row:
            return {"error": f"BLOCKED: Agent '{agent_name}' not registered."}
        if row["agent_class"] != "lead":
            return {"error": f"BLOCKED: Only lead-class agents can set the battle plan. '{agent_name}' is '{row['agent_class']}'."}

        # Supersede previous active plans
        cursor.execute(
            "UPDATE battle_plan SET status = 'superseded', updated_at = ? WHERE status = 'active'",
            (now,),
        )

        # Write plan to filesystem — fail before DB insert if write fails
        plan_file = battle_plan_file_path(agent_name)
        try:
            atomic_write_file(plan_file, plan)
        except Exception as exc:
            return {"error": f"BLOCKED: Failed to write battle plan file: {exc}"}

        cursor.execute(
            """INSERT INTO battle_plan (set_by, plan_file, status, created_at, updated_at)
               VALUES (?, ?, 'active', ?, ?)""",
            (agent_name, plan_file, now, now),
        )
        plan_id = cursor.lastrowid
        conn.commit()

        return {"status": "active", "plan_id": plan_id, "set_by": agent_name, "plan_file": plan_file}
    finally:
        conn.close()


def get_battle_plan(status: str = "active") -> dict[str, object]:
    if status not in BATTLE_PLAN_STATUSES:
        return {"error": f"Invalid status '{status}'. Valid: {', '.join(sorted(BATTLE_PLAN_STATUSES))}"}

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT * FROM battle_plan WHERE status = ? ORDER BY created_at DESC",
            (status,),
        )
        plans = []
        for row in cursor.fetchall():
            p = dict(row)
            p["plan_content"] = read_content_file(p.get("plan_file"))
            plans.append(p)

        if not plans:
            return {"plans": [], "note": f"No battle plans with status '{status}'."}
        return {"plans": plans}
    finally:
        conn.close()


def update_battle_plan_status(agent_name: str, plan_id: int, status: str) -> dict[str, object]:
    if status not in BATTLE_PLAN_STATUSES:
        return {"error": f"Invalid status '{status}'. Valid: {', '.join(sorted(BATTLE_PLAN_STATUSES))}"}

    conn = get_db()
    cursor = conn.cursor()
    now = now_iso()
    try:
        cursor.execute("SELECT agent_class FROM agents WHERE name = ?", (agent_name,))
        row = cursor.fetchone()
        if not row:
            return {"error": f"BLOCKED: Agent '{agent_name}' not registered."}
        if row["agent_class"] != "lead":
            return {"error": f"BLOCKED: Only lead-class agents can update battle plan status. '{agent_name}' is '{row['agent_class']}'."}

        cursor.execute("SELECT id, status FROM battle_plan WHERE id = ?", (plan_id,))
        plan_row = cursor.fetchone()
        if not plan_row:
            return {"error": f"Battle plan #{plan_id} not found."}

        old_status = plan_row["status"]
        cursor.execute(
            "UPDATE battle_plan SET status = ?, updated_at = ? WHERE id = ?",
            (status, now, plan_id),
        )
        conn.commit()
        return {"status": "updated", "plan_id": plan_id, "old_status": old_status, "new_status": status}
    finally:
        conn.close()


def log_raid(agent_name: str, entry: str, priority: str = "normal") -> dict[str, object]:
    if priority not in RAID_LOG_PRIORITIES:
        return {"error": f"Invalid priority '{priority}'. Valid: {', '.join(sorted(RAID_LOG_PRIORITIES))}"}

    conn = get_db()
    cursor = conn.cursor()
    now = now_iso()
    try:
        cursor.execute("SELECT name FROM agents WHERE name = ?", (agent_name,))
        if not cursor.fetchone():
            return {"error": f"BLOCKED: Agent '{agent_name}' not registered."}

        # Write entry to filesystem — fail before DB insert if write fails
        entry_file = raid_log_file_path(agent_name, priority)
        try:
            atomic_write_file(entry_file, entry)
        except Exception as exc:
            return {"error": f"BLOCKED: Failed to write raid log file: {exc}"}

        cursor.execute(
            """INSERT INTO raid_log (agent_name, entry_file, priority, created_at)
               VALUES (?, ?, ?, ?)""",
            (agent_name, entry_file, priority, now),
        )
        log_id = cursor.lastrowid

        cursor.execute("UPDATE agents SET last_seen = ? WHERE name = ?", (now, agent_name))
        conn.commit()

        return {"status": "logged", "log_id": log_id, "agent": agent_name, "priority": priority}
    finally:
        conn.close()


def get_raid_log(
    priority: str = "",
    count: int = 20,
    agent_name: str = "",
) -> dict[str, object]:
    if priority and priority not in RAID_LOG_PRIORITIES:
        return {"error": f"Invalid priority '{priority}'. Valid: {', '.join(sorted(RAID_LOG_PRIORITIES))}"}

    conn = get_db()
    cursor = conn.cursor()
    try:
        query = "SELECT * FROM raid_log WHERE 1=1"
        params: list[str | int] = []

        if priority:
            query += " AND priority = ?"
            params.append(priority)
        if agent_name:
            query += " AND agent_name = ?"
            params.append(agent_name)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(count)

        cursor.execute(query, params)
        entries = []
        for row in cursor.fetchall():
            e = dict(row)
            e["entry_content"] = read_content_file(e.get("entry_file"))
            entries.append(e)

        return {"entries": entries}
    finally:
        conn.close()
