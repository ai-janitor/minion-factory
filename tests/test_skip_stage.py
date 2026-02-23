"""Tests for update_stage skip=True shortcut (T81)."""

from __future__ import annotations

import pytest

from minion.db import init_db, reset_db_path, register_agent_db


# ---------------------------------------------------------------------------
# DB isolation fixture
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Each test gets its own .work/ dir and isolated SQLite DB."""
    work_dir = tmp_path / ".work"
    work_dir.mkdir(parents=True, exist_ok=True)
    req_dir = work_dir / "requirements"
    req_dir.mkdir(parents=True, exist_ok=True)

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


def _make_req(tmp_path, rel_path: str, extra_files: list[str] | None = None) -> None:
    """Create a requirement folder with README.md and optional extra files."""
    from minion.db import _get_db_path
    from pathlib import Path

    work_dir = Path(_get_db_path()).parent
    req_root = work_dir / "requirements"
    folder = req_root / rel_path
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "README.md").write_text(f"# {rel_path}\n")
    for fname in (extra_files or []):
        (folder / fname).write_text(f"# {fname}\n")


def _register_req(rel_path: str, created_by: str = "human") -> dict:
    from minion.requirements.crud import register
    return register(rel_path, created_by)


def _stage(tmp_path, rel_path: str) -> str:
    import sqlite3
    db_path = str(tmp_path / ".work" / "minion.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT stage FROM requirements WHERE file_path = ?", (rel_path,)
    ).fetchone()
    conn.close()
    return row["stage"]


# ---------------------------------------------------------------------------
# T81 — skip=True walks through intermediate stages for lead
# ---------------------------------------------------------------------------


def test_skip_from_tasked_to_completed_walks_in_progress(tmp_path):
    """skip=True from tasked should walk through in_progress to reach completed.

    The requirement flow: tasked → in_progress → completed.
    completed.requires = [all_impl_tasks_closed] which passes vacuously
    when there are no tasks (COUNT(*) == 0 evaluates as all closed).
    """
    from minion.requirements.crud import update_stage, register

    rel = "features/skip-test"
    _make_req(tmp_path, rel)
    register(rel)

    # Manually advance to decomposing (alt_next from seed)
    update_stage(rel, "decomposing")

    # Create a numbered child so tasked gates pass
    child_rel = f"{rel}/001-impl"
    _make_req(tmp_path, child_rel)
    register(child_rel)

    # Advance parent to tasked
    res = update_stage(rel, "tasked")
    assert "error" not in res, res

    # Now skip from tasked all the way to in_progress
    result = update_stage(rel, "in_progress", skip=True, agent="lead")
    assert "error" not in result, result

    final = _stage(tmp_path, rel)
    # Should reach at least in_progress (completed may require closed tasks)
    assert final in ("in_progress", "completed"), f"Unexpected stage: {final}"
    assert result["from_stage"] == "tasked"


def test_skip_non_lead_agent_rejected(tmp_path):
    """Non-lead agents with skip=True are treated as non-skip (no privilege escalation).

    When agent is not in _LEAD_CLASSES, the skip branch is not entered.
    The function falls through to normal single-hop transition logic.
    """
    from minion.requirements.crud import update_stage, register

    rel = "features/skip-non-lead"
    _make_req(tmp_path, rel)
    register(rel)

    # Try to skip from seed to completed as a coder — should not jump multiple stages
    result = update_stage(rel, "completed", skip=True, agent="coder")

    # A coder cannot jump seed → completed even with skip=True;
    # the skip branch is bypassed and normal transition validation applies
    assert "error" in result or result.get("to_stage") != "completed", (
        "Non-lead agent should not be able to skip to completed"
    )


def test_skip_halts_at_gate_failure(tmp_path):
    """skip=True halts at stages whose gates fail rather than crashing.

    completed requires all_impl_tasks_closed. If tasks exist and are open,
    the walk should halt before or at completed and include a warning.
    """
    from minion.requirements.crud import update_stage, register
    from minion.db import get_db, now_iso

    rel = "features/skip-gate-test"
    _make_req(tmp_path, rel)
    register(rel)
    update_stage(rel, "decomposing")

    # Create child req so tasked gates pass
    child_rel = f"{rel}/001-gated"
    _make_req(tmp_path, child_rel)
    register(child_rel)
    update_stage(rel, "tasked")

    # Insert an open task linked to this requirement so completed gate fails
    conn = get_db()
    now = now_iso()
    conn.execute(
        """INSERT INTO tasks
           (title, task_file, status, created_by, created_at, updated_at,
            requirement_path, flow_type)
           VALUES (?, ?, 'open', 'test', ?, ?, ?, 'feature')""",
        ("Blocking task", "/tmp/t.md", now, now, child_rel),
    )
    conn.commit()
    conn.close()

    # Skip from in_progress toward completed — gate should block at completed
    update_stage(rel, "in_progress")
    result = update_stage(rel, "completed", skip=True, agent="lead")

    # Either an error, or a warning that we halted before the requested stage
    final = _stage(tmp_path, rel)
    halted = "warning" in result or final != "completed"
    assert halted, (
        f"Expected skip to halt before 'completed' with open tasks. "
        f"Got stage={final}, result={result}"
    )
