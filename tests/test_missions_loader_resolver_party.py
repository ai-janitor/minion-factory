"""Tests for the missions subsystem — loader, resolver, party suggestion.

Purpose: Cover the zero-test gap for src/minion/missions/ (backlog #85).
Rationale: Missions compose teams from capabilities. If loader or resolver
           breaks, the entire crew-spawn pipeline fails silently.
Responsibility: Validate load_mission, list_missions, resolve_slots, suggest_party.
Organization: Grouped by module — loader tests, resolver tests, party tests.
"""

from __future__ import annotations

import os
import textwrap
from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fixture: temporary missions directory with test YAML files
# ---------------------------------------------------------------------------


@pytest.fixture()
def missions_dir(tmp_path):
    """Create a temporary missions directory with valid and invalid YAMLs."""
    mdir = tmp_path / "missions"
    mdir.mkdir()

    # Valid mission — uses only known capabilities from auth.py
    (mdir / "bugfix.yaml").write_text(textwrap.dedent("""\
        name: bugfix
        description: Find bug, fix code, test, review fix
        requires:
          - manage
          - investigate
          - code
          - test
          - review
    """))

    (mdir / "simple.yaml").write_text(textwrap.dedent("""\
        name: simple
        description: Just code
        requires:
          - code
    """))

    # Invalid mission — missing required 'requires' key
    (mdir / "broken-no-requires.yaml").write_text(textwrap.dedent("""\
        name: broken
        description: Missing requires
    """))

    # Invalid mission — unknown capability
    (mdir / "broken-bad-cap.yaml").write_text(textwrap.dedent("""\
        name: broken-bad-cap
        description: Has a bad capability
        requires:
          - code
          - flying
    """))

    return mdir


# ---------------------------------------------------------------------------
# Loader tests — load_mission, list_missions
# ---------------------------------------------------------------------------


class TestLoadMission:
    """Tests for missions.loader.load_mission."""

    def test_load_valid_mission(self, missions_dir):
        from minion.missions.loader import load_mission
        m = load_mission("bugfix", missions_dir=missions_dir)
        assert m.name == "bugfix"
        assert m.description == "Find bug, fix code, test, review fix"
        assert "code" in m.requires
        assert "manage" in m.requires

    def test_load_missing_mission_raises(self, missions_dir):
        from minion.missions.loader import load_mission
        with pytest.raises(FileNotFoundError, match="nonexistent"):
            load_mission("nonexistent", missions_dir=missions_dir)

    def test_load_mission_missing_requires_raises(self, missions_dir):
        from minion.missions.loader import load_mission
        with pytest.raises(ValueError, match="non-empty 'requires'"):
            load_mission("broken-no-requires", missions_dir=missions_dir)

    def test_load_mission_unknown_capability_raises(self, missions_dir):
        from minion.missions.loader import load_mission
        with pytest.raises(ValueError, match="flying"):
            load_mission("broken-bad-cap", missions_dir=missions_dir)


class TestListMissions:
    """Tests for missions.loader.list_missions."""

    def test_list_returns_sorted_names(self, missions_dir):
        from minion.missions.loader import list_missions
        names = list_missions(missions_dir=missions_dir)
        assert isinstance(names, list)
        # Should include all .yaml files (valid and broken)
        assert "bugfix" in names
        assert "simple" in names
        assert names == sorted(names)

    def test_list_empty_dir(self, tmp_path):
        from minion.missions.loader import list_missions
        empty = tmp_path / "empty"
        empty.mkdir()
        assert list_missions(missions_dir=empty) == []

    def test_list_nonexistent_dir(self, tmp_path):
        from minion.missions.loader import list_missions
        assert list_missions(missions_dir=tmp_path / "nope") == []


# ---------------------------------------------------------------------------
# Resolver tests — resolve_slots
# ---------------------------------------------------------------------------


class TestResolveSlots:
    """Tests for missions.resolver.resolve_slots."""

    def test_always_includes_lead(self):
        from minion.missions.resolver import resolve_slots
        slots = resolve_slots({"code"})
        assert "lead" in slots

    def test_code_capability_adds_coder(self):
        from minion.missions.resolver import resolve_slots
        slots = resolve_slots({"code"})
        assert "coder" in slots

    def test_unknown_capability_raises(self):
        from minion.missions.resolver import resolve_slots
        with pytest.raises(ValueError, match="Unknown capabilities"):
            resolve_slots({"flying"})

    def test_result_is_sorted(self):
        from minion.missions.resolver import resolve_slots
        slots = resolve_slots({"code", "build", "test"})
        assert slots == sorted(slots)

    def test_manage_only_returns_lead(self):
        """manage is covered by lead — no additional classes needed."""
        from minion.missions.resolver import resolve_slots
        slots = resolve_slots({"manage"})
        assert slots == ["lead"]

    def test_multi_capability_coverage(self):
        """Multiple capabilities should be covered with minimal classes."""
        from minion.missions.resolver import resolve_slots
        slots = resolve_slots({"manage", "code", "investigate"})
        assert "lead" in slots
        # code and investigate should be covered (could be coder + recon, etc.)
        assert len(slots) >= 2


# ---------------------------------------------------------------------------
# Party tests — suggest_party
# ---------------------------------------------------------------------------


class TestSuggestParty:
    """Tests for missions.party.suggest_party."""

    def test_suggest_returns_dict_keyed_by_slot(self, tmp_path):
        """suggest_party should return {slot: [characters...]}."""
        from minion.missions.party import suggest_party

        # Create a minimal crew YAML
        crews_dir = tmp_path / "crews"
        crews_dir.mkdir()
        crew_yaml = {
            "project_dir": str(tmp_path),
            "agents": {
                "alice": {"role": "lead", "system": "I am alice"},
                "bob": {"role": "coder", "system": "I am bob"},
            },
        }
        (crews_dir / "testcrew.yaml").write_text(yaml.dump(crew_yaml))

        # Monkeypatch search paths — we can call with project_dir
        import minion.crew.spawn as spawn_mod
        original = spawn_mod.CREW_SEARCH_PATHS
        spawn_mod.CREW_SEARCH_PATHS = [str(crews_dir)]
        try:
            result = suggest_party(["lead", "coder"], project_dir=str(tmp_path))
            assert isinstance(result, dict)
            assert "lead" in result
            assert "coder" in result
            # alice should be in lead slot
            lead_names = [c["name"] for c in result["lead"]]
            assert "alice" in lead_names
            # bob should be in coder slot
            coder_names = [c["name"] for c in result["coder"]]
            assert "bob" in coder_names
        finally:
            spawn_mod.CREW_SEARCH_PATHS = original

    def test_suggest_empty_slots(self, tmp_path):
        """Empty slots list should return empty dict."""
        from minion.missions.party import suggest_party
        result = suggest_party([], project_dir=str(tmp_path))
        assert result == {}

    def test_suggest_filters_by_crew(self, tmp_path):
        """crews filter should only include characters from matching crews."""
        from minion.missions.party import suggest_party

        crews_dir = tmp_path / "crews"
        crews_dir.mkdir()
        # Crew A
        (crews_dir / "alpha.yaml").write_text(yaml.dump({
            "project_dir": str(tmp_path),
            "agents": {"a1": {"role": "coder", "system": "A1"}},
        }))
        # Crew B
        (crews_dir / "beta.yaml").write_text(yaml.dump({
            "project_dir": str(tmp_path),
            "agents": {"b1": {"role": "coder", "system": "B1"}},
        }))

        import minion.crew.spawn as spawn_mod
        original = spawn_mod.CREW_SEARCH_PATHS
        spawn_mod.CREW_SEARCH_PATHS = [str(crews_dir)]
        try:
            result = suggest_party(["coder"], crews=["alpha"], project_dir=str(tmp_path))
            coder_names = [c["name"] for c in result["coder"]]
            assert "a1" in coder_names
            assert "b1" not in coder_names
        finally:
            spawn_mod.CREW_SEARCH_PATHS = original


# ---------------------------------------------------------------------------
# Bundled mission templates — verify repo missions/ dir loads correctly
# ---------------------------------------------------------------------------


class TestBundledMissions:
    """Verify the bundled mission YAML files in the repo load cleanly."""

    def test_bundled_missions_exist(self):
        from minion.missions.loader import list_missions
        # Use the default (bundled) missions dir
        repo_missions = Path(__file__).resolve().parent.parent / "missions"
        if not repo_missions.exists():
            pytest.skip("bundled missions/ dir not found")
        names = list_missions(missions_dir=repo_missions)
        assert len(names) >= 3, f"Expected at least 3 bundled missions, got {names}"

    def test_bundled_bugfix_loads(self):
        from minion.missions.loader import load_mission
        repo_missions = Path(__file__).resolve().parent.parent / "missions"
        if not repo_missions.exists():
            pytest.skip("bundled missions/ dir not found")
        m = load_mission("bugfix", missions_dir=repo_missions)
        assert m.name == "bugfix"
        assert len(m.requires) >= 3
