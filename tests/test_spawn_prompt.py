"""Tests for get_spawn_prompt() — spawn-ready agent briefing assembly."""

from __future__ import annotations

import os
import sqlite3
import textwrap

import pytest

from minion.db import init_db, reset_db_path, now_iso


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Each test gets its own .work/ dir and isolated SQLite DB."""
    work_dir = tmp_path / ".work"
    work_dir.mkdir(parents=True, exist_ok=True)

    db_path = str(work_dir / "minion.db")
    monkeypatch.setenv("MINION_DB_PATH", db_path)
    reset_db_path()
    init_db()

    from minion.db import register_agent_db
    register_agent_db("lead", "lead")

    from minion.warroom import make_test_battle_plan
    make_test_battle_plan()

    monkeypatch.chdir(tmp_path)
    yield tmp_path

    reset_db_path()


@pytest.fixture()
def crew_dir(tmp_path, monkeypatch):
    """Create a minimal crew YAML and point search paths at it."""
    crews = tmp_path / "crews"
    crews.mkdir()

    yaml_content = textwrap.dedent("""\
        project_dir: /tmp/fake-project

        system_prefix: "PREFIX:"

        agents:
          leo:
            role: coder
            zone: "Implementation"
            provider: claude
            model: claude-sonnet-4-6
            permission_mode: bypassPermissions
            allowed_tools: "Read,Write,Bash"
            system: |
              You are leo (coder class). Write clean code.
          raph:
            role: builder
            zone: "Build and test"
            provider: claude
    """)
    (crews / "testcrew.yaml").write_text(yaml_content)

    monkeypatch.setattr(
        "minion.crew.spawn.CREW_SEARCH_PATHS",
        [str(crews)],
    )
    return crews


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _insert_task(tmp_path, title: str = "Test task", content: str = "Do the thing") -> int:
    """Insert a task row with an on-disk task file, return task_id."""
    work = tmp_path / ".work"
    task_file = work / "tasks" / "test-task.md"
    task_file.parent.mkdir(parents=True, exist_ok=True)
    task_file.write_text(content)

    now = now_iso()
    db_path = str(work / "minion.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO tasks
               (title, task_file, status, assigned_to, created_by,
                flow_type, activity_count, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)""",
        (title, str(task_file), "assigned", "leo", "lead", "bugfix", now, now),
    )
    task_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return task_id


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_returns_system_prompt(tmp_path, crew_dir):
    """get_spawn_prompt returns the system prompt from crew YAML."""
    from minion.tasks.spawn_prompt import get_spawn_prompt

    task_id = _insert_task(tmp_path)
    result = get_spawn_prompt(task_id, "leo", "testcrew")

    assert "error" not in result
    assert "clean code" in result["system_prompt"]
    assert "PREFIX:" in result["system_prompt"]


def test_includes_task_content(tmp_path, crew_dir):
    """get_spawn_prompt includes the task file content in the briefing."""
    from minion.tasks.spawn_prompt import get_spawn_prompt

    task_id = _insert_task(tmp_path, title="Implement widget", content="Build the widget module")
    result = get_spawn_prompt(task_id, "leo", "testcrew")

    assert "error" not in result
    assert "Implement widget" in result["task_briefing"]
    assert "Build the widget module" in result["task_briefing"]
    assert result["task_id"] == task_id


def test_includes_tools_list(tmp_path, crew_dir):
    """get_spawn_prompt includes the tools list for the agent's role."""
    from minion.tasks.spawn_prompt import get_spawn_prompt

    task_id = _insert_task(tmp_path)
    result = get_spawn_prompt(task_id, "leo", "testcrew")

    assert "error" not in result
    assert isinstance(result["tools"], list)
    assert len(result["tools"]) > 0
    # Coder class should have common tools like send, check-inbox
    commands = [t["command"] for t in result["tools"]]
    assert "minion send" in commands
    assert "minion check-inbox" in commands


def test_error_when_task_not_found(tmp_path, crew_dir):
    """get_spawn_prompt returns error dict when task_id doesn't exist."""
    from minion.tasks.spawn_prompt import get_spawn_prompt

    result = get_spawn_prompt(99999, "leo", "testcrew")

    assert "error" in result


def test_error_when_agent_not_in_crew(tmp_path, crew_dir):
    """get_spawn_prompt returns error dict when agent isn't in the crew."""
    from minion.tasks.spawn_prompt import get_spawn_prompt

    task_id = _insert_task(tmp_path)
    result = get_spawn_prompt(task_id, "nonexistent_agent", "testcrew")

    assert "error" in result
    assert "nonexistent_agent" in result["error"]


def test_includes_model_and_permissions(tmp_path, crew_dir):
    """get_spawn_prompt propagates model, allowed_tools, permission_mode."""
    from minion.tasks.spawn_prompt import get_spawn_prompt

    task_id = _insert_task(tmp_path)
    result = get_spawn_prompt(task_id, "leo", "testcrew")

    assert result["model"] == "claude-sonnet-4-6"
    assert result["allowed_tools"] == "Read,Write,Bash"
    assert result["permission_mode"] == "bypassPermissions"
    assert result["agent_name"] == "leo"
    assert result["crew_name"] == "testcrew"
