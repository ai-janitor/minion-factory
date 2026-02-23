"""Tests for req decompose --inline flag and stdin (T85)."""

from __future__ import annotations

import json

import pytest
import yaml
from click.testing import CliRunner

from minion.cli import cli
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
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def seeded_project(tmp_path):
    """Seed DB with a lead agent, battle plan, and parent requirement ready to decompose."""
    from minion.warroom import make_test_battle_plan
    from minion.requirements.crud import register

    # Register lead agent
    register_agent_db("lead", "lead")

    # Insert test battle plan (DB-only, no filesystem side effects)
    make_test_battle_plan(set_by="lead")

    # Create parent requirement folder + README
    req_root = tmp_path / ".work" / "requirements"
    parent_dir = req_root / "features" / "genesis"
    parent_dir.mkdir(parents=True, exist_ok=True)
    (parent_dir / "README.md").write_text("# Genesis\n")

    # Register it in the DB at 'decomposing' stage so decompose() accepts it
    register("features/genesis")
    from minion.requirements.crud import update_stage
    update_stage("features/genesis", "decomposing")

    return tmp_path


def _run(runner, project_dir, *args, input=None):
    """Invoke CLI with temp project dir for DB isolation."""
    return runner.invoke(cli, ["-C", str(project_dir)] + list(args), input=input)


# ---------------------------------------------------------------------------
# Minimal valid spec
# ---------------------------------------------------------------------------

_SPEC = {
    "children": [
        {"slug": "auth", "title": "Implement auth"},
        {"slug": "dashboard", "title": "Build dashboard"},
    ]
}

_SPEC_YAML = yaml.dump(_SPEC)


# ---------------------------------------------------------------------------
# T85 — --inline parses YAML string directly
# ---------------------------------------------------------------------------


def test_decompose_inline_parses_yaml(runner, seeded_project):
    """--inline parses the YAML string and decomposes without a spec file."""
    res = _run(
        runner, seeded_project,
        "req", "decompose",
        "--path", "features/genesis",
        "--inline", _SPEC_YAML,
        "--by", "lead",
    )
    assert res.exit_code == 0, res.output
    data = json.loads(res.output)
    assert data["status"] == "decomposed"
    assert data["children_created"] == 2


def test_decompose_inline_creates_child_folders(runner, seeded_project):
    """--inline creates child requirement folders in the filesystem."""
    _run(
        runner, seeded_project,
        "req", "decompose",
        "--path", "features/genesis",
        "--inline", _SPEC_YAML,
        "--by", "lead",
    )
    req_root = seeded_project / ".work" / "requirements" / "features" / "genesis"
    children = [d.name for d in req_root.iterdir() if d.is_dir()]
    assert any("auth" in c for c in children), f"No auth child in {children}"
    assert any("dashboard" in c for c in children), f"No dashboard child in {children}"


def test_decompose_inline_invalid_yaml_returns_error(runner, seeded_project):
    """--inline with invalid YAML returns an error, does not crash."""
    res = _run(
        runner, seeded_project,
        "req", "decompose",
        "--path", "features/genesis",
        "--inline", ":::not valid yaml:::",
        "--by", "lead",
    )
    # Should exit with error, not exception traceback
    assert res.exit_code != 0 or "error" in res.output.lower()


def test_decompose_inline_missing_children_key_returns_error(runner, seeded_project):
    """--inline YAML without 'children' key returns a validation error."""
    bad_spec = yaml.dump({"items": []})
    res = _run(
        runner, seeded_project,
        "req", "decompose",
        "--path", "features/genesis",
        "--inline", bad_spec,
        "--by", "lead",
    )
    assert res.exit_code != 0 or "error" in res.output.lower()


# ---------------------------------------------------------------------------
# T85 — --spec - reads from stdin via CliRunner input=
# ---------------------------------------------------------------------------


def test_decompose_spec_stdin_reads_yaml(runner, seeded_project):
    """--spec - reads YAML spec from stdin when input= is provided to CliRunner."""
    res = _run(
        runner, seeded_project,
        "req", "decompose",
        "--path", "features/genesis",
        "--spec", "-",
        "--by", "lead",
        input=_SPEC_YAML,
    )
    assert res.exit_code == 0, res.output
    data = json.loads(res.output)
    assert data["status"] == "decomposed"
    assert data["children_created"] == 2


# ---------------------------------------------------------------------------
# T85 — error when neither --spec nor --inline provided
# ---------------------------------------------------------------------------


def test_decompose_no_spec_no_inline_returns_error(runner, seeded_project):
    """Calling decompose without --spec or --inline produces an error."""
    res = _run(
        runner, seeded_project,
        "req", "decompose",
        "--path", "features/genesis",
        "--by", "lead",
    )
    # Should exit non-zero or emit an error message
    assert res.exit_code != 0 or "error" in res.output.lower(), (
        f"Expected error when neither --spec nor --inline given. Got: {res.output!r}"
    )
