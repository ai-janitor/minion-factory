"""Tests for {agent_name} placeholder substitution in crew YAMLs and task spawn."""

from __future__ import annotations

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
    make_test_battle_plan(str(work_dir / "minion.db"))

    monkeypatch.chdir(tmp_path)
    yield tmp_path

    reset_db_path()


@pytest.fixture()
def crew_dir(tmp_path, monkeypatch):
    """Create a crew YAML with {agent_name} placeholders and point search paths at it."""
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
              You are leo (coder class). Disciplined strategist. Clean code.

              ON STARTUP (do this immediately, before anything else — use Bash tool):
              1. minion --compact register --name {agent_name} --class coder --transport terminal
              2. minion set-context --agent {agent_name} --context 'loaded, waiting for orders'
              3. minion check-inbox --agent {agent_name}
              4. minion set-status --agent {agent_name} --status "ready for orders"
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


def test_format_as_prompt_substitutes_agent_name(tmp_path, crew_dir):
    """format_as_prompt with agent_name='coder-alpha' substitutes {agent_name} in system prompt."""
    from minion.tasks.spawn_prompt import get_spawn_prompt, format_as_prompt

    task_id = _insert_task(tmp_path)
    result = get_spawn_prompt(task_id, profile_name="leo", agent_name="coder-alpha", crew_name="testcrew")

    assert "error" not in result
    prompt = format_as_prompt(result)

    # All {agent_name} placeholders must be replaced with the runtime name
    assert "{agent_name}" not in prompt
    assert "register --name coder-alpha" in prompt
    assert "--agent coder-alpha" in prompt


def test_profile_and_name_produce_correct_register_command(tmp_path, crew_dir):
    """--profile leo --name coder-alpha produces 'register --name coder-alpha' in prompt output."""
    task_id = _insert_task(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, [
        "task", "spawn",
        "--task-id", str(task_id),
        "--profile", "leo",
        "--name", "coder-alpha",
        "--crew", "testcrew",
        "--format", "prompt",
    ])

    assert result.exit_code == 0, f"CLI failed: {result.output}"
    assert "register --name coder-alpha" in result.output
    assert "{agent_name}" not in result.output


def test_omitting_name_defaults_to_profile(tmp_path, crew_dir):
    """Omitting --name uses the profile name as the runtime agent name."""
    task_id = _insert_task(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, [
        "task", "spawn",
        "--task-id", str(task_id),
        "--profile", "leo",
        "--crew", "testcrew",
        "--format", "prompt",
    ])

    assert result.exit_code == 0, f"CLI failed: {result.output}"
    # With no --name, should default to profile name "leo"
    assert "register --name leo" in result.output
    assert "{agent_name}" not in result.output


def test_real_crew_yaml_uses_agent_name_placeholder():
    """At least one real crew YAML contains {agent_name} in ON STARTUP register command."""
    import os
    import glob

    # Find crew YAML files relative to the project root
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    crew_files = glob.glob(os.path.join(project_root, "crews", "*.yaml"))

    assert crew_files, "No crew YAML files found"

    found = False
    for path in crew_files:
        with open(path) as f:
            content = f.read()
        if "register --name {agent_name}" in content:
            found = True
            break

    assert found, (
        "No crew YAML contains 'register --name {agent_name}' — "
        "hardcoded names were not replaced with the placeholder"
    )
