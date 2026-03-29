"""Channel CRUD endpoints — first-class collaboration scopes.

Channels are explicit groupings that agents join. Messages, roster,
and alerts are scoped per channel. Replaces the inferred project_path model.

Purpose: Channel CRUD — create, list, detail, join, leave, members, messages.
Rationale: Makes project/channel a first-class concept in the coordinator,
  not just an inferred project_path field.
Responsibility: Channel lifecycle and membership. Read/write to channels
  and channel_members tables in network.db."""

from __future__ import annotations

import logging
import os
import sqlite3
from datetime import datetime

logger = logging.getLogger(__name__)

from minion.network.server import _DB_LOCK, _get_server_db
from minion.network.handlers.core import _compute_presence


def register(router) -> None:
    """Register channel endpoints."""
    router.add_post("/channels", handle_create_channel)
    router.add_get("/channels", handle_list_channels)
    router.add_get("/channels/{name}", handle_channel_detail)
    router.add_post("/channels/{name}/join", handle_join_channel)
    router.add_post("/channels/{name}/leave", handle_leave_channel)
    router.add_get("/channels/{name}/members", handle_channel_members)
    router.add_get("/channels/{name}/messages", handle_channel_messages)


def _get_or_create_channel(conn: sqlite3.Connection, name: str, created_by: str = "") -> int:
    """Get channel id by name, creating it if it doesn't exist. Returns channel id."""
    row = conn.execute("SELECT id FROM channels WHERE name = ?", (name,)).fetchone()
    if row:
        return row[0]
    now = datetime.now().isoformat()
    conn.execute(
        "INSERT INTO channels (name, created_at, created_by) VALUES (?, ?, ?)",
        (name, now, created_by),
    )
    conn.commit()
    return conn.execute("SELECT id FROM channels WHERE name = ?", (name,)).fetchone()[0]


def handle_create_channel(handler, db_path: str, **kwargs) -> None:
    """POST /channels — create a new channel.

    Body: {"name": "llama-metal", "description": "...", "created_by": "agent-name"}
    """
    body = handler._parse_json_body()
    if not body:
        return
    name = body.get("name", "").strip()
    if not name:
        handler._json_response(400, {"error": "Channel name is required."})
        return

    description = body.get("description", "")
    created_by = body.get("created_by", "")
    now = datetime.now().isoformat()

    with _DB_LOCK:
        conn = _get_server_db(db_path)
        try:
            existing = conn.execute("SELECT id FROM channels WHERE name = ?", (name,)).fetchone()
            if existing:
                handler._json_response(409, {"error": f"Channel '{name}' already exists.", "id": existing[0]})
                return
            conn.execute(
                "INSERT INTO channels (name, created_at, description, created_by) VALUES (?, ?, ?, ?)",
                (name, now, description, created_by),
            )
            conn.commit()
            channel_id = conn.execute("SELECT id FROM channels WHERE name = ?", (name,)).fetchone()[0]
        finally:
            conn.close()

    handler._json_response(201, {"status": "created", "channel": name, "id": channel_id})


def handle_list_channels(handler, db_path: str, **kwargs) -> None:
    """GET /channels — list all channels with member counts and unread totals."""
    with _DB_LOCK:
        conn = _get_server_db(db_path)
        try:
            channels = conn.execute(
                "SELECT c.id, c.name, c.created_at, c.description, c.created_by, "
                "  (SELECT COUNT(*) FROM channel_members cm WHERE cm.channel_id = c.id) AS member_count, "
                "  (SELECT COUNT(*) FROM messages m WHERE m.channel_id = c.id AND m.read_flag = 0) AS total_unread "
                "FROM channels c ORDER BY c.name"
            ).fetchall()
        finally:
            conn.close()

    handler._json_response(200, {
        "channels": [
            {
                "name": ch["name"],
                "id": ch["id"],
                "created_at": ch["created_at"],
                "description": ch["description"],
                "created_by": ch["created_by"],
                "member_count": ch["member_count"],
                "total_unread": ch["total_unread"],
            }
            for ch in channels
        ],
    })


def handle_channel_detail(handler, db_path: str, name: str = "", **kwargs) -> None:
    """GET /channels/{name} — channel detail with members and unread counts."""
    if not name:
        handler._json_response(400, {"error": "Channel name is required."})
        return

    with _DB_LOCK:
        conn = _get_server_db(db_path)
        try:
            channel = conn.execute("SELECT * FROM channels WHERE name = ?", (name,)).fetchone()
            if not channel:
                handler._json_response(404, {"error": f"Channel '{name}' not found."})
                return

            channel_id = channel["id"]

            # Members with presence from agents table
            members = conn.execute(
                "SELECT cm.agent_name, cm.machine_id, cm.role, cm.joined_at, "
                "  a.agent_class, a.model, a.last_seen "
                "FROM channel_members cm "
                "LEFT JOIN agents a ON a.name = cm.agent_name AND a.machine_id = cm.machine_id "
                "WHERE cm.channel_id = ?",
                (channel_id,),
            ).fetchall()

            # Unread counts per agent
            unread = conn.execute(
                "SELECT to_agent, COUNT(*) as cnt FROM messages "
                "WHERE channel_id = ? AND read_flag = 0 GROUP BY to_agent",
                (channel_id,),
            ).fetchall()
            unread_map = {r["to_agent"]: r["cnt"] for r in unread}

            # Total messages
            msg_count = conn.execute(
                "SELECT COUNT(*) as cnt FROM messages WHERE channel_id = ?", (channel_id,)
            ).fetchone()["cnt"]
        finally:
            conn.close()

    handler._json_response(200, {
        "channel": name,
        "id": channel["id"],
        "created_at": channel["created_at"],
        "description": channel["description"],
        "member_count": len(members),
        "message_count": msg_count,
        "members": [
            {
                "name": m["agent_name"],
                "machine": m["machine_id"],
                "role": m["role"],
                "class": m["agent_class"],
                "model": m["model"],
                "presence": _compute_presence(m["last_seen"]),
                "unread": unread_map.get(m["agent_name"], 0),
            }
            for m in members
        ],
    })


def handle_join_channel(handler, db_path: str, name: str = "", **kwargs) -> None:
    """POST /channels/{name}/join — join a channel (auto-creates if needed).

    Body: {"agent": "leo", "machine_id": "trashcan", "role": "member"}
    """
    body = handler._parse_json_body()
    if not body:
        return
    agent = body.get("agent", "").strip()
    if not agent:
        handler._json_response(400, {"error": "Agent name is required."})
        return

    machine_id = body.get("machine_id", "unknown")
    role = body.get("role", "member")
    now = datetime.now().isoformat()

    with _DB_LOCK:
        conn = _get_server_db(db_path)
        try:
            channel_id = _get_or_create_channel(conn, name, created_by=agent)
            try:
                conn.execute(
                    "INSERT INTO channel_members (channel_id, agent_name, machine_id, joined_at, role) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (channel_id, agent, machine_id, now, role),
                )
                conn.commit()
                status = "joined"
            except sqlite3.IntegrityError:
                # Already a member — update role if changed
                conn.execute(
                    "UPDATE channel_members SET role = ? WHERE channel_id = ? AND agent_name = ? AND machine_id = ?",
                    (role, channel_id, agent, machine_id),
                )
                conn.commit()
                status = "already_member"
        finally:
            conn.close()

    handler._json_response(200, {"status": status, "channel": name, "agent": agent, "role": role})


def handle_leave_channel(handler, db_path: str, name: str = "", **kwargs) -> None:
    """POST /channels/{name}/leave — leave a channel.

    Body: {"agent": "leo", "machine_id": "trashcan"}
    """
    body = handler._parse_json_body()
    if not body:
        return
    agent = body.get("agent", "").strip()
    if not agent:
        handler._json_response(400, {"error": "Agent name is required."})
        return

    machine_id = body.get("machine_id", "unknown")

    with _DB_LOCK:
        conn = _get_server_db(db_path)
        try:
            channel = conn.execute("SELECT id FROM channels WHERE name = ?", (name,)).fetchone()
            if not channel:
                handler._json_response(404, {"error": f"Channel '{name}' not found."})
                return
            conn.execute(
                "DELETE FROM channel_members WHERE channel_id = ? AND agent_name = ? AND machine_id = ?",
                (channel["id"], agent, machine_id),
            )
            conn.commit()
        finally:
            conn.close()

    handler._json_response(200, {"status": "left", "channel": name, "agent": agent})


def handle_channel_members(handler, db_path: str, name: str = "", **kwargs) -> None:
    """GET /channels/{name}/members — list channel members with presence."""
    if not name:
        handler._json_response(400, {"error": "Channel name is required."})
        return

    with _DB_LOCK:
        conn = _get_server_db(db_path)
        try:
            channel = conn.execute("SELECT id FROM channels WHERE name = ?", (name,)).fetchone()
            if not channel:
                handler._json_response(404, {"error": f"Channel '{name}' not found."})
                return

            members = conn.execute(
                "SELECT cm.agent_name, cm.machine_id, cm.role, cm.joined_at, "
                "  a.agent_class, a.model, a.last_seen "
                "FROM channel_members cm "
                "LEFT JOIN agents a ON a.name = cm.agent_name AND a.machine_id = cm.machine_id "
                "WHERE cm.channel_id = ?",
                (channel["id"],),
            ).fetchall()
        finally:
            conn.close()

    handler._json_response(200, {
        "channel": name,
        "members": [
            {
                "name": m["agent_name"],
                "machine": m["machine_id"],
                "role": m["role"],
                "class": m["agent_class"],
                "model": m["model"],
                "presence": _compute_presence(m["last_seen"]),
                "joined_at": m["joined_at"],
            }
            for m in members
        ],
    })


def handle_channel_messages(handler, db_path: str, name: str = "", **kwargs) -> None:
    """GET /channels/{name}/messages — messages scoped to this channel."""
    if not name:
        handler._json_response(400, {"error": "Channel name is required."})
        return

    from urllib.parse import parse_qs, urlparse
    parsed = urlparse(handler.path)
    params = parse_qs(parsed.query)
    limit = int(params.get("limit", ["50"])[0])

    with _DB_LOCK:
        conn = _get_server_db(db_path)
        try:
            channel = conn.execute("SELECT id FROM channels WHERE name = ?", (name,)).fetchone()
            if not channel:
                handler._json_response(404, {"error": f"Channel '{name}' not found."})
                return

            messages = conn.execute(
                "SELECT id, from_agent, to_agent, content, timestamp, read_flag "
                "FROM messages WHERE channel_id = ? ORDER BY id DESC LIMIT ?",
                (channel["id"], limit),
            ).fetchall()
        finally:
            conn.close()

    handler._json_response(200, {
        "channel": name,
        "messages": [
            {
                "id": m["id"],
                "from": m["from_agent"],
                "to": m["to_agent"],
                "content": m["content"],
                "timestamp": m["timestamp"],
                "read": bool(m["read_flag"]),
            }
            for m in messages
        ],
    })
