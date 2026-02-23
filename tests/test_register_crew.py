"""Tests for register() with --crew flag (T92)."""

from __future__ import annotations

import os

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

    db_path = str(work_dir / "minion.db")
    monkeypatch.setenv("MINION_DB_PATH", db_path)
    reset_db_path()
    init_db()

    monkeypatch.chdir(tmp_path)
    yield tmp_path

    reset_db_path()


# ---------------------------------------------------------------------------
# Helper: create a minimal crew YAML on disk
# ---------------------------------------------------------------------------

def _write_crew_yaml(tmp_path: object, crew_name: str, agents: dict) -> str:
    """Write a crew YAML to a crews/ dir under tmp_path and return the path."""
    crews_dir = os.path.join(str(tmp_path), "crews")
    os.makedirs(crews_dir, exist_ok=True)
    crew_file = os.path.join(crews_dir, f"{crew_name}.yaml")

    import yaml
    cfg = {
        "project_dir": str(tmp_path),
        "agents": agents,
    }
    with open(crew_file, "w") as f:
        yaml.dump(cfg, f, default_flow_style=False)
    return crew_file


# ---------------------------------------------------------------------------
# T92 — register with crew returns zone in response
# ---------------------------------------------------------------------------

def test_register_with_crew_returns_zone(tmp_path, monkeypatch):
    """register() with crew='tmnt' for agent 'leo' includes zone from crew YAML."""
    _write_crew_yaml(tmp_path, "testcrew", {
        "leo": {
            "role": "coder",
            "zone": "Implementation, code changes, bug fixes",
            "system": "You are leo (coder class). Leader of the turtles.",
        },
    })

    # Patch _find_crew_file at its source module so the lazy import inside register() picks it up
    monkeypatch.setattr(
        "minion.crew.spawn._find_crew_file",
        lambda name, project_dir=".": os.path.join(str(tmp_path), "crews", f"{name}.yaml")
        if os.path.isfile(os.path.join(str(tmp_path), "crews", f"{name}.yaml"))
        else None,
    )

    from minion.comms import register as _register
    result = _register("leo", "coder", transport="terminal", crew="testcrew")

    assert result["status"] == "registered"
    assert result["crew"] == "testcrew"
    assert result["zone"] == "Implementation, code changes, bug fixes"
    assert "system_prompt_excerpt" in result
    assert result["system_prompt_excerpt"].startswith("You are leo")


# ---------------------------------------------------------------------------
# T92 — register without crew works as before
# ---------------------------------------------------------------------------

def test_register_without_crew_unchanged(tmp_path):
    """register() without --crew returns no crew-related keys."""
    from minion.comms import register as _register
    result = _register("agent-plain", "coder", transport="terminal")

    assert result["status"] == "registered"
    assert result["agent"] == "agent-plain"
    assert "crew" not in result
    assert "zone" not in result
    assert "capabilities" not in result
    assert "crew_error" not in result


# ---------------------------------------------------------------------------
# T92 — register with crew but agent not in YAML returns error
# ---------------------------------------------------------------------------

def test_register_with_crew_agent_not_found(tmp_path, monkeypatch):
    """register() with crew where agent name is not in the YAML returns crew_error."""
    _write_crew_yaml(tmp_path, "testcrew", {
        "leo": {
            "role": "coder",
            "zone": "Implementation",
            "system": "You are leo.",
        },
    })

    monkeypatch.setattr(
        "minion.crew.spawn._find_crew_file",
        lambda name, project_dir=".": os.path.join(str(tmp_path), "crews", f"{name}.yaml")
        if os.path.isfile(os.path.join(str(tmp_path), "crews", f"{name}.yaml"))
        else None,
    )

    from minion.comms import register as _register
    result = _register("unknown-agent", "coder", transport="terminal", crew="testcrew")

    assert result["status"] == "registered"
    assert "crew_error" in result
    assert "unknown-agent" in result["crew_error"]
    assert "leo" in result["crew_error"]
