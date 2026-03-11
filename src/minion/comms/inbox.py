"""Inbox operations — check_inbox, check_inbox_silent, get_history, purge_inbox.
Handles reading messages (direct + broadcast), marking as read,
WAL snapshot isolation ordering, and content file inlining.

Purpose: Inbox operations — check_inbox, check_inbox_silent, get_history, purge_inbox.
Rationale: Extracted into own module for single-responsibility agent communication.
Responsibility: Inbox operations — check_inbox, check_inbox_silent, get_history, purge_inbox. NOT responsible for unrelated concerns.
Organization: Standalone functions and/or a single class. See source."""

from __future__ import annotations

import datetime

from minion.db import (
    get_db,
    now_iso,
    staleness_check,
    touch_coordinator_activity,
)
from minion.fs import read_content_file


def check_inbox(agent_name: str, msg_type: str | None = None) -> dict[str, object]:
    """Check and return all unread messages for an agent, marking them as read.

    Big-O: O(M + B) where M = unread direct messages, B = unread broadcast messages.
    Direct query: O(M) scan on to_agent (no index). Broadcast query: O(B) with NOT IN subquery.
    Mark-read writes: O(M) UPDATE + O(B) INSERTs into broadcast_reads.
    File I/O: O(M+B) content file reads. Sorting: O((M+B) * log(M+B)).
    Hot path — called on every poll cycle and explicit inbox check.
    """
    # Precondition assertions — backlog #63
    assert agent_name, "agent_name must not be empty"

    conn = get_db()
    cursor = conn.cursor()
    now = now_iso()
    try:
        # ALL reads BEFORE any writes to avoid WAL snapshot isolation race.
        # An UPDATE/INSERT starts an implicit transaction whose read snapshot
        # would miss messages committed by another process after snapshot was taken.

        # Direct messages
        cursor.execute(
            "SELECT * FROM messages WHERE to_agent = ? AND read_flag = 0",
            (agent_name,),
        )
        direct_msgs = [dict(row) for row in cursor.fetchall()]

        # Broadcast messages
        cursor.execute(
            """SELECT * FROM messages
               WHERE to_agent = 'all'
               AND id NOT IN (SELECT message_id FROM broadcast_reads WHERE agent_name = ?)""",
            (agent_name,),
        )
        broadcast_msgs = [dict(row) for row in cursor.fetchall()]

        # --- Now do all writes ---
        cursor.execute(
            "UPDATE agents SET last_seen = ?, last_inbox_check = ? WHERE name = ?",
            (now, now, agent_name),
        )

        if direct_msgs:
            ids = [m["id"] for m in direct_msgs]
            placeholders = ",".join(["?"] * len(ids))
            cursor.execute(f"UPDATE messages SET read_flag = 1 WHERE id IN ({placeholders})", ids)

        for msg in broadcast_msgs:
            cursor.execute(
                "INSERT OR IGNORE INTO broadcast_reads (agent_name, message_id) VALUES (?, ?)",
                (agent_name, msg["id"]),
            )

        conn.commit()

        all_messages = direct_msgs + broadcast_msgs
        all_messages.sort(key=lambda x: x.get("timestamp", ""))

        # Inline content from files for convenience
        for msg in all_messages:
            msg["content"] = read_content_file(msg.get("content_file"))
            if msg.get("is_cc"):
                msg["cc_note"] = f"[CC] originally to: {msg.get('cc_original_to', 'unknown')}"

        # Filter by msg_type if requested — backlog #66
        if msg_type:
            all_messages = [m for m in all_messages if m.get("msg_type") == msg_type]

        _, stale_msg = staleness_check(cursor, agent_name)

        result: dict[str, object] = {"messages": all_messages}
        if stale_msg:
            result["warning"] = stale_msg.replace("BLOCKED: ", "")

        cursor.execute(
            "SELECT transport, hp_tokens_limit FROM agents WHERE name = ?",
            (agent_name,),
        )
        agent_row = cursor.fetchone()
        if agent_row and agent_row["transport"] == "terminal" and agent_row["hp_tokens_limit"] is None:
            result["hp_reminder"] = (
                f"HP unknown — report with: "
                f"minion set-context --agent {agent_name} --context '...' --hp <0-100>"
            )

        touch_coordinator_activity(agent_name)
        return result
    finally:
        conn.close()


def check_inbox_silent(agent_name: str) -> str:
    """Check inbox and return raw message content only. Empty string if no messages.

    Designed for PostToolUse hooks — fast, no JSON wrapper, no warnings.
    Marks messages as read on retrieval.

    Big-O: Same as check_inbox — O(M + B) where M = direct, B = broadcast messages.
    Optimized for hook context: no staleness check, no JSON envelope.
    """
    conn = get_db()
    cursor = conn.cursor()
    now = now_iso()
    try:
        # ALL reads before writes — WAL snapshot isolation race (see check_inbox)
        cursor.execute(
            "SELECT * FROM messages WHERE to_agent = ? AND read_flag = 0",
            (agent_name,),
        )
        direct_msgs = [dict(row) for row in cursor.fetchall()]

        cursor.execute(
            """SELECT * FROM messages
               WHERE to_agent = 'all'
               AND id NOT IN (SELECT message_id FROM broadcast_reads WHERE agent_name = ?)""",
            (agent_name,),
        )
        broadcast_msgs = [dict(row) for row in cursor.fetchall()]

        # --- Writes ---
        cursor.execute(
            "UPDATE agents SET last_seen = ?, last_inbox_check = ? WHERE name = ?",
            (now, now, agent_name),
        )
        if direct_msgs:
            ids = [m["id"] for m in direct_msgs]
            placeholders = ",".join(["?"] * len(ids))
            cursor.execute(f"UPDATE messages SET read_flag = 1 WHERE id IN ({placeholders})", ids)
        for msg in broadcast_msgs:
            cursor.execute(
                "INSERT OR IGNORE INTO broadcast_reads (agent_name, message_id) VALUES (?, ?)",
                (agent_name, msg["id"]),
            )

        conn.commit()

        all_messages = direct_msgs + broadcast_msgs
        if not all_messages:
            return ""

        all_messages.sort(key=lambda x: x.get("timestamp", ""))
        parts = []
        for msg in all_messages:
            content = read_content_file(msg.get("content_file"))
            sender = msg.get("from_agent", "unknown")
            parts.append(f"[{sender}] {content}")
        return "\n".join(parts)
    finally:
        conn.close()


def get_history(count: int = 20) -> dict[str, object]:
    """Return last N messages across all agents.

    Big-O: O(N * log(N)) where N = total messages (ORDER BY + LIMIT).
    File I/O: O(count) content file reads. Bounded by count parameter (default 20).
    """
    # Precondition assertions — backlog #63
    if not isinstance(count, int) or count < 1:
        raise ValueError(f"count must be a positive int, got {count}")

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM messages ORDER BY timestamp DESC LIMIT ?", (count,))
        msgs = [dict(row) for row in cursor.fetchall()]
        for msg in msgs:
            msg["content"] = read_content_file(msg.get("content_file"))
        return {"messages": msgs[::-1]}
    finally:
        conn.close()


def purge_inbox(agent_name: str, older_than_hours: int = 2) -> dict[str, object]:
    """Delete old messages for an agent and dismiss old broadcasts.

    Big-O: O(M) DELETE on direct messages + O(B) INSERT for broadcast dismissal +
    O(R) orphan cleanup of broadcast_reads. Total O(M + B + R) where M = direct
    messages older than cutoff, B = broadcasts older than cutoff, R = orphaned reads.
    """
    # Precondition assertions — backlog #63
    assert agent_name, "agent_name must not be empty"
    if not isinstance(older_than_hours, int) or older_than_hours < 0:
        raise ValueError(f"older_than_hours must be a non-negative int, got {older_than_hours}")

    conn = get_db()
    cursor = conn.cursor()
    cutoff = (datetime.datetime.now() - datetime.timedelta(hours=older_than_hours)).isoformat()
    try:
        cursor.execute(
            "DELETE FROM messages WHERE to_agent = ? AND timestamp < ?",
            (agent_name, cutoff),
        )
        deleted = cursor.rowcount

        cursor.execute(
            """INSERT OR IGNORE INTO broadcast_reads (agent_name, message_id)
               SELECT ?, id FROM messages WHERE to_agent = 'all' AND timestamp < ?""",
            (agent_name, cutoff),
        )
        dismissed = cursor.rowcount

        cursor.execute(
            """DELETE FROM broadcast_reads
               WHERE agent_name = ?
               AND message_id NOT IN (SELECT id FROM messages)""",
            (agent_name,),
        )
        conn.commit()

        return {
            "status": "purged",
            "agent": agent_name,
            "deleted_direct": deleted,
            "dismissed_broadcasts": dismissed,
            "older_than_hours": older_than_hours,
        }
    finally:
        conn.close()
