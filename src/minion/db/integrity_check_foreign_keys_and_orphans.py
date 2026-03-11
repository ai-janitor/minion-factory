"""Integrity checker — validate all FK relationships and detect orphan rows.

Purpose: Check ALL foreign key relationships across all tables and report/fix
         orphan rows (tasks pointing to nonexistent requirements, comments on
         deleted tasks, intel links to missing docs, etc.).
Rationale: PRAGMA foreign_keys=ON only prevents NEW violations. Existing orphan
           data from before FK enforcement was enabled needs detection and cleanup.
           Backlog #239 / task #157.
Responsibility: FK integrity checking, orphan detection, and optional cleanup.
                NOT responsible for schema migrations or connection management.
Organization: Three public functions — check, clean, report. Each takes a
              sqlite3.Connection and returns structured results.
"""

from __future__ import annotations

import logging
import sqlite3
from typing import Any

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# FK relationship definitions — every REFERENCES clause in the schema
# ---------------------------------------------------------------------------

# Each tuple: (source_table, source_column, target_table, target_column, cleanup_action)
# cleanup_action: "null" = SET source_column to NULL, "delete" = DELETE the source row
_FK_RELATIONSHIPS: list[tuple[str, str, str, str, str]] = [
    # tasks.parent_id -> tasks.id (self-referential)
    ("tasks", "parent_id", "tasks", "id", "null"),
    # tasks.requirement_id -> requirements.id
    ("tasks", "requirement_id", "requirements", "id", "null"),
    # task_comments.task_id -> tasks.id
    ("task_comments", "task_id", "tasks", "id", "delete"),
    # intel_links.intel_slug -> intel_docs.slug
    ("intel_links", "intel_slug", "intel_docs", "slug", "delete"),
    # requirements.parent_id -> requirements.id (self-referential)
    ("requirements", "parent_id", "requirements", "id", "null"),
]


# ---------------------------------------------------------------------------
# Check — detect orphan rows across all FK relationships
# ---------------------------------------------------------------------------


def check_all_fk_integrity(conn: sqlite3.Connection) -> dict[str, Any]:
    """Check all FK relationships and return orphan rows.

    Pseudo-logic:
      - For each FK relationship in _FK_RELATIONSHIPS:
        - Query source rows where source_column IS NOT NULL
          AND source_column NOT IN (SELECT target_column FROM target_table)
        - Collect orphan source row IDs (or primary key values)
      - Return dict mapping "source_table.source_column" -> list of orphan IDs
      - Also return a summary count

    Returns:
        {
            "violations": {
                "tasks.parent_id": [<list of task IDs with bad parent_id>],
                "tasks.requirement_id": [<list of task IDs with bad requirement_id>],
                ...
            },
            "total_violations": <int>,
            "status": "clean" | "violations_found"
        }
    """
    violations: dict[str, list[Any]] = {}
    total = 0

    for src_table, src_col, tgt_table, tgt_col, _action in _FK_RELATIONSHIPS:
        key = f"{src_table}.{src_col}"

        # Check if source table exists (migrations may not have run yet)
        table_exists = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?",
            (src_table,),
        ).fetchone()[0]
        if not table_exists:
            continue

        # Check if target table exists
        tgt_exists = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?",
            (tgt_table,),
        ).fetchone()[0]
        if not tgt_exists:
            continue

        # Check if source column exists
        cols = {row[1] for row in conn.execute(f"PRAGMA table_info({src_table})").fetchall()}
        if src_col not in cols:
            continue

        # Determine the primary key of the source table for reporting
        pk_col = _get_primary_key(conn, src_table)

        # Find orphan rows: source_column has a value not found in target
        query = f"""
            SELECT {pk_col} FROM {src_table}
            WHERE {src_col} IS NOT NULL
              AND {src_col} NOT IN (SELECT {tgt_col} FROM {tgt_table})
        """
        orphan_rows = conn.execute(query).fetchall()
        if orphan_rows:
            orphan_ids = [row[0] for row in orphan_rows]
            violations[key] = orphan_ids
            total += len(orphan_ids)

    return {
        "violations": violations,
        "total_violations": total,
        "status": "clean" if total == 0 else "violations_found",
    }


# ---------------------------------------------------------------------------
# Clean — fix orphan references (NULL out or delete rows)
# ---------------------------------------------------------------------------


def clean_orphans(conn: sqlite3.Connection, *, dry_run: bool = True) -> dict[str, Any]:
    """Fix orphan FK references by NULLing or deleting, depending on the relationship.

    Pseudo-logic:
      - For each FK relationship:
        - If cleanup_action is "null": UPDATE source SET source_col = NULL WHERE orphan
        - If cleanup_action is "delete": DELETE FROM source WHERE orphan
      - If dry_run=True, only report what would be done (no writes)
      - Return dict of actions taken per relationship

    Args:
        conn: Database connection.
        dry_run: If True, report but don't modify. If False, apply fixes.

    Returns:
        {
            "actions": {
                "tasks.parent_id": {"action": "null", "count": N},
                ...
            },
            "total_fixed": <int>,
            "dry_run": <bool>
        }
    """
    actions: dict[str, dict[str, Any]] = {}
    total_fixed = 0

    for src_table, src_col, tgt_table, tgt_col, cleanup_action in _FK_RELATIONSHIPS:
        key = f"{src_table}.{src_col}"

        # Check if tables and columns exist
        table_exists = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?",
            (src_table,),
        ).fetchone()[0]
        if not table_exists:
            continue

        tgt_exists = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?",
            (tgt_table,),
        ).fetchone()[0]
        if not tgt_exists:
            continue

        cols = {row[1] for row in conn.execute(f"PRAGMA table_info({src_table})").fetchall()}
        if src_col not in cols:
            continue

        # Count orphans
        count_query = f"""
            SELECT COUNT(*) FROM {src_table}
            WHERE {src_col} IS NOT NULL
              AND {src_col} NOT IN (SELECT {tgt_col} FROM {tgt_table})
        """
        count = conn.execute(count_query).fetchone()[0]

        if count == 0:
            continue

        if not dry_run:
            # Apply the fix
            if cleanup_action == "null":
                conn.execute(f"""
                    UPDATE {src_table} SET {src_col} = NULL
                    WHERE {src_col} IS NOT NULL
                      AND {src_col} NOT IN (SELECT {tgt_col} FROM {tgt_table})
                """)
            elif cleanup_action == "delete":
                conn.execute(f"""
                    DELETE FROM {src_table}
                    WHERE {src_col} IS NOT NULL
                      AND {src_col} NOT IN (SELECT {tgt_col} FROM {tgt_table})
                """)
            conn.commit()
            log.info("Cleaned %d orphan(s) in %s (%s)", count, key, cleanup_action)

        actions[key] = {"action": cleanup_action, "count": count}
        total_fixed += count

    return {
        "actions": actions,
        "total_fixed": total_fixed,
        "dry_run": dry_run,
    }


# ---------------------------------------------------------------------------
# Report — human-readable integrity summary
# ---------------------------------------------------------------------------


def report(conn: sqlite3.Connection) -> str:
    """Generate a human-readable integrity report.

    Pseudo-logic:
      - Call check_all_fk_integrity() to get violations
      - Format as a multi-line report with table headers and counts
      - Return the string

    Returns:
        Human-readable report string.
    """
    result = check_all_fk_integrity(conn)

    lines: list[str] = []
    lines.append("=== FK Integrity Report ===")
    lines.append("")

    if result["status"] == "clean":
        lines.append("All FK relationships are clean. No orphan rows detected.")
        return "\n".join(lines)

    lines.append(f"Total violations: {result['total_violations']}")
    lines.append("")

    for key, orphan_ids in result["violations"].items():
        src_table, src_col = key.split(".")
        lines.append(f"  {key}: {len(orphan_ids)} orphan(s)")
        # Show up to 10 IDs
        shown = orphan_ids[:10]
        lines.append(f"    IDs: {shown}")
        if len(orphan_ids) > 10:
            lines.append(f"    ... and {len(orphan_ids) - 10} more")

    lines.append("")
    lines.append("Run `minion db check-integrity --fix` to clean up.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_primary_key(conn: sqlite3.Connection, table: str) -> str:
    """Return the primary key column name for a table.

    Uses PRAGMA table_info — the 'pk' field is nonzero for PK columns.
    Falls back to 'rowid' if no explicit PK is found.
    """
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    for row in rows:
        # table_info returns (cid, name, type, notnull, dflt_value, pk)
        if row[5]:  # pk field is nonzero
            return row[1]
    return "rowid"
