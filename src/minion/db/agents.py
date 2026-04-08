"""Agent-related DB helpers — enrichment, staleness, HP summary.

Functions that read/transform agent rows from the agents table.
Staleness thresholds imported from minion.defaults (shared constants),
not from minion.auth, to avoid db→auth layer violation.
"""

from __future__ import annotations

import datetime
import sqlite3
from typing import Any


def _to_naive_local(dt: datetime.datetime) -> datetime.datetime:
    """Convert a possibly-aware datetime to naive local time.

    Timestamps in the DB may be naive-local (from now_iso()) or
    UTC-aware (from daemon watcher).  Normalise to naive-local so
    subtraction against datetime.now() is always apples-to-apples.
    """
    if dt.tzinfo is not None:
        return dt.astimezone().replace(tzinfo=None)
    return dt


def get_lead(cursor: sqlite3.Cursor) -> str | None:
    """Return the name of the first registered lead agent, or None.

    Big-O: O(N) worst-case where N = agents table rows (no index on agent_class).
    In practice N < 50 agents per project, so effectively O(1).
    """
    cursor.execute("SELECT name FROM agents WHERE agent_class = 'lead' LIMIT 1")
    row = cursor.fetchone()
    return row[0] if row else None


def hp_summary(
    input_tokens: int | None,
    output_tokens: int | None,
    limit: int | None,
    turn_input: int | None = None,
    turn_output: int | None = None,
) -> str:
    """Human-readable HP string from daemon-observed token counts.

    Uses per-turn values for HP% when available (actual context pressure),
    falls back to cumulative. Shows cumulative as session total.
    """
    if not limit:
        return "HP unknown"

    if turn_input is not None:
        used = turn_input
    else:
        used = min(input_tokens or 0, limit)

    if used == 0:
        return "HP unknown"

    pct_used = used / limit * 100
    hp_pct = max(0.0, 100 - pct_used)
    status = "Healthy" if hp_pct > 50 else ("Wounded" if hp_pct > 25 else "CRITICAL")

    return f"{hp_pct:.0f}% HP [{used // 1000}k/{limit // 1000}k] — {status}"


def enrich_agent_row(row: sqlite3.Row, now: datetime.datetime) -> dict[str, Any]:
    """Add HP, staleness, and last_seen_mins_ago to an agent row dict.

    Big-O: O(1) per row — constant-time dict copy + arithmetic.
    Called once per agent in who() and dashboard render, so total O(A) where A = agent count.
    """
    # Import here to avoid circular dependency with auth
    from minion.defaults import CLASS_STALENESS_SECONDS

    a: dict[str, Any] = dict(row)

    a["hp"] = hp_summary(
        a.get("hp_input_tokens"), a.get("hp_output_tokens"), a.get("hp_tokens_limit"),
        turn_input=a.get("hp_turn_input"), turn_output=a.get("hp_turn_output"),
    )

    threshold = CLASS_STALENESS_SECONDS.get(a.get("agent_class", ""))
    stale = False
    if threshold and a.get("context_updated_at"):
        try:
            updated = _to_naive_local(datetime.datetime.fromisoformat(a["context_updated_at"]))
            stale = (now - updated).total_seconds() > threshold
        except (ValueError, TypeError):
            import sys
            print(f"WARNING: corrupt context_updated_at for {a.get('name')}: {a['context_updated_at']!r}", file=sys.stderr)
    elif threshold and not a.get("context_updated_at"):
        stale = True
    a["context_stale"] = stale

    if a.get("last_seen"):
        try:
            ls = _to_naive_local(datetime.datetime.fromisoformat(a["last_seen"]))
            a["last_seen_mins_ago"] = int((now - ls).total_seconds() // 60)
        except (ValueError, TypeError):
            import sys
            print(f"WARNING: corrupt last_seen for {a.get('name')}: {a['last_seen']!r}", file=sys.stderr)

    # Backlog #323: liveness check on the recorded pid. Daemon state files
    # often go stale (status='working' but the actual process died), and
    # 'who'/'sitrep' end up displaying ghost agents as alive. Probe the pid
    # cheaply with kill(pid, 0); if it's gone, mark the row so the operator
    # can see at a glance that this isn't a real running daemon.
    pid = a.get("pid")
    if pid and isinstance(pid, int):
        import os as _os
        try:
            _os.kill(pid, 0)
            a["pid_alive"] = True
        except (OSError, ProcessLookupError):
            a["pid_alive"] = False
            # Don't lie about the status — agents.status is the daemon's
            # self-reported state, but if the pid is dead the daemon can't
            # update it any more. Override with a clear marker.
            if a.get("status") in ("working", "waiting for work", "idle"):
                a["status"] = "dead (pid gone)"

    return a


def staleness_check(cursor: sqlite3.Cursor, agent_name: str) -> tuple[bool, str]:
    """Check if agent's context is stale per class threshold.

    Returns (is_stale, message). is_stale=True means BLOCKED.

    Big-O: O(1) — single indexed lookup by PRIMARY KEY (agents.name), constant-time
    timestamp comparison. Called on every send() and check_inbox().
    """
    # Precondition assertions — backlog #63
    assert cursor is not None, "cursor must not be None"
    assert agent_name, "agent_name must not be empty"

    from minion.defaults import CLASS_STALENESS_SECONDS

    cursor.execute(
        "SELECT agent_class, context_updated_at FROM agents WHERE name = ?",
        (agent_name,),
    )
    row = cursor.fetchone()
    if not row:
        return False, ""

    agent_class: str = row["agent_class"]
    context_updated_at: str | None = row["context_updated_at"]

    threshold = CLASS_STALENESS_SECONDS.get(agent_class)
    if threshold is None:
        return False, ""

    if not context_updated_at:
        return (
            True,
            f"BLOCKED: Context not set. Call set-context before sending. "
            f"({agent_class} threshold: {threshold // 60} min)",
        )

    try:
        updated = _to_naive_local(datetime.datetime.fromisoformat(context_updated_at))
    except (ValueError, TypeError):
        import sys
        print(f"WARNING: corrupt context_updated_at for {agent_name}: {context_updated_at!r}", file=sys.stderr)
        return False, ""

    age_seconds = (datetime.datetime.now() - updated).total_seconds()
    if age_seconds > threshold:
        mins = int(age_seconds // 60)
        return (
            True,
            f"BLOCKED: Context stale ({mins}m old, threshold {threshold // 60}m for {agent_class}). "
            f"Call set-context to update your metrics before sending.",
        )

    return False, ""
