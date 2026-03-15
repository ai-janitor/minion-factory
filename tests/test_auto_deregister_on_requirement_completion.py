"""Tests for auto-deregister agent when requirement reaches terminal stage.

Purpose: Verify that deregister_agent_on_completion() removes an agent from the
registry when a requirement advances to a terminal stage (completed, stale, etc.).
Rationale: Bug fix — leads and workers linger as ghost agents after requirement
completion. Mechanical enforcement prevents this.
Responsibility: Test the deregister path in rollup.py and the integration in
requirements/crud.py update_stage().
Organization: Standalone test functions using conftest fixtures."""

from __future__ import annotations

import sqlite3

import pytest

from minion.db import init_db, reset_db_path, now_iso
from minion.tasks.rollup import deregister_agent_on_completion, RollupResult
from minion.tasks.dag import TERMINAL_STATUSES

pytestmark = [pytest.mark.integration, pytest.mark.db]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _register_agent(db_conn, name: str, agent_class: str = "lead") -> None:
    """Insert an agent row directly into the DB for testing."""
    now = now_iso()
    db_conn.execute(
        """INSERT INTO agents (name, agent_class, registered_at, last_seen, status)
           VALUES (?, ?, ?, ?, 'active')""",
        (name, agent_class, now, now),
    )
    db_conn.commit()


def _agent_exists(db_conn, name: str) -> bool:
    """Check if an agent is registered."""
    row = db_conn.execute(
        "SELECT name FROM agents WHERE name = ?", (name,)
    ).fetchone()
    return row is not None


# ---------------------------------------------------------------------------
# Unit tests — deregister_agent_on_completion()
# ---------------------------------------------------------------------------


class TestDeregisterAgentOnCompletion:
    """Direct tests for deregister_agent_on_completion in rollup.py."""

    def test_deregisters_registered_agent(self, isolated_db):
        """A registered agent should be removed from the agents table."""
        db_path = str(isolated_db / ".work" / "minion.db")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        _register_agent(conn, "test-lead")
        assert _agent_exists(conn, "test-lead")

        results: list[RollupResult] = []
        deregister_agent_on_completion(conn, "test-lead", results=results)

        assert not _agent_exists(conn, "test-lead"), "Agent should be deregistered"

        agent_results = [r for r in results if r.entity_type == "agent"]
        assert len(agent_results) == 1
        assert agent_results[0].triggered is True
        assert agent_results[0].to_status == "deregistered"

        conn.close()

    def test_noop_for_unregistered_agent(self, isolated_db):
        """Should not fail or emit results when agent is not registered."""
        db_path = str(isolated_db / ".work" / "minion.db")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        results: list[RollupResult] = []
        deregister_agent_on_completion(conn, "nonexistent-agent", results=results)

        agent_results = [r for r in results if r.entity_type == "agent"]
        assert len(agent_results) == 0, "No result should be emitted for unregistered agent"

        conn.close()

    def test_noop_for_empty_agent_name(self, isolated_db):
        """Should not fail when agent name is empty."""
        db_path = str(isolated_db / ".work" / "minion.db")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        results: list[RollupResult] = []
        deregister_agent_on_completion(conn, "", results=results)

        assert len(results) == 0

        conn.close()

    def test_releases_file_claims(self, isolated_db):
        """Deregistration should release any file claims held by the agent."""
        db_path = str(isolated_db / ".work" / "minion.db")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        _register_agent(conn, "claim-agent")
        now = now_iso()
        conn.execute(
            "INSERT INTO file_claims (file_path, agent_name, claimed_at) VALUES (?, ?, ?)",
            ("/some/file.py", "claim-agent", now),
        )
        conn.commit()

        results: list[RollupResult] = []
        deregister_agent_on_completion(conn, "claim-agent", results=results)

        # Agent should be gone
        assert not _agent_exists(conn, "claim-agent")

        # File claim should be released
        claim = conn.execute(
            "SELECT * FROM file_claims WHERE agent_name = ?", ("claim-agent",)
        ).fetchone()
        assert claim is None, "File claim should be released"

        conn.close()


# ---------------------------------------------------------------------------
# Integration tests — update_stage() triggers auto-deregister
# ---------------------------------------------------------------------------


class TestUpdateStageAutoDeregister:
    """Integration: verify req update to terminal stage deregisters the agent."""

    def test_req_update_to_completed_deregisters_agent(self, isolated_db):
        """Advancing a requirement to 'completed' should deregister the agent."""
        db_path = str(isolated_db / ".work" / "minion.db")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        now = now_iso()

        # Register the lead agent
        _register_agent(conn, "my-lead")

        # Create requirement at 'tasked' stage with requirement-lite flow
        conn.execute(
            """INSERT INTO requirements (file_path, origin, stage, flow_type, created_by, created_at, updated_at)
               VALUES ('bugs/deregister-test', 'bug', 'tasked', 'requirement-lite', 'test', ?, ?)""",
            (now, now),
        )
        req_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Create a closed task so the all_impl_tasks_closed gate passes
        conn.execute(
            """INSERT INTO tasks (title, task_file, status, requirement_id, requirement_path, flow_type, created_by, created_at, updated_at)
               VALUES ('Fix bug', 'TASK-1.md', 'closed', ?, 'bugs/deregister-test', 'bugfix', 'test', ?, ?)""",
            (req_id, now, now),
        )
        conn.commit()
        conn.close()

        # Create the filesystem structure for gates
        req_dir = isolated_db / ".work" / "requirements" / "bugs" / "deregister-test"
        req_dir.mkdir(parents=True, exist_ok=True)
        (req_dir / "README.md").write_text("# Test")
        child_dir = req_dir / "001-fix"
        child_dir.mkdir(parents=True, exist_ok=True)
        (child_dir / "README.md").write_text("# Fix")

        # Use the update_stage function from crud.py
        from minion.requirements.crud import update_stage
        result = update_stage("bugs/deregister-test", "completed", agent="my-lead")

        assert result.get("status") == "updated", f"Expected 'updated', got: {result}"
        assert result.get("to_stage") == "completed", f"Expected 'completed', got: {result}"

        # Verify agent was deregistered
        if "deregistered_agents" in result:
            assert "my-lead" in result["deregistered_agents"]

        # Double-check in DB
        conn2 = sqlite3.connect(db_path)
        conn2.row_factory = sqlite3.Row
        assert not _agent_exists(conn2, "my-lead"), "Agent should be deregistered after req reaches completed"
        conn2.close()

    def test_req_update_to_non_terminal_does_not_deregister(self, isolated_db):
        """Advancing a requirement to a non-terminal stage should NOT deregister."""
        db_path = str(isolated_db / ".work" / "minion.db")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        now = now_iso()

        # Register the lead agent
        _register_agent(conn, "keep-lead")

        # Create requirement at 'seed' stage
        conn.execute(
            """INSERT INTO requirements (file_path, origin, stage, flow_type, created_by, created_at, updated_at)
               VALUES ('bugs/keep-test', 'bug', 'seed', 'requirement-lite', 'test', ?, ?)""",
            (now, now),
        )
        conn.commit()

        # Create the filesystem structure
        req_dir = isolated_db / ".work" / "requirements" / "bugs" / "keep-test"
        req_dir.mkdir(parents=True, exist_ok=True)
        (req_dir / "README.md").write_text("# Test")

        conn.close()

        # Advance to decomposing (non-terminal)
        from minion.requirements.crud import update_stage
        result = update_stage("bugs/keep-test", "decomposing", agent="keep-lead")

        assert result.get("status") == "updated", f"Expected 'updated', got: {result}"
        assert "deregistered_agents" not in result, "Should not deregister on non-terminal stage"

        # Agent should still exist
        conn2 = sqlite3.connect(db_path)
        conn2.row_factory = sqlite3.Row
        assert _agent_exists(conn2, "keep-lead"), "Agent should still be registered"
        conn2.close()

    def test_req_update_no_agent_no_deregister(self, isolated_db):
        """When no agent is specified, no deregistration should happen."""
        db_path = str(isolated_db / ".work" / "minion.db")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        now = now_iso()

        conn.execute(
            """INSERT INTO requirements (file_path, origin, stage, flow_type, created_by, created_at, updated_at)
               VALUES ('bugs/no-agent-test', 'bug', 'tasked', 'requirement-lite', 'test', ?, ?)""",
            (now, now),
        )
        req_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        conn.execute(
            """INSERT INTO tasks (title, task_file, status, requirement_id, requirement_path, flow_type, created_by, created_at, updated_at)
               VALUES ('Fix', 'TASK-1.md', 'closed', ?, 'bugs/no-agent-test', 'bugfix', 'test', ?, ?)""",
            (req_id, now, now),
        )
        conn.commit()

        # Create the filesystem structure for gates
        req_dir = isolated_db / ".work" / "requirements" / "bugs" / "no-agent-test"
        req_dir.mkdir(parents=True, exist_ok=True)
        (req_dir / "README.md").write_text("# Test")
        child_dir = req_dir / "001-fix"
        child_dir.mkdir(parents=True, exist_ok=True)
        (child_dir / "README.md").write_text("# Fix")

        conn.close()

        from minion.requirements.crud import update_stage
        result = update_stage("bugs/no-agent-test", "completed", agent="")

        assert result.get("status") == "updated", f"Expected 'updated', got: {result}"
        assert "deregistered_agents" not in result, "No deregistration without agent"
