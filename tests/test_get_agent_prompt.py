"""Tests for get_agent_prompt() — crew agent prompt lookup."""

from __future__ import annotations

import os
import textwrap

import pytest

from minion.crew.config import get_agent_prompt


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

    # Patch _find_crew_file to search our tmp dir
    monkeypatch.setattr(
        "minion.crew.spawn.CREW_SEARCH_PATHS",
        [str(crews)],
    )
    return crews


def test_returns_agent_prompt(crew_dir):
    """get_agent_prompt returns full config dict for a known agent."""
    result = get_agent_prompt("leo", "testcrew")

    assert "error" not in result
    assert result["name"] == "leo"
    assert result["role"] == "coder"
    assert result["zone"] == "Implementation"
    assert result["model"] == "claude-sonnet-4-6"
    assert result["permission_mode"] == "bypassPermissions"
    assert result["allowed_tools"] == "Read,Write,Bash"
    # system_prefix should be injected into the system prompt
    assert "PREFIX:" in result["system"]
    assert "clean code" in result["system"]
    assert isinstance(result["capabilities"], list)


def test_nonexistent_agent_returns_error(crew_dir):
    """Requesting an agent that doesn't exist returns an error dict."""
    result = get_agent_prompt("nonexistent", "testcrew")

    assert "error" in result
    assert "nonexistent" in result["error"]
    assert "available_agents" in result
    assert "leo" in result["available_agents"]


def test_nonexistent_crew_returns_error(crew_dir):
    """Requesting a crew that doesn't exist returns an error dict."""
    result = get_agent_prompt("leo", "nonexistent")

    assert "error" in result
    assert "nonexistent" in result["error"]


def test_real_tmnt_crew_leo():
    """Smoke test against the real tmnt.yaml in the repo."""
    # Point search paths at the repo's crews/ directory
    repo_crews = os.path.join(os.path.dirname(__file__), "..", "crews")
    if not os.path.isdir(repo_crews):
        pytest.skip("crews/ directory not found relative to tests/")

    import minion.crew.spawn as spawn_mod
    original = spawn_mod.CREW_SEARCH_PATHS
    try:
        spawn_mod.CREW_SEARCH_PATHS = [os.path.abspath(repo_crews)]
        result = get_agent_prompt("leo", "tmnt")
    finally:
        spawn_mod.CREW_SEARCH_PATHS = original

    assert "error" not in result, f"Unexpected error: {result}"
    assert result["name"] == "leo"
    assert result["role"] == "coder"
    assert "system" in result
    assert len(result["system"]) > 0
