"""Message sending — send() local and send_global() cross-repo.
send() delivers within the local project DB with inbox discipline,
CC handling, trigger detection, and lead auto-CC.
send_global() always routes through the coordinator DB for cross-repo delivery.

Purpose: Message sending — send() local and send_global() cross-repo.
Rationale: Extracted into own module for single-responsibility agent communication.
Responsibility: Message sending — send() local and send_global() cross-repo. NOT responsible for unrelated concerns.
Organization: Standalone functions and/or a single class. See source."""

from __future__ import annotations

import os
import sqlite3

from minion.comms.delivery import route_cross_repo
from minion.db import (
    get_coordinator_db,
    get_db,
    get_lead,
    now_iso,
    scan_triggers,
    staleness_check,
    touch_coordinator_activity,
)
from minion.fs import (
    atomic_write_file,
    message_file_path,
)


# Valid message types — backlog #66: typed message taxonomy
VALID_MSG_TYPES = {"order", "sitrep", "query", "response", "alert", "system"}


def send(
    from_agent: str,
    to_agent: str,
    message: str,
    cc: str = "",
    msg_type: str | None = None,
) -> dict[str, object]:
    """Send a message from one agent to another.

    Time complexity: O(1) DB INSERT + O(CC) for CC recipients where CC = number of CC'd agents.
    Big-O: O(CC) where CC is the number of CC recipients (usually 0-3).
    """
    # Precondition assertions — backlog #63
    assert from_agent, "from_agent must not be empty"
    assert to_agent, "to_agent must not be empty"
    assert message, "message must not be empty"
    assert from_agent != to_agent or to_agent == "all", "Cannot send a message to yourself"

    # Validate msg_type if provided — backlog #66
    if msg_type is not None:
        assert msg_type in VALID_MSG_TYPES, (
            f"Invalid msg_type '{msg_type}'. Valid: {sorted(VALID_MSG_TYPES)}"
        )

    # Normalize broadcast alias
    if to_agent == "broadcast":
        to_agent = "all"

    conn = get_db()
    cursor = conn.cursor()
    now = now_iso()
    try:
        # Inbox discipline: must read before sending
        cursor.execute(
            "SELECT COUNT(*) FROM messages WHERE to_agent = ? AND read_flag = 0",
            (from_agent,),
        )
        unread_direct = cursor.fetchone()[0]

        cursor.execute(
            """SELECT COUNT(*) FROM messages
               WHERE to_agent = 'all' AND from_agent != ?
               AND id NOT IN (SELECT message_id FROM broadcast_reads WHERE agent_name = ?)""",
            (from_agent, from_agent),
        )
        unread_broadcast = cursor.fetchone()[0]

        unread = unread_direct + unread_broadcast
        if unread > 0:
            return {"error": f"BLOCKED: You have {unread} unread message(s). Call check-inbox first."}

        # Context freshness
        is_stale, stale_msg = staleness_check(cursor, from_agent)
        if is_stale:
            return {"error": stale_msg}

        # Verify sender is registered (no auto-register — prevents -C flag
        # leaking agent presence into foreign project DBs)
        cursor.execute("SELECT name FROM agents WHERE name = ?", (from_agent,))
        if not cursor.fetchone():
            return {
                "error": f"Agent '{from_agent}' not registered in this project. "
                f"Register first: minion agent register --name {from_agent} --class <role>"
            }

        # Local-only: target must exist in this repo's DB AND belong to this project
        if to_agent != "all":
            cursor.execute("SELECT name FROM agents WHERE name = ?", (to_agent,))
            if not cursor.fetchone():
                return {
                    "error": f"Agent '{to_agent}' not found in local DB. "
                    f"For cross-repo messaging, use: minion comms send global"
                }
            # Cross-check coordinator: if target's project_path differs, reject
            try:
                coord = get_coordinator_db()
                try:
                    row = coord.execute(
                        "SELECT project_path FROM agents WHERE name = ?", (to_agent,)
                    ).fetchone()
                    if row and row["project_path"] and row["project_path"] != os.getcwd():
                        return {
                            "error": f"Agent '{to_agent}' belongs to {row['project_path']}, not this repo. "
                            f"Use: minion comms send global --from {from_agent} --to {to_agent}"
                        }
                finally:
                    coord.close()
            except (sqlite3.DatabaseError, OSError):
                pass  # Coordinator unavailable — allow local send

        # Write message body to filesystem
        content_file = message_file_path(to_agent, from_agent)
        atomic_write_file(content_file, message)

        # Insert metadata into DB (with optional msg_type — backlog #66)
        cursor.execute(
            "INSERT INTO messages (from_agent, to_agent, content_file, timestamp, read_flag, is_cc, msg_type) VALUES (?, ?, ?, ?, 0, 0, ?)",
            (from_agent, to_agent, content_file, now, msg_type),
        )

        # Build CC list: explicit + auto-CC lead
        cc_agents = [a.strip() for a in cc.split(",") if a.strip()] if cc else []

        lead_name = get_lead(cursor)
        if lead_name and from_agent != lead_name and to_agent != lead_name and lead_name not in cc_agents:
            cc_agents.append(lead_name)

        for cc_agent in cc_agents:
            if cc_agent != to_agent:
                cc_file = message_file_path(cc_agent, from_agent, "cc")
                atomic_write_file(cc_file, message)
                cursor.execute(
                    """INSERT INTO messages
                       (from_agent, to_agent, content_file, timestamp, read_flag, is_cc, cc_original_to, msg_type)
                       VALUES (?, ?, ?, ?, 0, 1, ?, ?)""",
                    (from_agent, cc_agent, cc_file, now, to_agent, msg_type),
                )

        # Update sender's last_seen
        cursor.execute("UPDATE agents SET last_seen = ? WHERE name = ?", (now, from_agent))

        # Trigger word detection
        triggers_found = scan_triggers(message)

        if "moon_crash" in triggers_found:
            cursor.execute(
                """INSERT INTO flags (key, value, set_by, set_at)
                   VALUES ('moon_crash', '1', ?, ?)
                   ON CONFLICT(key) DO UPDATE SET value = '1', set_by = excluded.set_by, set_at = excluded.set_at""",
                (from_agent, now),
            )

        if "stand_down" in triggers_found:
            cursor.execute(
                """INSERT INTO flags (key, value, set_by, set_at)
                   VALUES ('stand_down', '1', ?, ?)
                   ON CONFLICT(key) DO UPDATE SET value = '1', set_by = excluded.set_by, set_at = excluded.set_at""",
                (from_agent, now),
            )

        conn.commit()

        result: dict[str, object] = {
            "timestamp": now,
            "status": "sent",
            "from": from_agent,
            "to": to_agent,
        }
        if msg_type:
            result["msg_type"] = msg_type
        if cc_agents:
            result["cc"] = cc_agents
        if triggers_found:
            result["triggers"] = triggers_found

        # Transport-based poll reminder + task nudge for leads
        cursor.execute("SELECT transport, agent_class FROM agents WHERE name = ?", (from_agent,))
        sender_row = cursor.fetchone()
        if sender_row and sender_row["transport"] == "terminal":
            result["reminder"] = "Ensure 'minion poll' is running so you don't miss replies."
        if sender_row and sender_row["agent_class"] == "lead" and to_agent != "all":
            cursor.execute(
                "SELECT COUNT(*) FROM tasks WHERE assigned_to = ? AND status IN ('open', 'assigned', 'in_progress')",
                (to_agent,),
            )
            if cursor.fetchone()[0] == 0:
                result["nudge"] = f"No open task found for {to_agent} — create one with `create-task`"

        # Artifact nudge: large messages with no file path reference likely contain inline artifacts
        _FILE_PATH_SIGNALS = (".work/", ".md\n", ".md ", ".md\t", ".md'", '.md"')
        if len(message) > 500 and not any(sig in message for sig in _FILE_PATH_SIGNALS):
            result["artifact_reminder"] = (
                "Large message without a file path detected. "
                "SDLC artifacts should be written to .work/ first, then referenced by path."
            )

        touch_coordinator_activity(from_agent)
        return result
    finally:
        conn.close()


def send_global(
    from_agent: str,
    to_agent: str,
    message: str,
) -> dict[str, object]:
    """Send a message ALWAYS routed through the coordinator DB.

    Bypasses local DB target lookup — always uses coordinator to find
    the target agent's project_path and delivers to that project's
    .work/minion.db. Sender guards (inbox, battle plan, context) are
    still checked against the sender's local DB.
    """
    conn = get_db()
    cursor = conn.cursor()
    now = now_iso()
    try:
        # Check if sender is registered in THIS project's DB.
        # If not (e.g. using -C to send from a foreign project), skip sender
        # guards — they're meaningless against a DB the sender doesn't belong to.
        # Critically: do NOT auto-register, which would leak presence into the
        # foreign project and trigger stop-hook for the wrong project.
        cursor.execute("SELECT name FROM agents WHERE name = ?", (from_agent,))
        sender_is_local = cursor.fetchone() is not None

        if sender_is_local:
            # Sender guards — only meaningful when sender belongs to this DB
            cursor.execute(
                "SELECT COUNT(*) FROM messages WHERE to_agent = ? AND read_flag = 0",
                (from_agent,),
            )
            unread_direct = cursor.fetchone()[0]
            cursor.execute(
                """SELECT COUNT(*) FROM messages
                   WHERE to_agent = 'all' AND from_agent != ?
                   AND id NOT IN (SELECT message_id FROM broadcast_reads WHERE agent_name = ?)""",
                (from_agent, from_agent),
            )
            unread_broadcast = cursor.fetchone()[0]
            unread = unread_direct + unread_broadcast
            if unread > 0:
                return {"error": f"BLOCKED: You have {unread} unread message(s). Call check-inbox first."}

            is_stale, stale_msg = staleness_check(cursor, from_agent)
            if is_stale:
                return {"error": stale_msg}

        # Commit before cross-repo delivery.
        # Without this, the open read transaction on THIS connection blocks
        # route_cross_repo() from writing to the same DB when sender and
        # recipient share a project (same-project global send).
        conn.commit()

        # ALWAYS route through coordinator — never check local DB for target
        cross_result = route_cross_repo(to_agent, from_agent, message, now)
        if cross_result:
            if sender_is_local:
                cursor.execute("UPDATE agents SET last_seen = ? WHERE name = ?", (now, from_agent))
                conn.commit()
            touch_coordinator_activity(from_agent)
            # Warn if recipient doesn't have poll running
            try:
                from minion.polling import is_poll_alive
                target_project = cross_result.get("target_project", "")
                if target_project and not is_poll_alive(to_agent, target_project):
                    cross_result["reminder"] = (
                        f"Recipient '{to_agent}' does not have poll running. "
                        f"Make sure they have poll in the foreground if operating from a terminal."
                    )
            except ImportError:
                pass  # polling module unavailable
            return cross_result

        # Tier 3: API GLOBAL — try network server
        try:
            from minion.network.client import get_client
            net = get_client()
            if net.configured:
                net_result = net.send(from_agent, to_agent, message)
                if "error" not in net_result:
                    if sender_is_local:
                        cursor.execute("UPDATE agents SET last_seen = ? WHERE name = ?", (now, from_agent))
                        conn.commit()
                    touch_coordinator_activity(from_agent)
                    net_result["routed_via"] = "network"
                    net_result["timestamp"] = now
                    return net_result
                # Network send failed — queue for offline delivery
                from minion.network.outbox import queue_message
                queued = queue_message(from_agent, to_agent, message)
                if sender_is_local:
                    cursor.execute("UPDATE agents SET last_seen = ? WHERE name = ?", (now, from_agent))
                    conn.commit()
                return {
                    "timestamp": now,
                    "status": "queued",
                    "from": from_agent,
                    "to": to_agent,
                    "queued_file": queued,
                    "reason": net_result.get("error", "network send failed"),
                }
        except (ImportError, OSError):
            pass  # network tier unavailable

        return {"error": f"Agent '{to_agent}' not found in coordinator DB or network, or target unreachable."}
    finally:
        conn.close()


def sitrep_global(
    from_agent: str,
    message: str = "",
) -> dict[str, object]:
    """Send a cross-project sitrep to all project leads.

    Purpose: SU-19 cross-project coordination — allows a coordinator agent to
             broadcast a status report to all leads across all known projects.
    Rationale: A coordinator needs to send sitreps up and laterally without
               knowing every lead's name or project. This discovers all leads
               from the coordinator DB and sends to each.

    Pseudo-logic:
      1. Query coordinator DB for all agents with class 'lead' or 'coordinator'
      2. Deduplicate by name (agent may be in multiple projects)
      3. For each lead: send_global(from_agent, lead_name, sitrep_message)
      4. Return summary: {sent_to: [...], failed: [...]}
    """
    assert from_agent, "from_agent must not be empty"

    # PSEUDO: build the sitrep message — use monitoring.sitrep() if no custom message
    if not message:
        try:
            from minion.monitoring import sitrep as _sitrep
            sitrep_data = _sitrep()
            import json
            message = f"SITREP from {from_agent}:\n{json.dumps(sitrep_data, indent=2, default=str)}"
        except (ImportError, ValueError):
            message = f"SITREP from {from_agent}: (unable to gather status data)"

    # PSEUDO: discover all leads from coordinator DB
    leads: set[str] = set()
    try:
        coord = get_coordinator_db()
        try:
            rows = coord.execute(
                "SELECT DISTINCT name FROM agents WHERE agent_class IN ('lead', 'coordinator')"
            ).fetchall()
            leads = {r[0] for r in rows if r[0] != from_agent}
        finally:
            coord.close()
    except (sqlite3.DatabaseError, OSError):
        pass  # coordinator DB unavailable

    if not leads:
        return {"error": "No leads found in coordinator DB to send sitrep to."}

    # PSEUDO: send to each lead via send_global
    sent_to: list[str] = []
    failed: list[dict[str, str]] = []
    for lead in sorted(leads):
        try:
            result = send_global(from_agent, lead, message)
            if "error" in result:
                failed.append({"agent": lead, "error": str(result["error"])})
            else:
                sent_to.append(lead)
        except (OSError, sqlite3.DatabaseError, ValueError) as e:
            failed.append({"agent": lead, "error": str(e)})

    return {
        "status": "sitrep_sent",
        "from": from_agent,
        "sent_to": sent_to,
        "failed": failed,
        "total_leads": len(leads),
    }
