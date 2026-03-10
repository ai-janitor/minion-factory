"""Wave 6 feature tests — SU-18 through SU-22.

Purpose: Verify Wave 6 features: network API parity, cross-project coordination,
         agent experience, DAG scaffolding enforcement, dashboard queries.
Rationale: Test coverage for the corresponding modules.
Responsibility: Wave 6 feature tests. NOT responsible for unrelated concerns.
Organization: One test function per spec unit concern."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.db]


# ---------------------------------------------------------------------------
# SU-18: Network API Route Parity
# ---------------------------------------------------------------------------

def test_su18_new_handler_modules_importable():
    """All new handler modules for SU-18 should import without error."""
    from minion.network.handlers import lifecycle  # noqa: F401
    from minion.network.handlers import agent_context  # noqa: F401
    from minion.network.handlers import task_workflow  # noqa: F401
    from minion.network.handlers import diagnostics  # noqa: F401


def test_su18_lifecycle_handlers_have_register():
    """Each new handler module must have a register(router) function."""
    from minion.network.handlers import lifecycle, agent_context, task_workflow, diagnostics
    for mod in [lifecycle, agent_context, task_workflow, diagnostics]:
        assert hasattr(mod, "register"), f"{mod.__name__} missing register()"
        assert callable(mod.register), f"{mod.__name__}.register is not callable"


def test_su18_all_new_routes_registered():
    """After register_all, all SU-18 routes must exist in the router."""
    from minion.network.router import Router
    from minion.network.handlers import register_all
    router = Router()
    register_all(router)

    get_patterns = [regex.pattern for regex, _, _ in router._get_routes]
    post_patterns = [regex.pattern for regex, _, _ in router._post_routes]

    # Lifecycle routes
    assert any("cold-start" in p for p in post_patterns)
    assert any("refresh" in p for p in post_patterns)
    assert any("fenix-down" in p for p in post_patterns)

    # Agent context
    assert any("context" in p for p in post_patterns)

    # Task workflow
    assert any("complete-phase" in p for p in post_patterns)
    assert any("/tasks/result" in p for p in post_patterns)
    assert any("/tasks/review" in p for p in post_patterns)
    assert any("/tasks/test" in p for p in post_patterns)

    # Diagnostics
    assert any("db/stats" in p for p in get_patterns)

    # Lineage
    assert any("lineage" in p for p in get_patterns)


# ---------------------------------------------------------------------------
# SU-19: Cross-Project Coordination
# ---------------------------------------------------------------------------

def test_su19_coordinator_class_in_yaml():
    """The coordinator class must be defined in _agent-classes.yaml."""
    from minion.tasks.agent_classes import get_valid_classes, _load, _VALID_CLASSES
    # Force reload to pick up changes
    import minion.tasks.agent_classes as ac
    ac._REGISTRY = None
    ac._VALID_CLASSES = None
    ac._CLASS_CAPABILITIES = None
    ac._CLASS_MODELS = None
    classes = get_valid_classes()
    assert "coordinator" in classes, f"coordinator class missing from agent-classes.yaml. Found: {classes}"


def test_su19_coordinator_in_fallback_valid_classes():
    """The coordinator class must be in auth.py VALID_CLASSES fallback set."""
    from minion.auth import VALID_CLASSES
    assert "coordinator" in VALID_CLASSES


def test_su19_coordinator_exempt_from_cross_project(monkeypatch):
    """Coordinators should never be treated as cross-project (is_cross_project=False)."""
    from minion.auth import is_cross_project
    monkeypatch.setenv("MINION_CLASS", "coordinator")
    monkeypatch.setenv("MINION_PROJECT_DIR", "/some/other/project")
    assert is_cross_project() is False


def test_su19_get_project_paths(monkeypatch):
    """get_project_paths should parse MINION_PROJECTS env var."""
    from minion.defaults import get_project_paths
    monkeypatch.setenv("MINION_PROJECTS", "/proj/a:/proj/b:/proj/c")
    paths = get_project_paths()
    assert paths == ["/proj/a", "/proj/b", "/proj/c"]


def test_su19_get_project_paths_empty(monkeypatch):
    """get_project_paths returns empty list when env var not set."""
    from minion.defaults import get_project_paths
    monkeypatch.delenv("MINION_PROJECTS", raising=False)
    paths = get_project_paths()
    assert paths == []


def test_su19_multi_project_poll_with_no_paths(monkeypatch, tmp_path):
    """multi_project_poll with no paths returns a note about no projects."""
    from minion.polling import multi_project_poll
    monkeypatch.delenv("MINION_PROJECTS", raising=False)
    monkeypatch.delenv("MINION_COORDINATOR_DB_PATH", raising=False)
    # Point coordinator DB to a non-existent path so it falls through
    monkeypatch.setenv("MINION_COORDINATOR_DB_PATH", str(tmp_path / "nonexistent.db"))
    result = multi_project_poll("test-agent", project_paths=[])
    assert "projects" in result
    assert len(result["projects"]) == 0


# ---------------------------------------------------------------------------
# SU-20: Agent Experience
# ---------------------------------------------------------------------------

def test_su20_completions_importable():
    """Shell completions CLI module should import cleanly."""
    from minion.cli.completion_cmds import completions, show, install
    assert completions is not None
    assert show is not None
    assert install is not None


def test_su20_completions_registered_in_cli():
    """The completions command group should be registered in the main CLI."""
    from minion.cli.main import cli
    cmds = cli.list_commands(None)
    assert "completions" in cmds, f"completions not in CLI commands: {cmds}"


# ---------------------------------------------------------------------------
# SU-21: DAG Scaffolding Enforcement
# ---------------------------------------------------------------------------

def test_su21_implementation_flow_has_scaffolding_gate():
    """The implementation flow's plan stage should have gate: scaffolding."""
    from minion.tasks.loader import load_flow
    flow = load_flow("implementation")
    plan_stage = flow.stages.get("plan")
    assert plan_stage is not None, "implementation flow missing 'plan' stage"
    assert plan_stage.gate == "scaffolding", f"plan stage gate should be 'scaffolding', got '{plan_stage.gate}'"


def test_su21_scaffolding_gate_blocks_missing_files(tmp_path, monkeypatch):
    """complete_phase should block scaffolding stage if listed files don't exist."""
    from minion.db import init_db, reset_db_path

    # Set up isolated DB
    work_dir = tmp_path / ".work"
    work_dir.mkdir(parents=True)
    db_path = str(work_dir / "minion.db")
    monkeypatch.setenv("MINION_DB_PATH", db_path)
    monkeypatch.setenv("MINION_PROJECT_DIR", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    reset_db_path()
    init_db()

    from minion.db import get_db, now_iso
    conn = get_db()
    now = now_iso()

    # Register agent — oracle class is eligible for the plan stage
    conn.execute(
        "INSERT INTO agents (name, agent_class, registered_at, last_seen) VALUES (?, ?, ?, ?)",
        ("oracle-1", "oracle", now, now),
    )

    # Create a task in the plan stage of implementation flow with missing files
    conn.execute(
        "INSERT INTO tasks (title, task_file, created_by, status, flow_type, assigned_to, class_required, files, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("Test task", "tasks/test.md", "oracle-1", "plan", "implementation", "oracle-1", "coder", "src/missing.py", now, now),
    )
    conn.commit()

    task_id = conn.execute("SELECT id FROM tasks WHERE title = 'Test task'").fetchone()["id"]
    conn.close()

    from minion.tasks.update_task import complete_phase
    result = complete_phase("oracle-1", task_id, passed=True)
    assert "error" in result, f"Expected BLOCKED error, got: {result}"
    assert "Scaffolding incomplete" in result["error"]
    assert "src/missing.py" in result["error"]

    reset_db_path()


def test_su21_scaffolding_gate_passes_with_files(tmp_path, monkeypatch):
    """complete_phase should pass scaffolding stage if listed files exist."""
    from minion.db import init_db, reset_db_path

    work_dir = tmp_path / ".work"
    work_dir.mkdir(parents=True)
    db_path = str(work_dir / "minion.db")
    monkeypatch.setenv("MINION_DB_PATH", db_path)
    monkeypatch.setenv("MINION_PROJECT_DIR", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    reset_db_path()
    init_db()

    # Create the file that the task lists
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "exists.py").write_text("# stub\n")

    from minion.db import get_db, now_iso
    conn = get_db()
    now = now_iso()

    conn.execute(
        "INSERT INTO agents (name, agent_class, registered_at, last_seen) VALUES (?, ?, ?, ?)",
        ("coder-1", "coder", now, now),
    )
    conn.execute(
        "INSERT INTO tasks (title, task_file, created_by, status, flow_type, assigned_to, class_required, files, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("Test task 2", "tasks/test2.md", "coder-1", "plan", "implementation", "coder-1", "coder", "src/exists.py", now, now),
    )
    conn.commit()

    task_id = conn.execute("SELECT id FROM tasks WHERE title = 'Test task 2'").fetchone()["id"]
    conn.close()

    from minion.tasks.update_task import complete_phase
    result = complete_phase("coder-1", task_id, passed=True)
    # Should not have a scaffolding error (may have other issues but not scaffolding)
    if "error" in result:
        assert "Scaffolding incomplete" not in result["error"], f"Unexpected scaffolding block: {result}"

    reset_db_path()


def test_su21_lead_bypass_scaffolding_gate(tmp_path, monkeypatch):
    """Lead class should bypass scaffolding gate even with missing files."""
    from minion.db import init_db, reset_db_path

    work_dir = tmp_path / ".work"
    work_dir.mkdir(parents=True)
    db_path = str(work_dir / "minion.db")
    monkeypatch.setenv("MINION_DB_PATH", db_path)
    monkeypatch.setenv("MINION_PROJECT_DIR", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    reset_db_path()
    init_db()

    from minion.db import get_db, now_iso
    conn = get_db()
    now = now_iso()

    conn.execute(
        "INSERT INTO agents (name, agent_class, registered_at, last_seen) VALUES (?, ?, ?, ?)",
        ("lead-1", "lead", now, now),
    )
    conn.execute(
        "INSERT INTO tasks (title, task_file, created_by, status, flow_type, assigned_to, class_required, files, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("Test task 3", "tasks/test3.md", "lead-1", "plan", "implementation", "lead-1", "coder", "src/missing.py", now, now),
    )
    conn.commit()
    task_id = conn.execute("SELECT id FROM tasks WHERE title = 'Test task 3'").fetchone()["id"]
    conn.close()

    from minion.tasks.update_task import complete_phase
    result = complete_phase("lead-1", task_id, passed=True)
    # Lead should NOT be blocked by scaffolding
    if "error" in result:
        assert "Scaffolding incomplete" not in result["error"], f"Lead should bypass scaffolding gate: {result}"

    reset_db_path()


# ---------------------------------------------------------------------------
# SU-22: Dashboard Queries
# ---------------------------------------------------------------------------

def test_su22_dashboard_queries_importable():
    """Dashboard query functions from SU-22 should be importable."""
    from minion.dashboard.queries import (
        get_agent_summary,
        get_task_pipeline,
        get_system_stats,
        get_recent_messages,
    )
    assert callable(get_agent_summary)
    assert callable(get_task_pipeline)
    assert callable(get_system_stats)
    assert callable(get_recent_messages)


def test_su22_dashboard_queries_run(tmp_path, monkeypatch):
    """Dashboard queries should execute without error on a fresh DB."""
    from minion.db import init_db, reset_db_path

    work_dir = tmp_path / ".work"
    work_dir.mkdir(parents=True)
    db_path = str(work_dir / "minion.db")
    monkeypatch.setenv("MINION_DB_PATH", db_path)
    monkeypatch.chdir(tmp_path)
    reset_db_path()
    init_db()

    from minion.db import get_db
    conn = get_db()

    from minion.dashboard.queries import (
        get_agent_summary,
        get_task_pipeline,
        get_system_stats,
        get_recent_messages,
    )

    agents = get_agent_summary(conn)
    assert isinstance(agents, list)

    pipeline = get_task_pipeline(conn)
    assert isinstance(pipeline, dict)

    stats = get_system_stats(conn, db_path=db_path)
    assert isinstance(stats, dict)
    assert "tables" in stats
    assert "db_size_bytes" in stats

    messages = get_recent_messages(conn)
    assert isinstance(messages, list)

    conn.close()
    reset_db_path()
