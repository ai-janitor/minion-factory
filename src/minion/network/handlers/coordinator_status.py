"""Coordinator status endpoint — GET /coordinator/status.

Returns a consolidated snapshot of the entire coordinator state in one call:
server info, auth state, agent counts, unread messages, alerts, projects.
Designed to be polled by the Swift menu bar app every 5-10 seconds.

Purpose: Single-call dashboard snapshot for the coordinator GUI.
Rationale: Avoids multiple round-trips to /health, /who, /overview, /alerts.
Responsibility: Read-only aggregation. No writes.
Organization: One endpoint, one handler."""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

from minion.network.server import _DB_LOCK
from minion.network.handlers.core import _compute_presence
from minion.network.discovery import discover_projects
from minion.network.project_db import get_project_db

# Schema version — increment when response shape changes.
# Swift client should check this and warn on mismatch.
SCHEMA_VERSION = 2


def register(router) -> None:
    """Register coordinator status endpoint."""
    router.add_get("/coordinator/status", handle_coordinator_status)


def _read_server_state() -> dict:
    """Read the daemon state file for uptime and config info."""
    state_file = Path.home() / ".minion" / "api-server.json"
    if not state_file.exists():
        return {}
    try:
        import json as _json
        return _json.loads(state_file.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _compute_uptime_seconds(started_at: str) -> int:
    """Compute uptime in seconds from a started_at ISO timestamp."""
    if not started_at:
        return 0
    try:
        from minion.db.timestamp_and_agent_registry import parse_iso_to_naive_local
        start = parse_iso_to_naive_local(started_at)
        return int((datetime.now() - start).total_seconds())
    except (ValueError, TypeError):
        return 0


def handle_coordinator_status(handler, db_path: str, **kwargs) -> None:
    """GET /coordinator/status — consolidated coordinator snapshot.

    Returns server info, auth state, agent summary, unread message counts,
    recent alerts, and project list. One call for the GUI to poll.
    """
    # --- Server info ---
    state = _read_server_state()

    # Stable coordinator_id — derived from the DB path (consistent across restarts)
    import hashlib
    coordinator_id = hashlib.sha256(db_path.encode()).hexdigest()[:12]

    server_info = {
        "status": "running",
        "coordinator_id": coordinator_id,
        "uptime_seconds": _compute_uptime_seconds(state.get("started_at", "")),
        "port": state.get("port", 8377),
        "tls": state.get("tls_enabled", False),
        "started_at": state.get("started_at", ""),
    }

    # --- Auth info ---
    token_path = Path.home() / ".minion" / ".api-token"
    auth_info = {
        "enabled": state.get("auth", False),
        "token_path": str(token_path) if token_path.exists() else None,
    }

    # --- Agents from network coordinator DB ---
    agent_summary = {"total": 0, "online": 0, "stale": 0, "offline": 0, "by_class": {}}
    agents_list = []

    from minion.network.server import _get_server_db
    with _DB_LOCK:
        conn = _get_server_db(db_path)
        try:
            rows = conn.execute(
                "SELECT name, agent_class, machine_id, model, last_seen, project_path FROM agents"
            ).fetchall()
        finally:
            conn.close()

    for row in rows:
        presence = _compute_presence(row["last_seen"])
        agent_summary["total"] += 1
        agent_summary[presence] = agent_summary.get(presence, 0) + 1
        cls = row["agent_class"] or "unknown"
        agent_summary["by_class"][cls] = agent_summary["by_class"].get(cls, 0) + 1
        agents_list.append({
            "name": row["name"],
            "class": row["agent_class"],
            "machine": row["machine_id"],
            "model": row["model"],
            "presence": presence,
        })

    # --- Unread messages from network coordinator DB ---
    unread_by_agent = {}
    with _DB_LOCK:
        conn = _get_server_db(db_path)
        try:
            rows = conn.execute(
                "SELECT to_agent, COUNT(*) as cnt FROM messages WHERE read_flag = 0 GROUP BY to_agent"
            ).fetchall()
        finally:
            conn.close()

    for row in rows:
        unread_by_agent[row["to_agent"]] = row["cnt"]
    total_unread = sum(unread_by_agent.values())

    # --- Channels ---
    channels_list = []
    with _DB_LOCK:
        conn = _get_server_db(db_path)
        try:
            ch_rows = conn.execute(
                "SELECT c.id, c.name, "
                "  (SELECT COUNT(*) FROM channel_members cm WHERE cm.channel_id = c.id) AS member_count, "
                "  (SELECT COUNT(*) FROM messages m WHERE m.channel_id = c.id AND m.read_flag = 0) AS total_unread "
                "FROM channels c ORDER BY c.name"
            ).fetchall()

            for ch in ch_rows:
                # Get member names and compute online count
                members = conn.execute(
                    "SELECT cm.agent_name, a.last_seen FROM channel_members cm "
                    "LEFT JOIN agents a ON a.name = cm.agent_name AND a.machine_id = cm.machine_id "
                    "WHERE cm.channel_id = ?", (ch["id"],)
                ).fetchall()
                online = sum(1 for m in members if _compute_presence(m["last_seen"]) == "online")
                channels_list.append({
                    "name": ch["name"],
                    "member_count": ch["member_count"],
                    "online_count": online,
                    "total_unread": ch["total_unread"],
                    "members": [m["agent_name"] for m in members],
                })
        except sqlite3.OperationalError:
            pass  # channels table may not exist yet on old DBs
        finally:
            conn.close()

    # --- Projects ---
    projects = discover_projects(db_path, _DB_LOCK)
    project_names = [p["name"] for p in projects]

    # --- Recent alerts (top 5 from project DBs) ---
    alerts = []
    now = datetime.now()
    for proj in projects:
        pconn = get_project_db(proj["path"])
        if not pconn:
            continue
        try:
            # HP critical agents
            for row in pconn.execute(
                "SELECT name, hp_turn_input, hp_tokens_limit FROM agents"
            ).fetchall():
                raw = row["hp_turn_input"]
                limit = row["hp_tokens_limit"]
                if raw is not None and limit and limit > 0:
                    hp_pct = max(0, 100 - (raw / limit * 100))
                    if hp_pct < 30:
                        alerts.append({
                            "type": "hp_critical",
                            "severity": "critical",
                            "project": proj["name"],
                            "agent": row["name"],
                            "hp_pct": round(hp_pct),
                        })
        except (sqlite3.Error, AttributeError) as e:
            logger.warning("coordinator_status: failed to read project %s: %s", proj["name"], e)

    # Sort by severity, limit to 5
    severity_order = {"critical": 0, "warning": 1, "info": 2}
    alerts.sort(key=lambda a: severity_order.get(a.get("severity", "info"), 2))
    alerts = alerts[:5]

    handler._json_response(200, {
        "schema_version": SCHEMA_VERSION,
        "timestamp": datetime.now().isoformat(),
        "server": server_info,
        "auth": auth_info,
        "agents": agent_summary,
        "agents_list": agents_list,
        "messages": {"total_unread": total_unread, "unread_by_agent": unread_by_agent},
        "alerts": {"total": len(alerts), "items": alerts},
        "channels": {"count": len(channels_list), "items": channels_list},
        "projects": {"count": len(project_names), "names": project_names},
    })
