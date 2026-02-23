"""Multi-agent coordination smoke test.

Exercises the full task DAG with two agents and blocked_by dependencies:
  1. Register lead + coder agents
  2. Create task 1 (unblocked) and task 2 (blocked by task 1)
  3. Coder pulls task 1, submits result, lead closes it
  4. Verify task 2 becomes unblocked (pullable)
  5. Coder 2 pulls task 2, submits result, lead closes it
  6. Verify both tasks closed
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from minion.db import init_db, register_agent_db, reset_db_path


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Each test gets its own .work/ tree and isolated DB."""
    work_dir = tmp_path / ".work"
    work_dir.mkdir(parents=True, exist_ok=True)

    db_path = str(work_dir / "minion.db")
    monkeypatch.setenv("MINION_DB_PATH", db_path)
    reset_db_path()
    init_db()

    monkeypatch.chdir(tmp_path)
    yield tmp_path

    reset_db_path()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _insert_battle_plan(db_path: str, agent_name: str) -> None:
    """Insert an active battle plan row directly — avoids filesystem path issues."""
    from minion.db import now_iso

    now = now_iso()
    work_dir = Path(db_path).parent
    plan_dir = work_dir / "battle-plans"
    plan_dir.mkdir(parents=True, exist_ok=True)
    plan_file = str(plan_dir / "plan.md")
    Path(plan_file).write_text("# Test Plan\n")

    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO battle_plan (set_by, plan_file, status, created_at, updated_at) "
        "VALUES (?, ?, 'active', ?, ?)",
        (agent_name, plan_file, now, now),
    )
    conn.commit()
    conn.close()


def _task_status(db_path: str, task_id: int) -> str:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT status FROM tasks WHERE id = ?", (task_id,)).fetchone()
    conn.close()
    return row["status"]


def _set_result_file(db_path: str, task_id: int, result_file: str) -> None:
    """Stamp a result_file on a task row — close_task requires this."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        "UPDATE tasks SET result_file = ? WHERE id = ?", (result_file, task_id)
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Smoke test
# ---------------------------------------------------------------------------


def test_multi_agent_coordination(isolated_db):
    """Two agents, two tasks with a dependency — full pull/close lifecycle."""
    tmp_path = isolated_db
    db_path = str(tmp_path / ".work" / "minion.db")

    # -- 1. Register agents and seed battle plan --------------------------
    register_agent_db("lead", "lead")
    register_agent_db("coder-1", "coder")
    register_agent_db("coder-2", "coder")
    _insert_battle_plan(db_path, "lead")

    # Create dummy task files — create_task checks os.path.exists()
    task_dir = tmp_path / ".work" / "tasks"
    task_dir.mkdir(parents=True, exist_ok=True)
    task_file_1 = task_dir / "task-1.md"
    task_file_2 = task_dir / "task-2.md"
    task_file_1.write_text("# Task 1\nFirst task.\n")
    task_file_2.write_text("# Task 2\nSecond task, depends on task 1.\n")

    # -- 2. Create tasks — task 2 blocked by task 1 ----------------------
    from minion.tasks.create_task import create_task

    r1 = create_task(
        agent_name="lead",
        title="Setup infrastructure",
        task_file=str(task_file_1),
        task_type="feature",
    )
    assert "error" not in r1, f"create_task 1 failed: {r1}"
    task1_id = r1["task_id"]

    r2 = create_task(
        agent_name="lead",
        title="Build on infrastructure",
        task_file=str(task_file_2),
        task_type="feature",
        blocked_by=str(task1_id),
    )
    assert "error" not in r2, f"create_task 2 failed: {r2}"
    task2_id = r2["task_id"]

    # Both tasks start as 'open'
    assert _task_status(db_path, task1_id) == "open"
    assert _task_status(db_path, task2_id) == "open"

    # -- 3. Verify task 2 is blocked — pull should fail -------------------
    from minion.tasks.pull_task import pull_task

    blocked_pull = pull_task("coder-2", task2_id)
    assert "error" in blocked_pull, "Task 2 should be blocked"
    assert "unresolved blockers" in blocked_pull["error"].lower()

    # -- 4. Agent 1 pulls task 1 and completes it -------------------------
    pull1 = pull_task("coder-1", task1_id)
    assert "error" not in pull1, f"pull_task 1 failed: {pull1}"
    assert _task_status(db_path, task1_id) == "assigned"

    # Stamp a result file so close_task will accept it
    result_file = task_dir / "result-1.md"
    result_file.write_text("# Result\nDone.\n")
    _set_result_file(db_path, task1_id, str(result_file))

    from minion.tasks.close_task import close_task

    close1 = close_task("lead", task1_id)
    assert "error" not in close1, f"close_task 1 failed: {close1}"
    assert _task_status(db_path, task1_id) == "closed"

    # -- 5. Task 2 should now be unblocked — coder-2 can pull it ----------
    pull2 = pull_task("coder-2", task2_id)
    assert "error" not in pull2, f"pull_task 2 failed (should be unblocked): {pull2}"
    assert _task_status(db_path, task2_id) == "assigned"

    # -- 6. Agent 2 completes task 2 --------------------------------------
    result_file_2 = task_dir / "result-2.md"
    result_file_2.write_text("# Result\nAlso done.\n")
    _set_result_file(db_path, task2_id, str(result_file_2))

    close2 = close_task("lead", task2_id)
    assert "error" not in close2, f"close_task 2 failed: {close2}"
    assert _task_status(db_path, task2_id) == "closed"

    # -- 7. Final verification — both tasks closed ------------------------
    for tid in (task1_id, task2_id):
        assert _task_status(db_path, tid) == "closed", (
            f"Task #{tid} not closed — status: '{_task_status(db_path, tid)}'"
        )

    # Verify transition history exists for both tasks
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    for tid in (task1_id, task2_id):
        rows = conn.execute(
            "SELECT * FROM transition_log WHERE entity_id = ? AND entity_type = 'task'",
            (tid,),
        ).fetchall()
        assert len(rows) >= 2, (
            f"Task #{tid} should have at least 2 transitions (open→assigned, *→closed), got {len(rows)}"
        )
    conn.close()
