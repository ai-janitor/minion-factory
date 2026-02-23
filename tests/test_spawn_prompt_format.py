"""Tests for format_as_prompt() and --format prompt CLI flag."""

from __future__ import annotations

import textwrap

import pytest
from click.testing import CliRunner

from minion.db import init_db, reset_db_path, now_iso


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Each test gets its own isolated SQLite DB and .work/ dir."""
    monkeypatch.setenv("MINION_DB_PATH", str(tmp_path / "test.db"))
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
    """)
    (crews / "testcrew.yaml").write_text(yaml_content)

    monkeypatch.setattr(
        "minion.crew.spawn.CREW_SEARCH_PATHS",
        [str(crews)],
    )
    return crews


def _insert_task(tmp_path, title: str = "Test task", content: str = "Do the thing") -> int:
    """Insert a task row with an on-disk task file; return task_id."""
    import sqlite3

    work = tmp_path / ".work"
    task_file = work / "tasks" / "test-task.md"
    task_file.parent.mkdir(parents=True, exist_ok=True)
    task_file.write_text(content)

    now = now_iso()
    db_path = str(tmp_path / "test.db")
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
# Unit tests for format_as_prompt()
# ---------------------------------------------------------------------------


def _make_data(
    system_prompt: str = "You are a test agent.",
    task_briefing: str = "# Task #1: Do the thing\n\nContent here.",
    tools: list | None = None,
    task_id: int = 1,
    agent_name: str = "leo",
) -> dict:
    if tools is None:
        tools = [
            {"command": "minion send"},
            {"command": "minion check-inbox"},
            {"command": "minion task result"},
        ]
    return {
        "system_prompt": system_prompt,
        "task_briefing": task_briefing,
        "tools": tools,
        "task_id": task_id,
        "agent_name": agent_name,
    }


def test_format_includes_system_prompt():
    """format_as_prompt includes the system_prompt text."""
    from minion.tasks.spawn_prompt import format_as_prompt

    data = _make_data(system_prompt="You are a disciplined coder.")
    result = format_as_prompt(data)

    assert "You are a disciplined coder." in result


def test_format_includes_task_briefing():
    """format_as_prompt includes the full task briefing."""
    from minion.tasks.spawn_prompt import format_as_prompt

    data = _make_data(task_briefing="# Task #42: Build the widget\n\nDetails follow.")
    result = format_as_prompt(data)

    assert "Task #42: Build the widget" in result
    assert "Details follow." in result


def test_format_includes_tool_commands():
    """format_as_prompt lists tool commands in a comma-separated line."""
    from minion.tasks.spawn_prompt import format_as_prompt

    data = _make_data(tools=[
        {"command": "minion send"},
        {"command": "minion task result"},
    ])
    result = format_as_prompt(data)

    assert "minion send" in result
    assert "minion task result" in result
    # Both appear on the same "Available tools:" line
    tools_line = next(
        line for line in result.splitlines() if line.startswith("Available tools:")
    )
    assert "minion send" in tools_line
    assert "minion task result" in tools_line


def test_format_includes_result_reporting_instruction():
    """format_as_prompt includes the minion task result command with agent/task."""
    from minion.tasks.spawn_prompt import format_as_prompt

    data = _make_data(task_id=97, agent_name="leo")
    result = format_as_prompt(data)

    assert "minion --compact task result" in result
    assert "--agent leo" in result
    assert "--task-id 97" in result


# ---------------------------------------------------------------------------
# CLI integration test for --format prompt
# ---------------------------------------------------------------------------


def test_cli_format_prompt_returns_flat_string(tmp_path, crew_dir):
    """CLI --format prompt prints the flat assembled string."""
    from minion.cli import cli

    task_id = _insert_task(tmp_path, title="Impl widget", content="Build the widget module")
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--compact", "task", "spawn", "--task-id", str(task_id), "--agent", "leo",
         "--crew", "testcrew", "--format", "prompt"],
    )

    assert result.exit_code == 0, result.output
    # Should contain fused prompt elements in one flat output
    assert "leo" in result.output
    assert "Impl widget" in result.output
    assert "minion --compact task result" in result.output
    assert "Available tools:" in result.output
