"""Poll loop — replaces poll.sh with first-class Python.
Returns actionable content (messages + available tasks) in one response.
Exit codes (minion-swarm contract):
  0 — content delivered (messages and/or tasks)
  1 — timeout reached
  3 — stand_down/retire signal detected

Purpose: Poll loop — replaces poll.sh with first-class Python.
Rationale: Extracted into own module following single-responsibility principle.
Responsibility: Poll loop — replaces poll.sh with first-class Python. NOT responsible for unrelated concerns.
Organization: Standalone functions and/or a single class. See source."""

from __future__ import annotations

import os
import time
from typing import Any

from minion.auth import CAP_REVIEW, classes_with
from minion.db import get_db, now_iso, touch_coordinator_activity
from minion.defaults import MAX_DOC_SIZE

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
    except OSError:
        pass


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
        except OSError:
            pass


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

        # P3: fixed tasks for reviewers
        if not candidates and agent_class in _reviewers:
            cursor.execute(
                """SELECT id, title, task_file, status, class_required, blocked_by, flow_type
                   FROM tasks WHERE status = 'fixed' AND assigned_to IS NULL
                   ORDER BY created_at ASC LIMIT 10"""
            )
            candidates.extend(dict(r) for r in cursor.fetchall())

        # P4: verified tasks for testers
        if not candidates and agent_class in _reviewers:
            cursor.execute(
                """SELECT id, title, task_file, status, class_required, blocked_by, flow_type
                   FROM tasks WHERE status = 'verified' AND assigned_to IS NULL
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
            except (ImportError, KeyError, ValueError):
                pass
            # Render DAG so agent sees where they are in the flow
            task_type = task.get("flow_type") or "bugfix"
            dag_str = ""
            try:
                from minion.tasks import load_flow
                flow = load_flow(task_type)
                dag_str = flow.render_dag(task["status"])
            except (ImportError, FileNotFoundError, KeyError, ValueError):
                pass
            # Suggest relevant docs for this task
            suggested_docs: list[str] = []
            try:
                from minion.intel import suggest as _suggest
                s = _suggest(topic=task["title"], limit=3)
                suggested_docs = [d["doc_path"] for d in s.get("docs", []) if d.get("score", 0) > 0]
            except (ImportError, KeyError, TypeError):
                pass
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
    """Check stand_down / retire. Returns signal name or None."""
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
    # Heartbeat every ~30 min so idle agents don't get pruned by the 6-hour rule
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
        except (ImportError, OSError, KeyError, ValueError):
            pass

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
