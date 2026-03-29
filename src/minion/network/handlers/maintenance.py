"""Maintenance endpoints — retention pruning for coordinator data.

Short TTLs for routine messages/alerts/heartbeat history.
Durable identity/membership state kept longer.
Both automatic periodic prune and explicit maintenance command.

Purpose: Data retention and pruning for the coordinator DB.
Rationale: SQLite is fine but routine data accumulates. Prune, don't migrate.
Responsibility: Delete old messages, heartbeat history, stale alerts.
  NOT responsible for identity or membership — those are durable."""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

from minion.network.server import _DB_LOCK, _get_server_db

# Retention defaults (days)
DEFAULT_MESSAGE_RETENTION_DAYS = 7      # routine messages
DEFAULT_READ_MESSAGE_RETENTION_DAYS = 3  # already-read messages pruned sooner
DEFAULT_ALERT_RETENTION_DAYS = 3         # alerts
DEFAULT_OFFLINE_AGENT_DAYS = 30          # agents offline > 30 days get pruned (not identity, just network row)


def register(router) -> None:
    """Register maintenance endpoints."""
    router.add_post("/maintenance/prune", handle_prune)
    router.add_get("/maintenance/stats", handle_stats)


def prune_db(db_path: str, message_days: int = DEFAULT_MESSAGE_RETENTION_DAYS,
             read_message_days: int = DEFAULT_READ_MESSAGE_RETENTION_DAYS) -> dict:
    """Run retention pruning on the coordinator DB. Returns counts of deleted rows."""
    now = datetime.now()
    message_cutoff = (now - timedelta(days=message_days)).isoformat()
    read_cutoff = (now - timedelta(days=read_message_days)).isoformat()

    results = {}

    with _DB_LOCK:
        conn = _get_server_db(db_path)
        try:
            # Prune read messages older than read_message_days
            cursor = conn.execute(
                "DELETE FROM messages WHERE read_flag = 1 AND timestamp < ?",
                (read_cutoff,),
            )
            results["read_messages_pruned"] = cursor.rowcount

            # Prune all messages older than message_days (even unread)
            cursor = conn.execute(
                "DELETE FROM messages WHERE timestamp < ?",
                (message_cutoff,),
            )
            results["old_messages_pruned"] = cursor.rowcount

            conn.commit()
        finally:
            conn.close()

    results["status"] = "pruned"
    results["message_retention_days"] = message_days
    results["read_message_retention_days"] = read_message_days
    return results


def get_stats(db_path: str) -> dict:
    """Get coordinator DB statistics for maintenance visibility."""
    with _DB_LOCK:
        conn = _get_server_db(db_path)
        try:
            msg_total = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
            msg_unread = conn.execute("SELECT COUNT(*) FROM messages WHERE read_flag = 0").fetchone()[0]
            msg_read = msg_total - msg_unread
            agent_total = conn.execute("SELECT COUNT(*) FROM agents").fetchone()[0]

            channel_count = 0
            member_count = 0
            try:
                channel_count = conn.execute("SELECT COUNT(*) FROM channels").fetchone()[0]
                member_count = conn.execute("SELECT COUNT(*) FROM channel_members").fetchone()[0]
            except sqlite3.OperationalError:
                pass  # tables may not exist on old DBs

            # DB file size
            db_size_row = conn.execute("PRAGMA page_count").fetchone()
            page_size_row = conn.execute("PRAGMA page_size").fetchone()
            db_size_bytes = (db_size_row[0] * page_size_row[0]) if db_size_row and page_size_row else 0
        finally:
            conn.close()

    return {
        "messages": {"total": msg_total, "unread": msg_unread, "read": msg_read},
        "agents": {"total": agent_total},
        "channels": {"total": channel_count, "memberships": member_count},
        "db_size_bytes": db_size_bytes,
        "db_size_mb": round(db_size_bytes / (1024 * 1024), 2),
    }


def handle_prune(handler, db_path: str, **kwargs) -> None:
    """POST /maintenance/prune — run retention pruning.

    Optional body: {"message_days": 7, "read_message_days": 3}
    """
    body = handler._parse_json_body()
    if body is None:
        body = {}

    message_days = body.get("message_days", DEFAULT_MESSAGE_RETENTION_DAYS)
    read_message_days = body.get("read_message_days", DEFAULT_READ_MESSAGE_RETENTION_DAYS)

    result = prune_db(db_path, message_days=message_days, read_message_days=read_message_days)
    handler._json_response(200, result)


def handle_stats(handler, db_path: str, **kwargs) -> None:
    """GET /maintenance/stats — coordinator DB statistics."""
    handler._json_response(200, get_stats(db_path))
