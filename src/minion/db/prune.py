"""DB pruning — delete old records from unbounded-growth tables.

Purpose: Prevent messages, transition_log, invocation_log, and compaction_log
from growing without bound. Deletes rows older than a configurable age.
Rationale: Backlog #61 — these tables accumulate indefinitely in long-running
projects. Without pruning, the DB file grows forever.
Responsibility: Provide prune_old_records() callable and per-table helpers.
Organization: Called by `minion db prune` CLI command.

Pseudo-logic:
  1. Accept a max_age_days parameter (default 30)
  2. Compute cutoff timestamp = now - max_age_days
  3. For each table (messages, transition_log, invocation_log, compaction_log):
     a. DELETE WHERE timestamp_column < cutoff
     b. Track count of deleted rows per table
  4. Also prune broadcast_reads referencing deleted messages (orphan cleanup)
  5. Run VACUUM if any rows were deleted (reclaim disk space)
  6. Return summary dict with per-table delete counts
"""

from __future__ import annotations

import datetime

from minion.db.connection import get_db


def prune_old_records(max_age_days: int = 30) -> dict[str, object]:
    """Delete records older than max_age_days from unbounded-growth tables.

    Tables pruned:
      - messages (timestamp column: timestamp)
      - transition_log (timestamp column: created_at)
      - invocation_log (timestamp column: started_at)
      - compaction_log (timestamp column: compacted_at)
      - broadcast_reads (orphan cleanup — rows referencing deleted messages)

    Returns dict with per-table deletion counts and total rows removed.

    Time complexity: O(n) per table where n = total rows, due to DELETE scan.
    """
    # Precondition: max_age_days must be positive
    assert max_age_days > 0, f"max_age_days must be positive, got {max_age_days}"

    cutoff = (datetime.datetime.now() - datetime.timedelta(days=max_age_days)).isoformat()

    conn = get_db()
    try:
        cursor = conn.cursor()
        counts: dict[str, int] = {}

        # Prune messages — timestamp column is 'timestamp'
        cursor.execute("DELETE FROM messages WHERE timestamp < ?", (cutoff,))
        counts["messages"] = cursor.rowcount

        # Prune broadcast_reads — orphan cleanup for deleted messages
        cursor.execute(
            "DELETE FROM broadcast_reads WHERE message_id NOT IN (SELECT id FROM messages)"
        )
        counts["broadcast_reads"] = cursor.rowcount

        # Prune transition_log — timestamp column is 'created_at'
        cursor.execute("DELETE FROM transition_log WHERE created_at < ?", (cutoff,))
        counts["transition_log"] = cursor.rowcount

        # Prune invocation_log — timestamp column is 'started_at'
        cursor.execute("DELETE FROM invocation_log WHERE started_at < ?", (cutoff,))
        counts["invocation_log"] = cursor.rowcount

        # Prune compaction_log — timestamp column is 'compacted_at'
        cursor.execute("DELETE FROM compaction_log WHERE compacted_at < ?", (cutoff,))
        counts["compaction_log"] = cursor.rowcount

        conn.commit()

        total = sum(counts.values())

        # Reclaim disk space if anything was deleted
        if total > 0:
            conn.execute("VACUUM")

        return {
            "status": "pruned",
            "max_age_days": max_age_days,
            "cutoff": cutoff,
            "deleted": counts,
            "total_deleted": total,
        }
    finally:
        conn.close()
