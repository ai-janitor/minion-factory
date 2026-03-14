"""SQL queries for the TUI dashboard.
All queries use PRAGMA query_only=ON connection — no writes permitted.
Returns list[sqlite3.Row] so render layer can access columns by name.

Purpose: SQL queries for the TUI dashboard.
Rationale: Extracted into own module following single-responsibility principle.
Responsibility: SQL queries for the TUI dashboard. NOT responsible for unrelated concerns.
Organization: Standalone functions and/or a single class. See source."""

from __future__ import annotations

import logging
import sqlite3

from minion.tasks.dag import TERMINAL_STATUSES

logger = logging.getLogger(__name__)

# Build SQL literal from the single source of truth — safe (values are code-controlled, not user input).
_TERMINAL_SQL = ", ".join(f"'{s}'" for s in sorted(TERMINAL_STATUSES))


def fetch_tasks(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Active tasks ordered by status priority then ID.

    Excludes terminal states. Includes blocked_by for tree rendering.
    Includes requirement_id so web_server can map tasks back to originating
    backlog items via fetch_task_to_backlog_map (#193).

    Big-O: O(T * log(T)) where T = active (non-terminal) tasks. Full table scan
    with NOT IN filter + CASE-based ORDER BY. LIMIT 50 caps output. Hot path —
    called every 2 seconds by dashboard loop.
    """
    cursor = conn.execute("""
        SELECT
            t.id,
            SUBSTR(t.title, 1, 40)          AS title_short,
            t.status,
            COALESCE(t.assigned_to, '—')    AS assignee,
            COALESCE(t.class_required, '')  AS class_req,
            t.flow_type,
            t.blocked_by,
            t.activity_count,
            t.result_file IS NOT NULL       AS has_result,
            t.requirement_id
        FROM tasks t
        WHERE t.status NOT IN (""" + _TERMINAL_SQL + """)
        ORDER BY
            CASE t.status
                WHEN 'in_progress' THEN 0
                WHEN 'assigned'    THEN 1
                WHEN 'fixed'          THEN 2
                WHEN 'findings_ready' THEN 2
                WHEN 'verified'       THEN 3
                WHEN 'assessed'       THEN 3
                WHEN 'open'        THEN 4
                ELSE 5
            END,
            t.id ASC
        LIMIT 50
    """)
    return cursor.fetchall()


def fetch_agents(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Daemon agents with HP metrics for bar rendering.

    Computes effective_last_seen as the most recent of last_seen,
    context_updated_at, or registered_at — so newly registered agents
    that haven't heartbeated yet don't show "never".

    Big-O: O(A * log(A)) where A = agents with daemon/terminal transport.
    Full scan + ORDER BY agent_class, name. Hot path — called every 2s by dashboard.
    """
    cursor = conn.execute("""
        SELECT
            name,
            agent_class,
            COALESCE(model, '')                                             AS model,
            status,
            transport,
            COALESCE(hp_input_tokens, 0)  + COALESCE(hp_output_tokens, 0)  AS tokens_used,
            COALESCE(hp_tokens_limit, 0)                                    AS tokens_limit,
            hp_updated_at,
            last_seen,
            registered_at,
            MAX(
                COALESCE(last_seen, ''),
                COALESCE(context_updated_at, ''),
                COALESCE(registered_at, '')
            ) AS effective_last_seen
        FROM agents
        WHERE transport IN ('daemon', 'daemon-ts', 'terminal')
        ORDER BY agent_class, name
    """)
    return cursor.fetchall()


def get_agent_summary(conn: sqlite3.Connection) -> list[dict]:
    """Query all agents with health data for web dashboard.

    SU-22: Returns enriched agent list with HP percentage, current task, unread count.

    Big-O: O(A * (T + M)) where A = agents, T = tasks per agent (LIMIT 1 subquery),
    M = messages per agent (COUNT). Each agent triggers 2 additional queries.
    Total: O(A) agents * O(1) per subquery = O(A). Space: O(A).
    """
    agents = []
    for row in conn.execute(
        "SELECT name, agent_class, status, hp_turn_input, hp_tokens_limit, "
        "last_seen, registered_at FROM agents ORDER BY agent_class, name"
    ).fetchall():
        agent = dict(row)
        # Compute HP percentage
        raw = agent.get("hp_turn_input")
        limit = agent.get("hp_tokens_limit")
        if raw is not None and limit and limit > 0:
            agent["hp_pct"] = max(0, round(100 - (raw / limit * 100)))
        else:
            agent["hp_pct"] = None

        # Current task
        task_row = conn.execute(
            "SELECT id, title, status FROM tasks WHERE assigned_to = ? "
            f"AND status NOT IN ({_TERMINAL_SQL}) LIMIT 1",
            (agent["name"],),
        ).fetchone()
        agent["current_task"] = dict(task_row) if task_row else None

        # Unread message count
        unread = conn.execute(
            "SELECT COUNT(*) FROM messages WHERE to_agent = ? AND read_flag = 0",
            (agent["name"],),
        ).fetchone()
        agent["unread_count"] = unread[0] if unread else 0

        agents.append(agent)
    return agents


def get_task_pipeline(conn: sqlite3.Connection) -> dict[str, list[dict]]:
    """Query tasks grouped by status for kanban-style display.

    SU-22: Returns {status: [task_dicts]} for web dashboard pipeline view.

    Big-O: O(T * log(T)) where T = total tasks (ORDER BY updated_at DESC, full scan).
    Space: O(T) for the result dict. No LIMIT — returns all tasks.
    """
    pipeline: dict[str, list[dict]] = {}
    for row in conn.execute(
        # requirement_id included so frontend can resolve originating backlog ID (#193)
        "SELECT id, title, status, assigned_to, flow_type, updated_at, requirement_id "
        "FROM tasks ORDER BY updated_at DESC"
    ).fetchall():
        task = dict(row)
        status = task["status"]
        if status not in pipeline:
            pipeline[status] = []
        pipeline[status].append(task)
    return pipeline


def get_system_stats(conn: sqlite3.Connection, db_path: str = "") -> dict:
    """Query DB and system stats for web dashboard health view.

    SU-22: Returns DB size, row counts per table, WAL mode, agent/task counts.

    Big-O: O(sum(Ni)) where Ni = row count of each table. COUNT(*) on each table
    is O(Ni) without covering index. Number of tables is fixed (~15), so bounded by
    total DB row count. Also runs GROUP BY on agents and tasks — O(A + T).
    """
    import os
    stats: dict = {"tables": {}, "agents": {}, "tasks": {}}

    # DB file size
    if db_path and os.path.exists(db_path):
        stats["db_size_bytes"] = os.path.getsize(db_path)
    else:
        stats["db_size_bytes"] = 0

    # WAL mode
    try:
        mode = conn.execute("PRAGMA journal_mode").fetchone()
        stats["journal_mode"] = mode[0] if mode else "unknown"
    except sqlite3.DatabaseError:
        stats["journal_mode"] = "unknown"

    # Row counts per table
    try:
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
        for (table_name,) in tables:
            try:
                count = conn.execute(f"SELECT COUNT(*) FROM [{table_name}]").fetchone()[0]
                stats["tables"][table_name] = count
            except sqlite3.DatabaseError:
                stats["tables"][table_name] = -1
    except sqlite3.DatabaseError as e:
        logger.error("Failed to fetch table row counts: %s", e)

    # Agent breakdown
    try:
        stats["agents"]["total"] = conn.execute("SELECT COUNT(*) FROM agents").fetchone()[0]
        for row in conn.execute("SELECT agent_class, COUNT(*) as cnt FROM agents GROUP BY agent_class").fetchall():
            stats["agents"][row["agent_class"] or "unknown"] = row["cnt"]
    except sqlite3.DatabaseError as e:
        logger.error("Failed to fetch agent breakdown: %s", e)

    # Task breakdown
    try:
        stats["tasks"]["total"] = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        for row in conn.execute("SELECT status, COUNT(*) as cnt FROM tasks GROUP BY status").fetchall():
            stats["tasks"][row["status"]] = row["cnt"]
    except sqlite3.DatabaseError as e:
        logger.error("Failed to fetch task breakdown: %s", e)

    return stats


def get_recent_messages(conn: sqlite3.Connection, limit: int = 50) -> list[dict]:
    """Query recent messages for web dashboard message view.

    SU-22: Returns last N messages with all fields, newest first.
    """
    rows = conn.execute(
        "SELECT * FROM messages ORDER BY timestamp DESC LIMIT ?", (limit,)
    ).fetchall()
    return [dict(r) for r in rows]


def fetch_backlog(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Promoted backlog items — items that have been promoted to tasks.

    Shows backlog items with their promoted_to task ID so the TUI can display
    the DAG stage of the linked task. Only shows items with status != 'closed'.
    Backlog #112: TUI dashboard should show promoted backlog items with DAG stage.

    Big-O: O(B * log(B)) where B = non-closed backlog items. LEFT JOIN tasks is
    O(B) with PK lookup on tasks.id. CASE-based ORDER BY + LIMIT 20. Hot path —
    called every 2s by dashboard.
    """
    # The backlog table may not exist in older DBs — fail gracefully
    try:
        cursor = conn.execute("""
            SELECT
                b.id,
                b.type,
                SUBSTR(b.title, 1, 35)              AS title_short,
                b.priority,
                b.status,
                b.promoted_to,
                COALESCE(t.status, '')               AS task_status,
                COALESCE(t.assigned_to, '')          AS task_assignee,
                b.updated_at
            FROM backlog b
            LEFT JOIN tasks t ON b.promoted_to = CAST(t.id AS TEXT)
            WHERE b.status NOT IN ('closed', 'abandoned', 'killed')
            ORDER BY
                CASE b.priority
                    WHEN 'critical' THEN 0
                    WHEN 'high'     THEN 1
                    WHEN 'medium'   THEN 2
                    WHEN 'low'      THEN 3
                    ELSE 4
                END,
                b.id ASC
            LIMIT 20
        """)
        return cursor.fetchall()
    except sqlite3.DatabaseError:
        return []


def fetch_lineage(conn: sqlite3.Connection, backlog_id: int, work_dir: str = "") -> dict:
    """Fetch full lineage for a backlog item: backlog → requirements → tasks → transitions.

    Returns a dict with:
      - backlog: the backlog row (id, title, status, type, priority, promoted_to, ...)
      - readme_content: string content of the backlog's README.md, or None
      - requirements: list of dicts, each with:
          - req: requirement row (id, file_path, origin, stage)
          - tasks: list of dicts, each with:
              - task: task row (id, title, status, flow_type, assigned_to)
              - transitions: list of transition rows (from_status, to_status, triggered_by, created_at)

    Big-O: O(R * T * L) where R = requirements, T = tasks per requirement,
    L = transition log entries per task. Typically small (single-digit R and T).
    NOT on the hot path — called only when user selects a backlog item.
    """
    result: dict = {"backlog": None, "readme_content": None, "requirements": [], "checklists": []}

    # Fetch backlog item
    bk_row = conn.execute(
        "SELECT id, title, status, type, priority, promoted_to, file_path, created_at, updated_at "
        "FROM backlog WHERE id = ?",
        (backlog_id,),
    ).fetchone()
    if not bk_row:
        return result
    result["backlog"] = bk_row

    # Read the backlog item's README.md from the filesystem (#246)
    result["readme_content"] = fetch_backlog_readme(work_dir, bk_row["file_path"])

    promoted_to = bk_row["promoted_to"]
    if not promoted_to:
        return result

    # Fetch requirements whose file_path starts with promoted_to prefix
    req_rows = conn.execute(
        "SELECT id, file_path, origin, stage, created_at "
        "FROM requirements WHERE file_path LIKE ? || '%' "
        "ORDER BY id",
        (promoted_to,),
    ).fetchall()

    for req in req_rows:
        req_entry: dict = {"req": req, "tasks": []}

        # Read requirement README content from filesystem (#249: surface all data)
        req_readme = _read_requirement_readme(work_dir, req["file_path"])
        req_entry["readme_content"] = req_readme

        # Fetch tasks linked to this requirement
        task_rows = conn.execute(
            "SELECT id, title, status, flow_type, assigned_to, "
            "task_file, result_file, created_at, updated_at "
            "FROM tasks WHERE requirement_id = ? ORDER BY id",
            (req["id"],),
        ).fetchall()

        for task in task_rows:
            # Fetch transition log for this task
            transitions = conn.execute(
                "SELECT from_status, to_status, triggered_by, created_at "
                "FROM transition_log "
                "WHERE entity_type = 'task' AND entity_id = ? "
                "ORDER BY created_at",
                (task["id"],),
            ).fetchall()

            # Read task spec file content (#249: surface spec in lineage)
            spec_content = _read_file_safe(task["task_file"])

            # Read result file content (#249: surface result in lineage)
            result_content = _read_file_safe(task["result_file"])

            req_entry["tasks"].append({
                "task": task,
                "transitions": transitions,
                "spec_content": spec_content,
                "result_content": result_content,
            })

        result["requirements"].append(req_entry)

    # Fetch checklists for all tasks in this lineage (#248: surface checklists in lineage view)
    all_checklists: list[dict] = []
    seen_checklist_files: set[str] = set()
    for req_entry in result["requirements"]:
        for task_entry in req_entry.get("tasks", []):
            task = task_entry["task"]
            task_id = task["id"] if hasattr(task, "__getitem__") else task.get("id")
            if task_id:
                for cl in fetch_checklists_for_task(work_dir, task_id, conn):
                    if cl["filename"] not in seen_checklist_files:
                        seen_checklist_files.add(cl["filename"])
                        all_checklists.append(cl)
    result["checklists"] = all_checklists

    return result


def fetch_backlog_readme(work_dir: str, file_path: str | None) -> str | None:
    """Read the README.md content for a backlog item from the filesystem.

    Backlog #246: Show backlog description in lineage view.
    Resolves the README path from the backlog's file_path field:
      {work_dir}/backlog/{file_path}/README.md

    file_path already includes the type prefix (e.g. "requests/foo", "bugs/bar").

    Returns the file content as a string, or None if the file doesn't exist
    or is unreadable. Never raises — graceful degradation for missing files.

    Big-O: O(F) where F = file size. Single filesystem read. NOT on hot path —
    called only when user selects a backlog item for lineage view.
    """
    import os
    if not work_dir or not file_path:
        return None
    readme_path = os.path.join(work_dir, "backlog", file_path, "README.md")
    try:
        with open(readme_path, "r", encoding="utf-8") as f:
            return f.read()
    except (OSError, UnicodeDecodeError):
        return None


def fetch_checklists_for_task(work_dir: str, task_id: int, conn: sqlite3.Connection) -> list[dict]:
    """Read checklist files from .work/checklists/ associated with a task.

    Purpose: Surface checklist content (lead and worker checklists) in the lineage view
        so users can see what was done at each DAG phase.
    Rationale: Checklists follow naming conventions that embed agent names. We find
        agents associated with a task (assigned_to, transition_log agents) and match
        their checklist files.

    Pseudo-logic:
    1. Collect all agent names associated with the task (assigned_to + transition_log)
    2. Scan .work/checklists/ for files matching those agent names
    3. Also check for files matching the task's backlog ID pattern (lead-b{id}*.md, b{id}*.md)
    4. Read each matching file and return list of {filename, content} dicts
    5. Graceful degradation — return empty list if checklists dir doesn't exist

    Big-O: O(A * F) where A = agents associated with task, F = files in checklists/.
    NOT on hot path — called only during lineage view.
    """
    import os
    import re

    if not work_dir:
        return []

    checklists_dir = os.path.join(work_dir, "checklists")
    if not os.path.isdir(checklists_dir):
        return []

    # Collect agent names associated with this task
    agent_names: set[str] = set()
    try:
        # From assigned_to
        row = conn.execute(
            "SELECT assigned_to FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        if row and row["assigned_to"]:
            agent_names.add(row["assigned_to"])

        # From transition_log
        tl_rows = conn.execute(
            "SELECT DISTINCT triggered_by FROM transition_log "
            "WHERE entity_type = 'task' AND entity_id = ? AND triggered_by IS NOT NULL",
            (task_id,),
        ).fetchall()
        for r in tl_rows:
            if r["triggered_by"]:
                agent_names.add(r["triggered_by"])
    except Exception as e:
        logger.error("Failed to collect agent names for task %s: %s: %s", task_id, type(e).__name__, e)

    # Scan checklists directory for matching files
    results: list[dict] = []
    seen_files: set[str] = set()
    try:
        all_files = sorted(os.listdir(checklists_dir))
    except OSError:
        return []

    # --- Pass 1: task-ID-scoped match (preferred) ---
    # Look for files containing "-task-<task_id>" in their name.
    # These are correctly scoped to this specific task session — no bleed from old sessions.
    task_id_pattern = f"-task-{task_id}"
    id_scoped_files: list[str] = [
        f for f in all_files
        if f.endswith(".md") and task_id_pattern in f
    ]

    # --- Pass 2: agent-name substring match (fallback) ---
    # Only used when no task-ID-scoped files exist. This is the legacy behavior and
    # may surface stale checklists from old sessions when agent names repeat across sessions.
    agent_matched_files: list[str] = []
    if not id_scoped_files:
        for fname in all_files:
            if not fname.endswith(".md"):
                continue
            for agent in agent_names:
                if agent in fname:
                    agent_matched_files.append(fname)
                    break

    # Use whichever pass found results
    candidate_files = id_scoped_files if id_scoped_files else agent_matched_files

    def _read_checklist_file(fname: str) -> None:
        if fname in seen_files:
            return
        seen_files.add(fname)
        fpath = os.path.join(checklists_dir, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()
            results.append({"filename": fname, "content": content})
        except (OSError, UnicodeDecodeError) as e:
            logger.error("Failed to read checklist %s: %s: %s", fname, type(e).__name__, e)

    for fname in candidate_files:
        _read_checklist_file(fname)

    return results


def parse_checklists_per_stage(checklists: list[dict]) -> dict[str, list[str]]:
    """Parse checklist markdown content to extract per-stage entries.

    Purpose: Extract what was done at each DAG stage from checklist files.
    Rationale: Checklist files have entries like:
        - [x] **seed** — Read README.md, decided to decompose directly
        - [x] **decomposing** — Created child task 168
    We parse these to build a map of stage_name → list of checklist entries.

    Pseudo-logic:
    1. For each checklist dict (filename, content), scan lines for pattern: - [x/space] **stage** — text
    2. Extract the stage name (bold text) and the description (after the dash)
    3. Build a dict mapping stage_name → [list of entries]
    4. Return the map — empty dict if no matching entries found

    Big-O: O(C * L) where C = checklists, L = lines per checklist. NOT on hot path.
    """
    import re
    stage_map: dict[str, list[str]] = {}
    # Pattern: - [x] **stage_name** — description  (or - [ ] for unchecked)
    pattern = re.compile(r'^-\s+\[(.)\]\s+\*\*([^*]+)\*\*\s*[—\-]\s*(.*)', re.MULTILINE)
    for cl in checklists:
        content = cl.get("content", "")
        for match in pattern.finditer(content):
            checked = match.group(1).strip()
            stage_name = match.group(2).strip()
            description = match.group(3).strip()
            status = "done" if checked.lower() == "x" else "pending"
            entry = {"text": description, "status": status, "source": cl.get("filename", "")}
            if stage_name not in stage_map:
                stage_map[stage_name] = []
            stage_map[stage_name].append(entry)
    return stage_map


def fetch_agent_contexts(conn: sqlite3.Connection, agent_names: set[str]) -> dict[str, str]:
    """Fetch context_summary for a set of agent names.

    Purpose: Surface the agent's context/prompt at the time they worked a stage.
    Rationale: The agents table stores context_summary set via set-context command.
        This gives visibility into what the agent was told/thinking when they worked a phase.

    Pseudo-logic:
    1. Query agents table for all names in the set
    2. Return dict mapping agent_name → context_summary
    3. Skip agents with no context_summary

    Big-O: O(A) where A = number of agents queried. NOT on hot path.
    """
    if not agent_names:
        return {}
    contexts: dict[str, str] = {}
    placeholders = ", ".join("?" for _ in agent_names)
    try:
        rows = conn.execute(
            f"SELECT name, context_summary FROM agents WHERE name IN ({placeholders})",
            list(agent_names),
        ).fetchall()
        for row in rows:
            if row["context_summary"]:
                contexts[row["name"]] = row["context_summary"]
    except sqlite3.DatabaseError as e:
        logger.error("fetch_agent_contexts failed: %s: %s", type(e).__name__, e)
    return contexts


def _read_file_safe(file_path: str | None) -> str | None:
    """Read a file's content safely, returning None on any error.

    Purpose: Generic file reader for surfacing task specs, results, etc.
    Rationale: Multiple places need to read filesystem content for the lineage view.
        Centralize the error handling in one place.

    Big-O: O(F) where F = file size. Single read. NOT on hot path.
    """
    import os
    if not file_path or not os.path.exists(file_path):
        return None
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except (OSError, UnicodeDecodeError):
        return None


def _read_requirement_readme(work_dir: str, req_file_path: str | None) -> str | None:
    """Read a requirement's README.md from its folder path.

    Purpose: Surface requirement README content in lineage view (#249).
    Rationale: Each requirement has a folder under .work/requirements/ with a README.md.

    Big-O: O(F) where F = file size. NOT on hot path.
    """
    import os
    if not work_dir or not req_file_path:
        return None
    readme_path = os.path.join(work_dir, "requirements", req_file_path, "README.md")
    try:
        with open(readme_path, "r", encoding="utf-8") as f:
            return f.read()
    except (OSError, UnicodeDecodeError):
        return None


def fetch_all_backlog(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Fetch ALL backlog items for lineage browser — including closed.

    Returns every backlog item so user can browse full history and view lineage.
    Ordered by most recently updated first, so recent work is at the top.
    """
    try:
        return conn.execute("""
            SELECT id, type, SUBSTR(title, 1, 50) AS title_short, priority, status,
                   promoted_to, updated_at
            FROM backlog
            ORDER BY updated_at DESC, id DESC
        """).fetchall()
    except sqlite3.DatabaseError:
        return []


def fetch_task_to_backlog_map(conn: sqlite3.Connection, task_ids: list[int]) -> dict[int, int]:
    """Map task IDs back to their originating backlog item IDs.

    Chain: task.requirement_id → requirements.id → requirements.file_path
    → backlog.promoted_to (prefix match on file_path).

    Returns {task_id: backlog_id} for tasks that can be traced back.
    Only called when activity rows need click targets — NOT on the hot path.
    """
    if not task_ids:
        return {}
    result: dict[int, int] = {}
    try:
        placeholders = ", ".join("?" for _ in task_ids)
        rows = conn.execute(f"""
            SELECT t.id AS task_id, b.id AS backlog_id
            FROM tasks t
            JOIN requirements r ON t.requirement_id = r.id
            JOIN backlog b ON r.file_path LIKE b.promoted_to || '%'
            WHERE t.id IN ({placeholders})
              AND b.promoted_to IS NOT NULL AND b.promoted_to <> ''
        """, task_ids).fetchall()
        for row in rows:
            result[row["task_id"]] = row["backlog_id"]
    except sqlite3.DatabaseError as e:
        logger.error("Failed to map tasks to backlog: %s", e)
    return result


def fetch_activity(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Recent task status transitions — one per task, most recent only.

    Big-O: O(L * log(L)) where L = transition_log rows for task entities.
    Window function ROW_NUMBER() requires sort. JOIN tasks O(1) per row by PK.
    idx_transition_entity index helps filter. Outer LIMIT 8 caps output.
    Hot path — called every 2s by dashboard loop.
    """
    cursor = conn.execute("""
        SELECT
            task_id,
            title,
            from_status,
            to_status,
            agent,
            timestamp
        FROM (
            SELECT
                tl.entity_id   AS task_id,
                SUBSTR(t.title, 1, 25)  AS title,
                tl.from_status,
                tl.to_status,
                tl.triggered_by AS agent,
                tl.created_at   AS timestamp,
                ROW_NUMBER() OVER (
                    PARTITION BY tl.entity_id
                    ORDER BY tl.created_at DESC
                ) AS rn
            FROM transition_log tl
            JOIN tasks t ON t.id = tl.entity_id
            WHERE tl.entity_type = 'task'
        )
        WHERE rn = 1
        ORDER BY timestamp DESC
        LIMIT 8
    """)
    return cursor.fetchall()
