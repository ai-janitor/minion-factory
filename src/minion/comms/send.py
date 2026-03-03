"""Message sending — send() local and send_global() cross-repo.

send() delivers within the local project DB with inbox discipline,
CC handling, trigger detection, and lead auto-CC.
send_global() always routes through the coordinator DB for cross-repo delivery.
"""

from __future__ import annotations

import os

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


def send(
    from_agent: str,
    to_agent: str,
    message: str,
    cc: str = "",
) -> dict[str, object]:
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

        # Auto-register unknown senders
        cursor.execute(
            "INSERT OR IGNORE INTO agents (name, agent_class, registered_at, last_seen) VALUES (?, 'coder', ?, ?)",
            (from_agent, now, now),
        )

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
            except Exception:
                pass  # Coordinator unavailable — allow local send

        # Write message body to filesystem
        content_file = message_file_path(to_agent, from_agent)
        atomic_write_file(content_file, message)

        # Insert metadata into DB
        cursor.execute(
            "INSERT INTO messages (from_agent, to_agent, content_file, timestamp, read_flag, is_cc) VALUES (?, ?, ?, ?, 0, 0)",
            (from_agent, to_agent, content_file, now),
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
                       (from_agent, to_agent, content_file, timestamp, read_flag, is_cc, cc_original_to)
                       VALUES (?, ?, ?, ?, 0, 1, ?)""",
                    (from_agent, cc_agent, cc_file, now, to_agent),
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
        # Sender guards — same as send()
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

        # Auto-register unknown senders
        cursor.execute(
            "INSERT OR IGNORE INTO agents (name, agent_class, registered_at, last_seen) VALUES (?, 'coder', ?, ?)",
            (from_agent, now, now),
        )

        # ALWAYS route through coordinator — never check local DB for target
        cross_result = route_cross_repo(to_agent, from_agent, message, now)
        if cross_result:
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
            except Exception:
                pass
            return cross_result

        # Tier 3: API GLOBAL — try network server
        try:
            from minion.network.client import get_client
            net = get_client()
            if net.configured:
                net_result = net.send(from_agent, to_agent, message)
                if "error" not in net_result:
                    cursor.execute("UPDATE agents SET last_seen = ? WHERE name = ?", (now, from_agent))
                    conn.commit()
                    touch_coordinator_activity(from_agent)
                    net_result["routed_via"] = "network"
                    net_result["timestamp"] = now
                    return net_result
                # Network send failed — queue for offline delivery
                from minion.network.outbox import queue_message
                queued = queue_message(from_agent, to_agent, message)
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
        except Exception:
            pass

        return {"error": f"Agent '{to_agent}' not found in coordinator DB or network, or target unreachable."}
    finally:
        conn.close()
