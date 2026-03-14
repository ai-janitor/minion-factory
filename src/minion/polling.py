"""Poll loop — replaces poll.sh with first-class Python.
Returns actionable content (messages + available tasks) in one response.
Exit codes (minion-swarm contract):
  0 — content delivered (messages and/or tasks)
  1 — timeout reached
  3 — stand_down/retire signal detected

Purpose: Poll loop — replaces poll.sh with first-class Python.
Rationale: Extracted into own module following single-responsibility principle.
Responsibility: Poll loop — replaces poll.sh with first-class Python. NOT responsible for unrelated concerns.
Organization: Standalone functions and/or a single class. See source.

ASSUMPTIONS:
- Only ONE poll process per agent per project. _kill_existing_poll() enforces this
  via PID files, but relies on SIGTERM being deliverable. If a poll process is
  zombied or in uninterruptible sleep, the new poll may fail to take over.
- Orphan detection uses os.getppid() — if the parent PID changes, poll exits.
  This assumes the parent process is the daemon/terminal that spawned us. On Linux
  with PR_SET_PDEATHSIG this is reliable; on macOS it's best-effort (reparenting
  to launchd/PID 1 is the signal, but there's a small race window).
- _fetch_messages() does ALL reads before ALL writes within a single connection to
  maintain WAL snapshot isolation. Interleaving reads and writes would cause messages
  to be marked read but not returned in the same transaction.
- seen_task_ids prevents re-surfacing tasks that were already shown to the agent in
  this poll session. This set lives in memory — if the poll process restarts, all
  tasks appear as "new" again. This is intentional (restart = fresh view).
- The 5-second default poll interval means message delivery latency is 0-5 seconds.
  Reducing the interval below 1 second risks SQLite lock contention under multi-agent
  load. The interval is not configurable at runtime via the DB — only via CLI flag.
- Exit code 3 is a CONTRACT with the daemon runner (daemon/runner/_state.py). The
  daemon uses exit code 3 to distinguish "agent dismissed" from "poll crashed" (exit 1).
  Changing these exit codes breaks daemon lifecycle management.
"""

from __future__ import annotations

import logging
import os
import ssl
import time
from typing import Any

logger = logging.getLogger(__name__)

from minion.auth import CAP_REVIEW, classes_with
from minion.db import get_db, now_iso, touch_coordinator_activity
from minion.defaults import MAX_DOC_SIZE

logger = logging.getLogger(__name__)

_reviewers = classes_with(CAP_REVIEW)


def _poll_pidfile(agent: str) -> str:
    """Path to the PID file for an agent's poll process."""
    from minion.db import get_runtime_dir
    return os.path.join(get_runtime_dir(), ".minion-poll", f"{agent}.pid")


def _write_pidfile(agent: str) -> None:
    pidfile = _poll_pidfile(agent)
    os.makedirs(os.path.dirname(pidfile), exist_ok=True)
    with open(pidfile, "w") as f:
        f.write(str(os.getpid()))


def _remove_pidfile(agent: str) -> None:
    try:
        os.remove(_poll_pidfile(agent))
    except OSError as e:
        logger.error("Failed to remove pidfile for %s: %s", agent, e)


def _kill_existing_poll(agent: str) -> int | None:
    """Kill any existing poll for this agent. Returns killed PID or None."""
    import signal as _sig
    pidfile = _poll_pidfile(agent)
    if not os.path.exists(pidfile):
        return None
    try:
        with open(pidfile) as f:
            old_pid = int(f.read().strip())
        if old_pid == os.getpid():
            return None
        os.kill(old_pid, 0)  # check alive
        os.kill(old_pid, _sig.SIGTERM)
        return old_pid
    except (ValueError, ProcessLookupError, PermissionError):
        return None
    finally:
        try:
            os.remove(pidfile)
        except OSError as e:
            logger.error("Failed to remove stale pidfile %s: %s", pidfile, e)


def is_poll_alive(agent: str, project_path: str) -> bool:
    """Check if a poll process is running for an agent in a given project."""
    pidfile = os.path.join(project_path, ".work", ".minion-poll", f"{agent}.pid")
    if not os.path.exists(pidfile):
        return False
    try:
        with open(pidfile) as f:
            pid = int(f.read().strip())
        os.kill(pid, 0)  # signal 0 = check if alive
        return True
    except (ValueError, ProcessLookupError, PermissionError, OSError):
        return False


def _fetch_messages(agent: str) -> list[dict[str, Any]]:
    """Fetch and mark-read all unread messages (direct + broadcast). Same as check-inbox.

    Time complexity: O(M + B) where M = unread direct messages, B = unread broadcasts.
    Sorting: O((M+B) * log(M+B)).
    File I/O: O(M+B) content file reads.
    """
    conn = get_db()
    cursor = conn.cursor()
    now = now_iso()
    try:
        # ALL reads before writes — WAL snapshot isolation race (see comms.check_inbox)
        cursor.execute(
            "SELECT * FROM messages WHERE to_agent = ? AND read_flag = 0", (agent,),
        )
        direct = [dict(r) for r in cursor.fetchall()]

        cursor.execute(
            """SELECT * FROM messages WHERE to_agent = 'all'
               AND id NOT IN (SELECT message_id FROM broadcast_reads WHERE agent_name = ?)""",
            (agent,),
        )
        broadcasts = [dict(r) for r in cursor.fetchall()]

        # --- Writes ---
        cursor.execute(
            "UPDATE agents SET last_seen = ?, last_inbox_check = ? WHERE name = ?",
            (now, now, agent),
        )
        if direct:
            ids = [m["id"] for m in direct]
            cursor.execute(
                f"UPDATE messages SET read_flag = 1 WHERE id IN ({','.join('?' * len(ids))})", ids,
            )
        for msg in broadcasts:
            cursor.execute(
                "INSERT OR IGNORE INTO broadcast_reads (agent_name, message_id) VALUES (?, ?)",
                (agent, msg["id"]),
            )

        conn.commit()

        all_msgs = direct + broadcasts
        all_msgs.sort(key=lambda x: x.get("timestamp", ""))

        # Inline content from files
        for msg in all_msgs:
            cf = msg.get("content_file")
            if cf and os.path.exists(cf):
                if os.path.getsize(cf) > MAX_DOC_SIZE:
                    msg["content"] = f"(content file too large: {cf})"
                else:
                    with open(cf) as f:
                        msg["content"] = f.read()
            else:
                msg["content"] = ""
            if msg.get("is_cc"):
                msg["cc_note"] = f"[CC] originally to: {msg.get('cc_original_to', 'unknown')}"

        return all_msgs
    finally:
        conn.close()


def _find_available_tasks(agent: str) -> list[dict[str, Any]]:
    """Find claimable tasks for this agent without claiming them.

    Time complexity: O(T * B) where T = candidate tasks (max 10 per priority tier),
    B = average blocked_by list length per task. For each candidate, checks blocker
    status (O(B) query) and DAG eligibility (O(1) lookup). Total bounded by
    O(40 * B) due to LIMIT 10 on each of 4 priority tiers.
    """
    from minion.flow_bridge import active_statuses

    conn = get_db()
    cursor = conn.cursor()
    try:
        # moon_crash blocks
        cursor.execute("SELECT value FROM flags WHERE key = 'moon_crash'")
        mc = cursor.fetchone()
        if mc and mc["value"] == "1":
            return []

        cursor.execute("SELECT agent_class FROM agents WHERE name = ?", (agent,))
        row = cursor.fetchone()
        if not row:
            return []
        agent_class = row["agent_class"]

        candidates: list[dict[str, Any]] = []

        # P1: already assigned to agent
        actives = active_statuses()
        cursor.execute(
            """SELECT id, title, task_file, status, class_required, blocked_by, flow_type
               FROM tasks WHERE assigned_to = ? AND status IN ({})
               ORDER BY created_at ASC LIMIT 10""".format(
                ",".join("?" for _ in actives)
            ),
            (agent, *actives),
        )
        candidates.extend(dict(r) for r in cursor.fetchall())

        # P2: open tasks matching class
        if not candidates:
            cursor.execute(
                """SELECT id, title, task_file, status, class_required, blocked_by, flow_type
                   FROM tasks WHERE status = 'open' AND class_required = ? AND assigned_to IS NULL
                   ORDER BY created_at ASC LIMIT 10""",
                (agent_class,),
            )
            candidates.extend(dict(r) for r in cursor.fetchall())

        # P3: fixed/findings_ready tasks for reviewers
        if not candidates and agent_class in _reviewers:
            cursor.execute(
                """SELECT id, title, task_file, status, class_required, blocked_by, flow_type
                   FROM tasks WHERE status IN ('fixed', 'findings_ready') AND assigned_to IS NULL
                   ORDER BY created_at ASC LIMIT 10"""
            )
            candidates.extend(dict(r) for r in cursor.fetchall())

        # P4: verified/assessed tasks for testers
        if not candidates and agent_class in _reviewers:
            cursor.execute(
                """SELECT id, title, task_file, status, class_required, blocked_by, flow_type
                   FROM tasks WHERE status IN ('verified', 'assessed') AND assigned_to IS NULL
                   ORDER BY created_at ASC LIMIT 10"""
            )
            candidates.extend(dict(r) for r in cursor.fetchall())

        # Filter blocked + filter tasks agent's class cannot advance
        result = []
        for task in candidates:
            blocked_by = task.get("blocked_by")
            if blocked_by:
                blocker_ids = [int(x.strip()) for x in blocked_by.split(",") if x.strip()]
                placeholders = ",".join("?" for _ in blocker_ids)
                cursor.execute(
                    f"SELECT COUNT(*) FROM tasks WHERE id IN ({placeholders}) AND status != 'closed'",
                    blocker_ids,
                )
                if cursor.fetchone()[0] > 0:
                    continue
            # Skip tasks whose current DAG stage needs a different class
            try:
                from minion.flow_bridge import workers_for as _workers_for
                eligible = _workers_for(task["status"], task.get("class_required") or "", task.get("flow_type") or "bugfix")
                if eligible is not None and agent_class not in eligible:
                    continue
            except (ImportError, KeyError, ValueError) as e:
                logger.error("Failed to check DAG eligibility for task %s: %s", task.get("id"), e)
                continue
            # Render DAG so agent sees where they are in the flow
            task_type = task.get("flow_type") or "bugfix"
            dag_str = ""
            try:
                from minion.tasks import load_flow
                flow = load_flow(task_type)
                dag_str = flow.render_dag(task["status"])
            except (ImportError, FileNotFoundError, KeyError, ValueError) as e:
                logger.error("Failed to render DAG for task %s (flow=%s): %s", task.get("id"), task_type, e)
                # Per GLOBAL-152: explicit error state — agent must see the failure, not receive empty dag.
                # Do NOT re-raise (task still returned) but mark dag as unavailable so agent has visibility.
                dag_str = f"(DAG unavailable — render failed: check flow YAML for '{task_type}')"
            # Suggest relevant docs for this task
            suggested_docs: list[str] = []
            try:
                from minion.intel import suggest as _suggest
                s = _suggest(topic=task["title"], limit=3)
                suggested_docs = [d["doc_path"] for d in s.get("docs", []) if d.get("score", 0) > 0]
            except (ImportError, KeyError, TypeError) as e:
                logger.error("Failed to suggest intel docs for task %s: %s", task.get("id"), e)
            entry: dict[str, object] = {
                "task_id": task["id"],
                "title": task["title"],
                "status": task["status"],
                "task_file": task["task_file"],
                "claim_cmd": f"minion pull-task --agent {agent} --task-id {task['id']}",
                "dag": dag_str,
            }
            if suggested_docs:
                entry["suggested_reading"] = suggested_docs
            result.append(entry)
        return result
    finally:
        conn.close()


def _check_signals(agent: str) -> str | None:
    """Check stand_down / retire. Returns signal name or None.

    Big-O: O(1) — three PK/indexed lookups (flags, agent_retire, agent_interrupt).
    Called every poll iteration (every 5s by default).
    """
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT value FROM flags WHERE key = 'stand_down'")
        row = cur.fetchone()
        if row and row[0] == "1":
            return "stand_down"
        cur.execute("SELECT agent_name FROM agent_retire WHERE agent_name = ?", (agent,))
        if cur.fetchone():
            return "retire"
        cur.execute("SELECT agent_name FROM agent_interrupt WHERE agent_name = ?", (agent,))
        if cur.fetchone():
            return "interrupt"
        return None
    finally:
        conn.close()


def poll_loop(agent: str, interval: int = 5, timeout: int = 0) -> dict[str, Any]:
    """Block until messages/tasks arrive, then return them.

    Returns dict with:
      - exit_code: 0 (content), 1 (timeout), 3 (signal)
      - messages: list of message dicts (if any)
      - tasks: list of available task dicts (if any)
      - signal: "stand_down" or "retire" (if exit_code 3)
      - transport_hint: restart reminder for terminal agents

    Big-O: O(timeout/interval) iterations. Per iteration: O(1) signal check +
    O(1) message count + O(T*B) task finding (see _find_available_tasks).
    On content delivery: O(M+B) message fetch + sort. PID management O(1).
    """
    # Precondition assertions — backlog #63
    assert agent, "agent name must not be empty"
    assert interval > 0, f"interval must be positive, got {interval}"
    assert timeout >= 0, f"timeout must be non-negative, got {timeout}"

    # Single instance: kill any existing poll for this agent
    _kill_existing_poll(agent)
    _write_pidfile(agent)

    elapsed = 0
    parent_pid = os.getppid()

    try:
        return _poll_inner(agent, interval, timeout, parent_pid)
    finally:
        _remove_pidfile(agent)


def _poll_inner(agent: str, interval: int, timeout: int, parent_pid: int) -> dict[str, Any]:
    """Inner poll loop — checks signals, messages, and tasks each iteration.

    Time complexity per iteration: O(M + B + T*B) where M = message count query (O(1)),
    B = broadcast count query (O(1) with subquery), T*B = task finding (see _find_available_tasks).
    Loop runs at most timeout/interval iterations. Each iteration is O(T*B) dominated.
    The seen_task_ids set prevents re-surfacing tasks: O(1) membership check per task.
    """
    elapsed = 0
    seen_task_ids: set[int] = set()
    # ASSUMPTION: Heartbeat every 30 min keeps agents alive vs the 6-hour prune threshold.
    # If prune threshold changes, adjust this proportionally (e.g., 1/12 of prune window).
    _HEARTBEAT_INTERVAL = 1800  # seconds
    _last_heartbeat = 0

    # Immediate heartbeat on poll start — coordinator knows agent is alive now
    touch_coordinator_activity(agent)

    while True:
        # Orphan detection: parent died → exit cleanly
        if os.getppid() != parent_pid:
            return {"exit_code": 1}

        # Check signals first
        signal = _check_signals(agent)
        if signal:
            return {
                "exit_code": 3,
                "signal": signal,
                "action": "Do NOT restart polling. The party has been dismissed."
                if signal == "stand_down"
                else "Do NOT restart polling. You have been retired from the party.",
            }

        # Check for messages (peek — don't consume yet)
        conn = get_db()
        try:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM messages WHERE to_agent = ? AND read_flag = 0", (agent,))
            direct = cur.fetchone()[0]
            cur.execute(
                """SELECT COUNT(*) FROM messages
                   WHERE to_agent = 'all' AND from_agent != ?
                   AND id NOT IN (SELECT message_id FROM broadcast_reads WHERE agent_name = ?)""",
                (agent, agent),
            )
            broadcast = cur.fetchone()[0]
            has_messages = (direct + broadcast) > 0

            # Get transport
            cur.execute("SELECT transport FROM agents WHERE name = ?", (agent,))
            row = cur.fetchone()
            transport = row["transport"] if row else "terminal"
        finally:
            conn.close()

        # Check API GLOBAL network tier for messages + drain outbox
        # Exception handling rationale:
        #   - ImportError: network client not installed — debug only, not an error
        #   - Network-specific (ssl.SSLError, ConnectionResetError, ConnectionRefusedError,
        #     TimeoutError, OSError): expected transient failures — log error and continue
        #   - Unexpected exceptions (KeyError, ValueError, AttributeError, etc.) propagate
        #     so they surface instead of silently dropping cross-project messages
        network_messages: list[dict[str, Any]] = []
        try:
            from minion.network.client import get_client
            net = get_client()
            if net.configured:
                net_inbox = net.check_inbox(agent)
                for msg in net_inbox.get("messages", []):
                    network_messages.append({
                        "from_agent": msg.get("from_agent", "unknown"),
                        "to_agent": agent,
                        "content": msg.get("content", ""),
                        "timestamp": msg.get("timestamp", ""),
                        "source": "network",
                    })
                # Drain offline outbox
                from minion.network.outbox import drain_outbox
                drain_outbox(net)
        except ImportError:
            # Network client not available — not an error, just skip
            logger.debug("Network client not available — skipping network tier poll")
        except (ssl.SSLError, ConnectionResetError, ConnectionRefusedError, TimeoutError, OSError) as e:
            # Transient network failures — log and continue; agent will retry next poll cycle
            logger.error("Network tier poll failed: %s", e)

        # Find available tasks — only surface NEW ones not yet seen this poll session
        available_tasks = _find_available_tasks(agent)
        new_tasks = [t for t in available_tasks if t["task_id"] not in seen_task_ids]

        if has_messages or new_tasks or network_messages:
            # Consume local messages
            messages = _fetch_messages(agent) if has_messages else []
            # Append network messages
            messages.extend(network_messages)

            result: dict[str, Any] = {"exit_code": 0}
            if messages:
                result["messages"] = messages
            if new_tasks:
                result["tasks"] = new_tasks
                seen_task_ids.update(t["task_id"] for t in new_tasks)
            if transport == "terminal":
                result["transport_hint"] = (
                    f"RESTART POLLING: Run `minion poll --agent {agent}` in the FOREGROUND. "
                    f"Do NOT add --timeout. It blocks until the next message arrives. "
                    f"Tuck to terminal background if needed — do NOT launch as a background task."
                )
            touch_coordinator_activity(agent)
            return result

        # Track current tasks as seen so they don't trigger on next iteration
        seen_task_ids.update(t["task_id"] for t in available_tasks)

        time.sleep(interval)
        elapsed += interval

        # Periodic heartbeat — keep agent alive in coordinator even when idle
        if elapsed - _last_heartbeat >= _HEARTBEAT_INTERVAL:
            _last_heartbeat = elapsed
            touch_coordinator_activity(agent)

        if timeout > 0 and elapsed >= timeout:
            return {"exit_code": 1}


def multi_project_poll(agent_name: str, project_paths: list[str] | None = None) -> dict[str, Any]:
    """Poll for messages and tasks across multiple projects.

    SU-19: Cross-project coordination — iterates project DBs and aggregates results.

    Step 1: Discover project paths from args, MINION_PROJECTS env var, or coordinator DB.
    Step 2: For each project, check for unread messages and available tasks.
    Step 3: Return aggregated results.

    Time complexity: O(P * (M + T)) where P = projects, M = messages per project,
    T = tasks per project. Each project requires one DB connection open + close.
    """
    import sqlite3

    from minion.db import connect
    from minion.defaults import get_project_paths

    # Step 1: Discover project paths
    if not project_paths:
        project_paths = get_project_paths()
    if not project_paths:
        # Fallback: query coordinator DB for known project paths
        try:
            from minion.db import get_coordinator_db
            coord = get_coordinator_db()
            try:
                rows = coord.execute("SELECT DISTINCT project_path FROM agents").fetchall()
                project_paths = [r[0] for r in rows if r[0] and r[0] != "unknown"]
            finally:
                coord.close()
        except (sqlite3.OperationalError, sqlite3.DatabaseError, OSError) as e:
            logger.error("Failed to query coordinator DB for project paths: %s", e)

    if not project_paths:
        # No projects discovered — fall back to single-project poll
        return {"projects": [], "note": "No project paths discovered. Use MINION_PROJECTS env var or coordinator DB."}

    # Step 2: Poll each project
    projects_result = []
    for path in project_paths:
        if not os.path.isdir(path):
            continue
        db_path = os.path.join(path, ".work", "minion.db")
        if not os.path.exists(db_path):
            continue
        proj_data: dict[str, Any] = {"path": path, "messages": [], "tasks": []}
        try:
            conn = connect(db_path, timeout=2)
            conn.row_factory = sqlite3.Row
            # Unread messages for this agent
            rows = conn.execute(
                "SELECT id, from_agent, content, timestamp FROM messages "
                "WHERE to_agent = ? AND read_flag = 0 ORDER BY timestamp ASC",
                (agent_name,),
            ).fetchall()
            proj_data["messages"] = [dict(r) for r in rows]

            # Available tasks (open + assigned to this agent)
            rows = conn.execute(
                "SELECT id, title, status, flow_type FROM tasks "
                "WHERE (assigned_to = ? AND status IN ('assigned', 'in_progress')) "
                "   OR (status = 'open' AND assigned_to IS NULL) "
                "ORDER BY created_at ASC LIMIT 20",
                (agent_name,),
            ).fetchall()
            proj_data["tasks"] = [dict(r) for r in rows]
            conn.close()
        except (sqlite3.OperationalError, sqlite3.DatabaseError, OSError):
            proj_data["error"] = "DB unavailable"

        projects_result.append(proj_data)

    # Step 3: Aggregate
    return {"projects": projects_result}


def poll_status(agent_name: str) -> dict[str, Any]:
    """Diagnostic: report poll health for an agent.

    SU-06: Check PID file, PID alive, last poll heartbeat, hook installed.
    Returns a dict with health status fields.
    """
    import json
    from pathlib import Path

    assert agent_name, "agent_name must not be empty"

    result: dict[str, Any] = {"agent": agent_name}

    # 1. Check PID file
    pidfile = _poll_pidfile(agent_name)
    result["pid_file_exists"] = os.path.exists(pidfile)
    result["pid_alive"] = False
    result["pid_value"] = None

    if result["pid_file_exists"]:
        try:
            with open(pidfile) as f:
                pid = int(f.read().strip())
            result["pid_value"] = pid
            os.kill(pid, 0)  # signal 0 = check alive
            result["pid_alive"] = True
        except (ValueError, ProcessLookupError, PermissionError, OSError) as e:
            logger.error("Failed to check poll PID for %s: %s", agent_name, e)

    # 2. Check last heartbeat from coordinator DB
    try:
        conn = get_db()
        try:
            row = conn.execute(
                "SELECT last_seen FROM agents WHERE name = ?", (agent_name,)
            ).fetchone()
            if row and row["last_seen"]:
                result["last_heartbeat"] = row["last_seen"]
                import datetime
                try:
                    last = datetime.datetime.fromisoformat(row["last_seen"])
                    now = datetime.datetime.now(datetime.timezone.utc)
                    if last.tzinfo is None:
                        last = last.replace(tzinfo=datetime.timezone.utc)
                    delta = (now - last).total_seconds()
                    result["seconds_since_heartbeat"] = int(delta)
                    # ASSUMPTION: 5-minute stale threshold for poll heartbeat
                    result["stale"] = delta > 300
                except (ValueError, TypeError):
                    result["stale"] = True
            else:
                result["last_heartbeat"] = None
                result["stale"] = True
        finally:
            conn.close()
    except (OSError, Exception):
        result["last_heartbeat"] = None
        result["stale"] = True

    # 3. Check Stop hook installed
    settings_path = Path.home() / ".claude" / "settings.json"
    result["hook_installed"] = False
    if settings_path.exists():
        try:
            settings = json.loads(settings_path.read_text())
            stop_hooks = settings.get("hooks", {}).get("Stop", [])
            result["hook_installed"] = any(
                "poll-on-stop" in str(h.get("command", ""))
                for h in stop_hooks
                if isinstance(h, dict)
            )
        except (json.JSONDecodeError, OSError) as e:
            logger.error("Failed to check Stop hook settings for %s: %s", agent_name, e)

    return result
