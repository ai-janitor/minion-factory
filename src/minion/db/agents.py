"""Agent-related DB helpers — enrichment, staleness, HP summary.

Functions that read/transform agent rows from the agents table.
Separated from connection/schema because they import from minion.auth
(deferred to avoid circular imports).
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
    """Return the name of the first registered lead agent, or None."""
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
    """Add HP, staleness, and last_seen_mins_ago to an agent row dict."""
    # Import here to avoid circular dependency with auth
    from minion.auth import CLASS_STALENESS_SECONDS

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
        except ValueError:
            import sys
            print(f"WARNING: corrupt context_updated_at for {a.get('name')}: {a['context_updated_at']!r}", file=sys.stderr)
    elif threshold and not a.get("context_updated_at"):
        stale = True
    a["context_stale"] = stale

    if a.get("last_seen"):
        try:
            ls = _to_naive_local(datetime.datetime.fromisoformat(a["last_seen"]))
            a["last_seen_mins_ago"] = int((now - ls).total_seconds() // 60)
        except ValueError:
            import sys
            print(f"WARNING: corrupt last_seen for {a.get('name')}: {a['last_seen']!r}", file=sys.stderr)

    return a


def staleness_check(cursor: sqlite3.Cursor, agent_name: str) -> tuple[bool, str]:
    """Check if agent's context is stale per class threshold.

    Returns (is_stale, message). is_stale=True means BLOCKED.
    """
    from minion.auth import CLASS_STALENESS_SECONDS

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
    except ValueError:
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
