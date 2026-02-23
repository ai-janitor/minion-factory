"""Tests for the requirements subsystem — CRUD, stage transitions, CLI commands."""

from __future__ import annotations

import os
import sqlite3
import tempfile

import pytest
from click.testing import CliRunner

from minion.cli import cli


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def project_dir(tmp_path):
    """Temporary project directory with a seeded .work/requirements/ tree."""
    work = tmp_path / ".work"
    req_root = work / "requirements"

    # features/genesis/ — root doc
    genesis = req_root / "features" / "genesis"
    genesis.mkdir(parents=True)
    (genesis / "README.md").write_text("# Genesis\n")
    (genesis / "itemized-requirements.md").write_text("1. Auth\n2. Dashboard\n")

    # features/genesis/001-auth-flow/ — child
    auth = genesis / "001-auth-flow"
    auth.mkdir()
    (auth / "README.md").write_text("# Auth Flow\n")

    # bugs/preview-word-loss/ — bug root
    bug = req_root / "bugs" / "preview-word-loss"
    bug.mkdir(parents=True)
    (bug / "README.md").write_text("# Bug: Preview Word Loss\n")

    return tmp_path


@pytest.fixture
def runner():
    return CliRunner()


def _run(runner, project_dir, *args):
    """Invoke CLI with a temporary project dir so DB is isolated."""
    return runner.invoke(cli, ["-C", str(project_dir)] + list(args))


# ---------------------------------------------------------------------------
# Stage module unit tests
# ---------------------------------------------------------------------------

def test_valid_stage_transitions():
    """Engine allows valid transitions defined in requirement.yaml."""
    from minion.tasks.engine import resolve_next
    from minion.tasks.loader import load_flow

    flow = load_flow("requirement")
    # Happy path
    assert resolve_next(flow, "seed").to_status == "itemizing"
    assert resolve_next(flow, "itemizing").to_status == "itemized"
    assert resolve_next(flow, "decomposing").to_status == "tasked"
    assert resolve_next(flow, "tasked").to_status == "in_progress"
    assert resolve_next(flow, "in_progress").to_status == "completed"
    # Fail path
    assert resolve_next(flow, "itemizing", passed=False).to_status == "seed"
    # Explicit target (alt_next)
    assert resolve_next(flow, "itemized", explicit_target="decomposing").success
    # Terminal
    assert not resolve_next(flow, "completed").success


def test_invalid_stage_transitions():
    """Engine rejects transitions not in the DAG."""
    from minion.tasks.engine import resolve_next
    from minion.tasks.loader import load_flow

    flow = load_flow("requirement")
    # Cannot skip stages
    assert not resolve_next(flow, "seed", explicit_target="tasked").success
    assert not resolve_next(flow, "seed", explicit_target="completed").success
    # Cannot go backwards arbitrarily
    assert not resolve_next(flow, "decomposing", explicit_target="seed").success


# ---------------------------------------------------------------------------
# CRUD unit tests
# ---------------------------------------------------------------------------

def test_register_and_list(runner, project_dir):
    res = _run(runner, project_dir, "req", "register", "--path", "features/genesis/")
    assert res.exit_code == 0, res.output
    assert "registered" in res.output

    res = _run(runner, project_dir, "req", "list")
    assert res.exit_code == 0
    assert "features/genesis" in res.output


def test_register_duplicate_returns_error(runner, project_dir):
    _run(runner, project_dir, "req", "register", "--path", "features/genesis/")
    res = _run(runner, project_dir, "req", "register", "--path", "features/genesis/")
    # Duplicate should fail (error written to stderr, exit 1)
    assert res.exit_code == 1
    assert "already registered" in res.output


def test_reindex_discovers_filesystem(runner, project_dir):
    res = _run(runner, project_dir, "req", "reindex")
    assert res.exit_code == 0, res.output
    assert "reindexed" in res.output

    res = _run(runner, project_dir, "req", "list")
    output = res.output
    # All three folders with README.md should appear
    assert "features/genesis" in output
    assert "001-auth-flow" in output
    assert "bugs/preview-word-loss" in output


def test_reindex_infers_origin(runner, project_dir):
    _run(runner, project_dir, "req", "reindex")

    res = _run(runner, project_dir, "req", "list", "--origin", "feature")
    assert res.exit_code == 0
    assert "genesis" in res.output

    res = _run(runner, project_dir, "req", "list", "--origin", "bug")
    assert res.exit_code == 0
    assert "preview-word-loss" in res.output


def test_reindex_is_idempotent(runner, project_dir):
    """Running reindex twice should not duplicate rows."""
    _run(runner, project_dir, "req", "reindex")
    res = _run(runner, project_dir, "req", "reindex")
    assert res.exit_code == 0
    import json
    data = json.loads(res.output)
    assert data["added"] == 0
    assert data["skipped"] > 0


def test_reindex_infers_decomposed_stage(runner, project_dir):
    """genesis/ has child folders → should be inferred as decomposed."""
    _run(runner, project_dir, "req", "reindex")
    import json
    res = _run(runner, project_dir, "req", "status", "features/genesis")
    data = json.loads(res.output)
    assert data["requirement"]["stage"] == "decomposed"


def test_reindex_infers_decomposing_stage(project_dir, runner):
    """A folder with itemized-requirements.md but no children → decomposing."""
    # Add a folder with itemized doc but no subfolders
    p = project_dir / ".work" / "requirements" / "features" / "solo"
    p.mkdir(parents=True)
    (p / "README.md").write_text("# Solo\n")
    (p / "itemized-requirements.md").write_text("1. item\n")

    _run(runner, project_dir, "req", "reindex")
    import json
    res = _run(runner, project_dir, "req", "status", "features/solo")
    data = json.loads(res.output)
    assert data["requirement"]["stage"] == "decomposing"


def test_stage_transition_valid(runner, project_dir):
    _run(runner, project_dir, "req", "register", "--path", "features/genesis/")
    res = _run(runner, project_dir, "req", "update", "--path", "features/genesis/", "--stage", "itemizing")
    assert res.exit_code == 0
    import json
    data = json.loads(res.output)
    assert data["to_stage"] == "itemizing"


def test_stage_transition_invalid_skip(runner, project_dir):
    _run(runner, project_dir, "req", "register", "--path", "features/genesis/")
    # Trying to skip from seed → tasked should fail
    res = _run(runner, project_dir, "req", "update", "--path", "features/genesis/", "--stage", "tasked")
    assert res.exit_code == 1
    assert "blocked" in res.output.lower() or "not a valid transition" in res.output.lower()


def test_stage_transition_fail_path(runner, project_dir):
    """itemizing → (fail) → seed is the fail-back path."""
    _run(runner, project_dir, "req", "register", "--path", "features/genesis/")
    _run(runner, project_dir, "req", "update", "--path", "features/genesis/", "--stage", "itemizing")

    # Go back to seed (fail path)
    res = _run(runner, project_dir, "req", "update", "--path", "features/genesis/", "--stage", "seed")
    assert res.exit_code == 0
    import json
    data = json.loads(res.output)
    assert data["to_stage"] == "seed"


def test_link_task(runner, project_dir, tmp_path):
    """Link a task to a requirement, then verify status shows it."""
    import json

    # Register a requirement
    _run(runner, project_dir, "req", "register", "--path", "features/genesis/")

    # Register a lead agent + create a task (requires lead class and battle plan)
    _run(runner, project_dir, "register", "--name", "lead1", "--class", "lead")

    battle_plan_file = project_dir / "plan.md"
    battle_plan_file.write_text("# Plan\n")
    _run(runner, project_dir, "set-battle-plan", "--agent", "lead1", "--plan", str(battle_plan_file))

    task_file = project_dir / "task.md"
    task_file.write_text("# Task\n")

    env = {"MINION_CLASS": "lead"}
    res = runner.invoke(cli, [
        "-C", str(project_dir),
        "create-task",
        "--agent", "lead1",
        "--title", "Auth implementation",
        "--task-file", str(task_file),
    ], env=env)
    assert res.exit_code == 0, res.output
    task_id = json.loads(res.output)["task_id"]

    # Link task to requirement
    res = _run(runner, project_dir, "req", "link", "--task", str(task_id), "--path", "features/genesis/")
    assert res.exit_code == 0
    data = json.loads(res.output)
    assert data["task_id"] == task_id

    # Status shows linked task
    res = _run(runner, project_dir, "req", "status", "features/genesis/")
    data = json.loads(res.output)
    assert data["task_count"] == 1


def test_tree_command(runner, project_dir):
    """Tree shows root and descendants."""
    _run(runner, project_dir, "req", "reindex")
    import json
    res = _run(runner, project_dir, "req", "tree", "features/genesis")
    assert res.exit_code == 0, res.output
    data = json.loads(res.output)
    paths = [n["file_path"] for n in data["nodes"]]
    assert "features/genesis" in paths
    assert "features/genesis/001-auth-flow" in paths


def test_orphans_returns_leaf_with_no_tasks(runner, project_dir):
    """A leaf requirement with no linked tasks appears in orphans."""
    _run(runner, project_dir, "req", "reindex")
    import json
    res = _run(runner, project_dir, "req", "orphans")
    assert res.exit_code == 0
    data = json.loads(res.output)
    paths = [o["file_path"] for o in data["orphans"]]
    # 001-auth-flow is a leaf (no children) and has no tasks
    assert "features/genesis/001-auth-flow" in paths
    # genesis itself has children, so it is NOT a leaf
    assert "features/genesis" not in paths


def test_unlinked_tasks(runner, project_dir, tmp_path):
    """Tasks without requirement_path appear in unlinked output."""
    import json

    _run(runner, project_dir, "register", "--name", "lead1", "--class", "lead")
    battle_plan_file = project_dir / "plan.md"
    battle_plan_file.write_text("# Plan\n")
    _run(runner, project_dir, "set-battle-plan", "--agent", "lead1", "--plan", str(battle_plan_file))
    task_file = project_dir / "task.md"
    task_file.write_text("# Task\n")

    env = {"MINION_CLASS": "lead"}
    runner.invoke(cli, [
        "-C", str(project_dir),
        "create-task",
        "--agent", "lead1",
        "--title", "Unlinked task",
        "--task-file", str(task_file),
    ], env=env)

    res = _run(runner, project_dir, "req", "unlinked")
    assert res.exit_code == 0
    data = json.loads(res.output)
    assert len(data["unlinked_tasks"]) >= 1


def test_list_filter_by_stage(runner, project_dir):
    """--stage filter returns only matching rows."""
    _run(runner, project_dir, "req", "register", "--path", "features/genesis/")
    _run(runner, project_dir, "req", "register", "--path", "bugs/preview-word-loss/")
    _run(runner, project_dir, "req", "update", "--path", "features/genesis/", "--stage", "itemizing")

    import json
    res = _run(runner, project_dir, "req", "list", "--stage", "itemizing")
    data = json.loads(res.output)
    assert all(r["stage"] == "itemizing" for r in data["requirements"])

    res = _run(runner, project_dir, "req", "list", "--stage", "seed")
    data = json.loads(res.output)
    assert all(r["stage"] == "seed" for r in data["requirements"])


# ---------------------------------------------------------------------------
# Auto-advance checkpoint tests
# ---------------------------------------------------------------------------

def test_itemized_is_a_checkpoint_not_auto_advanced(runner, project_dir):
    """Advancing to itemized must stop there — not auto-advance to investigating.

    itemized.requires = [itemized-requirements.md] triggers the `if stage_obj.requires: break`
    guard added to update_stage(). Without the fix, the engine would auto-advance
    to `investigating` whenever the next-stage gate happened to pass.
    """
    import json

    # genesis/ has itemized-requirements.md, satisfying the gate to enter itemized
    _run(runner, project_dir, "req", "register", "--path", "features/genesis/")
    _run(runner, project_dir, "req", "update", "--path", "features/genesis/", "--stage", "itemizing")

    res = _run(runner, project_dir, "req", "update", "--path", "features/genesis/", "--stage", "itemized")
    assert res.exit_code == 0, res.output

    data = json.loads(res.output)
    assert data["to_stage"] == "itemized", (
        f"Expected stage to stop at 'itemized', got '{data['to_stage']}'"
    )
    # Confirm auto-advance did NOT push past this checkpoint
    assert data["to_stage"] != "investigating"
    # auto_advanced_through should be absent or empty — itemized is where we land
    assert "auto_advanced_through" not in data or "itemized" not in data.get("auto_advanced_through", [])


def test_tasked_is_a_checkpoint_not_auto_advanced(runner, project_dir):
    """Advancing to tasked must stop there — not auto-advance to in_progress.

    tasked.requires = [numbered_child_folders, impl_task_readmes, all_leaves_have_tasks]
    triggers the `if stage_obj.requires: break` guard. Without the fix the engine
    would auto-advance into in_progress once all gate conditions vacuously pass.

    The fixture already contains features/genesis/001-auth-flow/ (a numbered folder
    with a README.md), satisfying the structural filesystem gates for tasked.
    all_leaves_have_tasks passes vacuously because the parent_id column does not
    exist in the current schema.
    """
    import json

    # genesis/ has 001-auth-flow/ (numbered child with README.md) — gates for
    # tasked pass: numbered_child_folders, impl_task_readmes, all_leaves_have_tasks
    _run(runner, project_dir, "req", "register", "--path", "features/genesis/")

    # Advance seed → decomposing via alt_next (skip itemizing for a small requirement)
    res = _run(runner, project_dir, "req", "update", "--path", "features/genesis/", "--stage", "decomposing")
    assert res.exit_code == 0, res.output

    # Now advance decomposing → tasked; the auto-advance loop must halt at tasked
    res = _run(runner, project_dir, "req", "update", "--path", "features/genesis/", "--stage", "tasked")
    assert res.exit_code == 0, res.output

    data = json.loads(res.output)
    assert data["to_stage"] == "tasked", (
        f"Expected stage to stop at 'tasked', got '{data['to_stage']}'"
    )
    # Confirm auto-advance did NOT push past this checkpoint into in_progress
    assert data["to_stage"] != "in_progress"
