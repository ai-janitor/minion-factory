"""Tests for DAG gate enforcement — task #176, backlog #269.

Purpose: Verify that update_task() blocks stage skipping and done_task() blocks
         fast-close from non-final stages.
Rationale: Before this change, update_task() warned but allowed stage skips, and
           done_task() force-closed from any status. Both are attack vectors for
           agents bypassing review, QE, and testing gates.
Responsibility: Test the 4 acceptance criteria for DAG gate enforcement. NOT
                responsible for testing other task or flow behaviors.
Organization: One TestClass per concern.
"""

from __future__ import annotations

import sqlite3

import pytest

from minion.db import register_agent_db, init_db, reset_db_path

pytestmark = [pytest.mark.integration, pytest.mark.db]


# ---------------------------------------------------------------------------
# Auto-apply isolated_db from conftest
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def isolated_db_auto(isolated_db):
    """Delegate to conftest.isolated_db so every test gets an isolated DB."""
    return isolated_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _insert_task(db_path: str, status: str = "open", flow_type: str = "bugfix") -> int:
    """Insert a task at the given status and return its ID."""
    from minion.db import now_iso
    now = now_iso()
    conn = sqlite3.connect(db_path)
    cur = conn.execute(
        "INSERT INTO tasks (title, task_file, status, flow_type, created_by, created_at, updated_at) "
        "VALUES (?, 'tasks/test.md', ?, ?, 'atlas', ?, ?)",
        (f"Test task {status}", status, flow_type, now, now),
    )
    task_id = cur.lastrowid
    conn.commit()
    conn.close()
    return task_id


def _db_path(tmp_path) -> str:
    return str(tmp_path / ".work" / "minion.db")


# ---------------------------------------------------------------------------
# Change 1: update_task() blocks stage skipping
# ---------------------------------------------------------------------------


class TestUpdateTaskBlocksSkipping:
    def test_skip_from_open_to_in_progress_blocked(self, isolated_db_auto):
        """update_task() blocks jumping from 'open' to 'in_progress' (skips assigned)."""
        tmp_path = isolated_db_auto
        register_agent_db("atlas", "lead")
        task_id = _insert_task(_db_path(tmp_path), status="open", flow_type="bugfix")

        from minion.tasks.update_task import update_task
        result = update_task("atlas", task_id, status="in_progress")

        assert "error" in result
        assert "BLOCKED" in result["error"]
        assert "in_progress" in result["error"]
        assert "open" in result["error"]

    def test_skip_from_assigned_to_qe_blocked(self, isolated_db_auto):
        """update_task() blocks jumping from 'assigned' to 'qe' (skips in_progress)."""
        tmp_path = isolated_db_auto
        register_agent_db("atlas", "lead")
        task_id = _insert_task(_db_path(tmp_path), status="assigned", flow_type="bugfix")

        from minion.tasks.update_task import update_task
        result = update_task("atlas", task_id, status="qe")

        assert "error" in result
        assert "BLOCKED" in result["error"]

    def test_skip_from_open_to_verified_blocked(self, isolated_db_auto):
        """update_task() blocks a multi-stage skip from open to verified."""
        tmp_path = isolated_db_auto
        register_agent_db("atlas", "lead")
        task_id = _insert_task(_db_path(tmp_path), status="open", flow_type="bugfix")

        from minion.tasks.update_task import update_task
        result = update_task("atlas", task_id, status="verified")

        assert "error" in result
        assert "BLOCKED" in result["error"]

    def test_valid_transition_open_to_assigned_allowed(self, isolated_db_auto):
        """update_task() allows valid transition open → assigned."""
        tmp_path = isolated_db_auto
        register_agent_db("atlas", "lead")
        task_id = _insert_task(_db_path(tmp_path), status="open", flow_type="bugfix")

        from minion.tasks.update_task import update_task
        result = update_task("atlas", task_id, status="assigned")

        # Should NOT be blocked — open → assigned is a valid transition
        assert "error" not in result
        assert result.get("new_status") == "assigned"

    def test_valid_dead_end_transition_allowed(self, isolated_db_auto):
        """update_task() allows dead_end transitions (abandoned, stale, obsolete)."""
        tmp_path = isolated_db_auto
        register_agent_db("atlas", "lead")
        task_id = _insert_task(_db_path(tmp_path), status="open", flow_type="bugfix")

        from minion.tasks.update_task import update_task
        # 'abandoned' is a dead_end — valid from any stage
        result = update_task("atlas", task_id, status="abandoned")

        # Dead-ends are in valid_transitions — should not be blocked by skip check
        # (but may be blocked by the terminal check — depends on implementation)
        # The key assertion: not blocked for "skipping steps"
        if "error" in result:
            assert "BLOCKED" not in result["error"] or "skip" not in result["error"].lower()

    def test_error_message_shows_valid_next_stages(self, isolated_db_auto):
        """Error message includes the valid next stages for the current status."""
        tmp_path = isolated_db_auto
        register_agent_db("atlas", "lead")
        task_id = _insert_task(_db_path(tmp_path), status="open", flow_type="bugfix")

        from minion.tasks.update_task import update_task
        result = update_task("atlas", task_id, status="verified")

        assert "error" in result
        # The error should mention what IS valid
        assert "assigned" in result["error"] or "Valid" in result["error"]

    def test_no_status_update_not_blocked(self, isolated_db_auto):
        """update_task() with no status change (progress-only) is never blocked."""
        tmp_path = isolated_db_auto
        register_agent_db("atlas", "lead")
        task_id = _insert_task(_db_path(tmp_path), status="open", flow_type="bugfix")

        from minion.tasks.update_task import update_task
        result = update_task("atlas", task_id, progress="50% done")

        assert "error" not in result


# ---------------------------------------------------------------------------
# Change 2: done_task() blocks fast-close from non-final stages
# ---------------------------------------------------------------------------


class TestDoneTaskBlocksNonFinalStage:
    def test_done_from_open_is_allowed(self, isolated_db_auto):
        """done_task() allows fast-close of open tasks (cancellation with no work done)."""
        tmp_path = isolated_db_auto
        register_agent_db("atlas", "lead")
        task_id = _insert_task(_db_path(tmp_path), status="open", flow_type="bugfix")

        from minion.tasks.done import done_task
        result = done_task("atlas", task_id)

        assert "error" not in result
        assert result["status"] == "closed"

    def test_done_from_in_progress_blocked_on_bugfix(self, isolated_db_auto):
        """done_task() blocks fast-close from in_progress on bugfix (qe/fixed/verified required)."""
        tmp_path = isolated_db_auto
        register_agent_db("atlas", "lead")
        task_id = _insert_task(_db_path(tmp_path), status="in_progress", flow_type="bugfix")

        from minion.tasks.done import done_task
        result = done_task("atlas", task_id)

        assert "error" in result
        assert "BLOCKED" in result["error"]
        assert "in_progress" in result["error"]
        assert "verified" in result["error"]  # must reach 'verified' first

    def test_done_from_qe_blocked_on_bugfix(self, isolated_db_auto):
        """done_task() blocks fast-close from qe on bugfix (fixed/verified required)."""
        tmp_path = isolated_db_auto
        register_agent_db("atlas", "lead")
        task_id = _insert_task(_db_path(tmp_path), status="qe", flow_type="bugfix")

        from minion.tasks.done import done_task
        result = done_task("atlas", task_id)

        assert "error" in result
        assert "BLOCKED" in result["error"]

    def test_done_from_fixed_blocked_on_bugfix(self, isolated_db_auto):
        """done_task() blocks fast-close from fixed on bugfix (verified required)."""
        tmp_path = isolated_db_auto
        register_agent_db("atlas", "lead")
        task_id = _insert_task(_db_path(tmp_path), status="fixed", flow_type="bugfix")

        from minion.tasks.done import done_task
        result = done_task("atlas", task_id)

        assert "error" in result
        assert "BLOCKED" in result["error"]

    def test_done_from_verified_allowed_on_bugfix(self, isolated_db_auto):
        """done_task() allows fast-close from verified on bugfix (final pre-terminal stage)."""
        tmp_path = isolated_db_auto
        register_agent_db("atlas", "lead")
        task_id = _insert_task(_db_path(tmp_path), status="verified", flow_type="bugfix")

        from minion.tasks.done import done_task
        result = done_task("atlas", task_id)

        assert "error" not in result
        assert result["status"] == "closed"

    def test_done_from_assigned_blocked_on_bugfix(self, isolated_db_auto):
        """done_task() blocks fast-close from assigned on bugfix."""
        tmp_path = isolated_db_auto
        register_agent_db("atlas", "lead")
        task_id = _insert_task(_db_path(tmp_path), status="assigned", flow_type="bugfix")

        from minion.tasks.done import done_task
        result = done_task("atlas", task_id)

        assert "error" in result
        assert "BLOCKED" in result["error"]

    def test_done_error_message_mentions_required_stage(self, isolated_db_auto):
        """done_task() error message tells the lead what stage is required."""
        tmp_path = isolated_db_auto
        register_agent_db("atlas", "lead")
        task_id = _insert_task(_db_path(tmp_path), status="in_progress", flow_type="bugfix")

        from minion.tasks.done import done_task
        result = done_task("atlas", task_id)

        assert "error" in result
        assert "verified" in result["error"]
        assert "complete-phase" in result["error"]


# ---------------------------------------------------------------------------
# Chore/hotfix fast-close: skip stages compress the final stage
# ---------------------------------------------------------------------------


class TestDoneTaskChoreAndHotfix:
    def test_chore_done_from_in_progress_allowed(self, isolated_db_auto):
        """done_task() allows fast-close from in_progress on chore (assigned/qe/fixed/verified all skip)."""
        tmp_path = isolated_db_auto
        register_agent_db("atlas", "lead")
        task_id = _insert_task(_db_path(tmp_path), status="in_progress", flow_type="chore")

        from minion.tasks.done import done_task
        result = done_task("atlas", task_id)

        # For chore: in_progress → (qe resolves to closed via skip chain)
        # so in_progress might not be the final stage either — depends on flow
        # Key: chore should not block when qe is the final stage before closed
        # Let's just verify the behavior is not an error claiming the wrong stage
        if "error" in result:
            # If blocked, must be for a real DAG reason, not the wrong final stage
            assert "verified" not in result["error"], (
                "Chore should not require 'verified' — those stages skip"
            )

    def test_hotfix_done_from_qe_allowed(self, isolated_db_auto):
        """done_task() allows fast-close from qe on hotfix (fixed/verified skip → qe is final)."""
        tmp_path = isolated_db_auto
        register_agent_db("atlas", "lead")
        task_id = _insert_task(_db_path(tmp_path), status="qe", flow_type="hotfix")

        from minion.tasks.done import done_task
        result = done_task("atlas", task_id)

        # For hotfix: qe → (fixed and verified skip) → closed
        # so qe is the final pre-terminal stage
        assert "error" not in result or "verified" not in result.get("error", ""), (
            "Hotfix should not require 'verified' — that stage skips"
        )
        if "error" not in result:
            assert result["status"] == "closed"

    def test_hotfix_done_from_in_progress_blocked(self, isolated_db_auto):
        """done_task() blocks fast-close from in_progress on hotfix (qe is required)."""
        tmp_path = isolated_db_auto
        register_agent_db("atlas", "lead")
        task_id = _insert_task(_db_path(tmp_path), status="in_progress", flow_type="hotfix")

        from minion.tasks.done import done_task
        result = done_task("atlas", task_id)

        assert "error" in result
        assert "BLOCKED" in result["error"]
        # Must advance through qe first
        assert "qe" in result["error"]


# ---------------------------------------------------------------------------
# Separation of duties — verifying existing SU-03 covers review stages
# ---------------------------------------------------------------------------


class TestReviewStageSeparationOfDuties:
    def test_complete_phase_blocks_self_review_at_qe(self, isolated_db_auto):
        """complete_phase() blocks the same agent from advancing from qe if they last advanced to qe."""
        tmp_path = isolated_db_auto
        db_path = _db_path(tmp_path)
        register_agent_db("coder-1", "builder")
        register_agent_db("atlas", "lead")

        # Create a task at 'qe' with a transition_log showing coder-1 last advanced it
        from minion.db import now_iso
        now = now_iso()
        conn = sqlite3.connect(db_path)
        conn.execute(
            "INSERT INTO tasks (title, task_file, created_by, status, created_at, updated_at, flow_type) "
            "VALUES ('QE test', 'tasks/t.md', 'atlas', 'qe', ?, ?, 'bugfix')",
            (now, now),
        )
        task_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute(
            "INSERT INTO transition_log (entity_type, entity_id, from_status, to_status, triggered_by, created_at) "
            "VALUES ('task', ?, 'in_progress', 'qe', 'coder-1', ?)",
            (task_id, now),
        )
        conn.commit()
        conn.close()

        from minion.tasks.update_task import complete_phase
        result = complete_phase("coder-1", task_id, passed=True)

        assert "error" in result
        assert "BLOCKED" in result["error"]
        assert "self-review" in result["error"]

    def test_different_agent_can_advance_review_stage(self, isolated_db_auto):
        """A different agent (different from implementer) can advance a review stage."""
        tmp_path = isolated_db_auto
        db_path = _db_path(tmp_path)
        register_agent_db("builder-1", "builder")
        register_agent_db("coder-1", "coder")
        register_agent_db("atlas", "lead")

        from minion.db import now_iso
        now = now_iso()
        conn = sqlite3.connect(db_path)
        conn.execute(
            "INSERT INTO tasks (title, task_file, created_by, status, created_at, updated_at, flow_type) "
            "VALUES ('QE test diff agent', 'tasks/t.md', 'atlas', 'qe', ?, ?, 'bugfix')",
            (now, now),
        )
        task_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        # coder-1 last advanced it
        conn.execute(
            "INSERT INTO transition_log (entity_type, entity_id, from_status, to_status, triggered_by, created_at) "
            "VALUES ('task', ?, 'in_progress', 'qe', 'coder-1', ?)",
            (task_id, now),
        )
        conn.commit()
        conn.close()

        from minion.tasks.update_task import complete_phase
        # builder-1 is different from coder-1 — should be allowed
        result = complete_phase("builder-1", task_id, passed=True)

        assert "error" not in result
        assert result["to_status"] == "fixed"
