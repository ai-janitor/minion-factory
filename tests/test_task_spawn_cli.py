"""Tests for `minion task spawn` CLI command."""

from __future__ import annotations

import json
import sqlite3
import textwrap

import pytest
from click.testing import CliRunner

from minion.cli import cli
from minion.db import init_db, now_iso, reset_db_path


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


def test_cli_returns_json_with_system_prompt(tmp_path, crew_dir):
    """CLI returns JSON with system_prompt field."""
    task_id = _insert_task(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, [
        "task", "spawn",
        "--task-id", str(task_id),
        "--agent", "leo",
        "--crew", "testcrew",
    ])
    assert result.exit_code == 0, f"CLI failed: {result.output}"
    data = json.loads(result.output)
    assert "system_prompt" in data
    assert "clean code" in data["system_prompt"]


def test_cli_error_when_task_not_found(tmp_path, crew_dir):
    """CLI exits 1 and reports error when task_id doesn't exist."""
    runner = CliRunner()
    result = runner.invoke(cli, [
        "task", "spawn",
        "--task-id", "99999",
        "--agent", "leo",
        "--crew", "testcrew",
    ])
    assert result.exit_code == 1
    # _output() writes error JSON to stderr, CliRunner mixes it into output
    data = json.loads(result.output)
    assert "error" in data


def test_cli_error_when_agent_not_in_crew(tmp_path, crew_dir):
    """CLI exits 1 and reports error when agent isn't in the crew."""
    task_id = _insert_task(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, [
        "task", "spawn",
        "--task-id", str(task_id),
        "--agent", "nonexistent_agent",
        "--crew", "testcrew",
    ])
    assert result.exit_code == 1
    data = json.loads(result.output)
    assert "error" in data
    assert "nonexistent_agent" in data["error"]


def test_cli_text_format(tmp_path, crew_dir):
    """CLI --format text produces human-readable output."""
    task_id = _insert_task(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, [
        "task", "spawn",
        "--task-id", str(task_id),
        "--agent", "leo",
        "--crew", "testcrew",
        "--format", "text",
    ])
    assert result.exit_code == 0, f"CLI failed: {result.output}"
    assert "SYSTEM PROMPT" in result.output
    assert "TASK BRIEFING" in result.output
    assert "Model:" in result.output
    assert "Permissions:" in result.output
    assert "Tools:" in result.output
