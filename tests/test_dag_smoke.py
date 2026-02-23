"""End-to-end DAG smoke test — walks a requirement seed to completed.

Exercises the full integration path:
  1. Register a lead agent
  2. Create a requirement via the Python API
  3. Advance to decomposing (skip shortcut)
  4. Write a spec YAML and call decompose()
  5. Verify children created, tasks linked
  6. Walk each child task through: pull → result → review → test → done
  7. Advance parent requirement to completed
  8. Assert final state: all tasks closed, requirement completed
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
import yaml

from minion.db import init_db, register_agent_db, reset_db_path


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Each test gets its own .work/ tree and isolated DB."""
    work_dir = tmp_path / ".work"
    work_dir.mkdir(parents=True, exist_ok=True)
    req_dir = work_dir / "requirements"
    req_dir.mkdir(parents=True, exist_ok=True)

    db_path = str(work_dir / "minion.db")
    monkeypatch.setenv("MINION_DB_PATH", db_path)
    reset_db_path()
    init_db()

    # cwd must be tmp_path so relative path resolution in minion.defaults works
    monkeypatch.chdir(tmp_path)
    yield tmp_path

    reset_db_path()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------



def _insert_battle_plan(db_path: str, agent_name: str, plan_text: str = "# Plan\n") -> None:
    """Insert an active battle plan row directly.

    warroom.set_battle_plan() writes to fs.BATTLE_PLAN_DIR which is computed
    at import time from RUNTIME_DIR (the real cwd), not tmp_path. Direct DB
    insertion avoids that path contamination.
    """
    from minion.db import now_iso
    now = now_iso()
    # Write plan file inside tmp .work/ so path is resolvable but isolated
    work_dir = Path(db_path).parent
    plan_dir = work_dir / "battle-plans"
    plan_dir.mkdir(parents=True, exist_ok=True)
    plan_file = str(plan_dir / "plan.md")
    Path(plan_file).write_text(plan_text)

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


def _req_stage(db_path: str, file_path: str) -> str:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT stage FROM requirements WHERE file_path = ?", (file_path,)
    ).fetchone()
    conn.close()
    return row["stage"]


# ---------------------------------------------------------------------------
# Smoke test
# ---------------------------------------------------------------------------


def test_dag_smoke(isolated_db):
    """Walk a single requirement from seed through decomposition to completed."""
    tmp_path = isolated_db
    db_path = str(tmp_path / ".work" / "minion.db")

    # -----------------------------------------------------------------------
    # 1. Register lead agent and set active battle plan
    # -----------------------------------------------------------------------
    lead = "lead-smoke"
    register_agent_db(lead, "lead")
    _insert_battle_plan(db_path, lead, plan_text="# Smoke-test plan\n")

    # Register extra agents needed for review (oracle) and test (builder)
    register_agent_db("oracle-1", "oracle")
    register_agent_db("builder-1", "builder")

    # -----------------------------------------------------------------------
    # 2. Create parent requirement
    # -----------------------------------------------------------------------
    from minion.requirements.crud import create, update_stage

    parent_path = "features/smoke-parent"
    create_result = create(
        file_path=parent_path,
        title="Smoke Parent",
        description="Integration smoke test parent requirement.",
        created_by=lead,
    )
    assert "error" not in create_result, f"create() failed: {create_result}"
    assert create_result["stage"] == "seed"

    # -----------------------------------------------------------------------
    # 3. Advance to decomposing (alt_next skip shortcut from seed)
    # -----------------------------------------------------------------------
    adv = update_stage(parent_path, "decomposing")
    assert "error" not in adv, f"update_stage(decomposing) failed: {adv}"
    assert adv["to_stage"] == "decomposing"

    # -----------------------------------------------------------------------
    # 4. Write a decomposition spec and call decompose()
    # -----------------------------------------------------------------------
    from minion.requirements.decompose import decompose

    spec = {
        "children": [
            {
                "slug": "impl-alpha",
                "title": "Implement Alpha",
                "description": "Alpha implementation task.",
                "task_type": "bugfix",
            },
            {
                "slug": "impl-beta",
                "title": "Implement Beta",
                "description": "Beta implementation task.",
                "task_type": "bugfix",
            },
        ]
    }

    decomp_result = decompose(parent_path, spec, agent_name=lead)
    assert "error" not in decomp_result, f"decompose() failed: {decomp_result}"
    assert decomp_result["status"] == "decomposed"
    assert decomp_result["children_created"] == 2
    assert decomp_result["tasks_created"] == 2

    # -----------------------------------------------------------------------
    # 5. Verify children created and tasks linked
    # -----------------------------------------------------------------------
    children = decomp_result["children"]
    assert len(children) == 2

    child_paths = [c["path"] for c in children]
    task_ids = [c["task_id"] for c in children]

    # Each child folder must exist on disk
    req_root = tmp_path / ".work" / "requirements"
    for child in children:
        child_dir = req_root / child["path"]
        assert child_dir.is_dir(), f"Child folder missing: {child['path']}"
        assert (child_dir / "README.md").exists(), f"Child README missing: {child['path']}"

    # Each task must be linked to its child requirement
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    for child in children:
        row = conn.execute(
            "SELECT requirement_path FROM tasks WHERE id = ?", (child["task_id"],)
        ).fetchone()
        assert row is not None, f"Task {child['task_id']} not found"
        assert row["requirement_path"] == child["path"], (
            f"Task {child['task_id']} linked to wrong path: {row['requirement_path']!r}"
        )
    conn.close()

    # Parent should have advanced to 'tasked' after decompose
    parent_stage = _req_stage(db_path, parent_path)
    assert parent_stage == "tasked", f"Expected parent in 'tasked', got '{parent_stage}'"

    # -----------------------------------------------------------------------
    # 6. Walk each child task through the bugfix DAG:
    #    pull → result → review (pass) → test (pass) → done (lead closes)
    # -----------------------------------------------------------------------
    from minion.tasks.pull_task import pull_task
    from minion.tasks.result import create_result
    from minion.tasks.review import create_review
    from minion.tasks.test_report import create_test_report
    from minion.tasks.done import done_task

    # Register coder-class agents for the pull step
    register_agent_db("coder-1", "coder")
    register_agent_db("coder-2", "coder")
    coders = ["coder-1", "coder-2"]

    for i, task_id in enumerate(task_ids):
        coder = coders[i]

        # 6a. Pull (claim) the task
        pull = pull_task(coder, task_id)
        assert "error" not in pull, f"pull_task(#{task_id}) failed: {pull}"
        assert pull["task_id"] == task_id

        # Status should be 'assigned' after pull
        assert _task_status(db_path, task_id) == "assigned", (
            f"Expected 'assigned' after pull, got '{_task_status(db_path, task_id)}'"
        )

        # 6b. Submit result — advances assigned → in_progress
        result = create_result(
            coder, task_id,
            summary=f"Implemented task #{task_id}.",
            files_changed="src/foo.py",
            notes="No issues.",
        )
        assert "error" not in result, f"create_result(#{task_id}) failed: {result}"

        # Status should advance to in_progress after result
        assert _task_status(db_path, task_id) == "in_progress", (
            f"Expected 'in_progress' after result, got '{_task_status(db_path, task_id)}'"
        )

        # 6c. Complete in_progress → fixed (requires submit_result gate which is now satisfied)
        from minion.tasks.update_task import complete_phase
        phase_result = complete_phase(coder, task_id, passed=True)
        assert "error" not in phase_result, f"complete_phase (in_progress) failed: {phase_result}"

        assert _task_status(db_path, task_id) == "fixed", (
            f"Expected 'fixed' after complete_phase, got '{_task_status(db_path, task_id)}'"
        )

        # 6d. Review (pass) — oracle reviews fixed → verified
        review = create_review("oracle-1", task_id, verdict="pass", notes="LGTM.")
        assert "error" not in review, f"create_review(#{task_id}) failed: {review}"

        assert _task_status(db_path, task_id) == "verified", (
            f"Expected 'verified' after review pass, got '{_task_status(db_path, task_id)}'"
        )

        # 6e. Test report (pass) — builder tests verified → closed
        test_rep = create_test_report(
            "builder-1", task_id,
            passed=True,
            output="All tests green.",
            notes="CI passed.",
        )
        assert "error" not in test_rep, f"create_test_report(#{task_id}) failed: {test_rep}"

        assert _task_status(db_path, task_id) == "closed", (
            f"Expected 'closed' after test pass, got '{_task_status(db_path, task_id)}'"
        )

    # -----------------------------------------------------------------------
    # 7. Advance parent requirement to completed
    # -----------------------------------------------------------------------
    # Parent is at 'tasked'; walk: tasked → in_progress → completed
    adv_ip = update_stage(parent_path, "in_progress")
    assert "error" not in adv_ip, f"update_stage(in_progress) failed: {adv_ip}"

    adv_done = update_stage(parent_path, "completed")
    assert "error" not in adv_done, f"update_stage(completed) failed: {adv_done}"
    assert adv_done["to_stage"] == "completed"

    # -----------------------------------------------------------------------
    # 8. Final assertions
    # -----------------------------------------------------------------------
    # All child tasks must be closed
    for task_id in task_ids:
        status = _task_status(db_path, task_id)
        assert status == "closed", f"Task #{task_id} not closed — status: '{status}'"

    # Parent requirement must be completed
    final_stage = _req_stage(db_path, parent_path)
    assert final_stage == "completed", f"Parent requirement not completed — stage: '{final_stage}'"
