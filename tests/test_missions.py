"""Tests for the missions package — loader, resolver, party, spawn.

Purpose: Comprehensive test coverage for src/minion/missions/ (task #138, backlog #85).
Rationale: Missions compose teams from capabilities via greedy set-cover. If any
           module breaks, crew spawning fails. These tests cover happy paths, edge
           cases, validation errors, and integration across modules.
Responsibility: Validate Mission dataclass, load_mission, list_missions, _validate,
                resolve_slots, _scan_all_characters, suggest_party, resolve_and_spawn.
Organization: Grouped by module — loader, resolver, party, spawn, integration.
"""

from __future__ import annotations

import textwrap
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import yaml

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fixture: ensure auth capabilities are loaded before any missions import
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _ensure_auth_loaded():
    """Force auth module to load capabilities from YAML before each test."""
    import minion.auth as _auth
    _auth._REGISTRY_LOADED = False
    _auth._ensure_loaded()
    yield


def _valid_cap():
    """Return an arbitrary valid capability string."""
    import minion.auth as _auth
    return next(iter(_auth.VALID_CAPABILITIES))


def _all_caps():
    """Return the full set of valid capabilities."""
    import minion.auth as _auth
    return set(_auth.VALID_CAPABILITIES)


# ---------------------------------------------------------------------------
# Fixture: temporary missions directory with various YAML files
# ---------------------------------------------------------------------------


@pytest.fixture()
def missions_dir(tmp_path):
    """Create temp missions dir with valid, minimal, and broken YAMLs."""
    mdir = tmp_path / "missions"
    mdir.mkdir()

    cap = _valid_cap()

    # Valid mission with multiple capabilities
    (mdir / "full.yaml").write_text(textwrap.dedent(f"""\
        name: full
        description: Full mission with multiple caps
        requires:
          - manage
          - code
          - test
    """))

    # Minimal valid mission — single capability, no description
    (mdir / "minimal.yaml").write_text(textwrap.dedent(f"""\
        name: minimal
        requires:
          - {cap}
    """))

    # Broken — missing name key
    (mdir / "no-name.yaml").write_text(textwrap.dedent(f"""\
        description: No name field
        requires:
          - {cap}
    """))

    # Broken — requires is empty list
    (mdir / "empty-requires.yaml").write_text(textwrap.dedent("""\
        name: empty-requires
        requires: []
    """))

    # Broken — requires is a string instead of list
    (mdir / "string-requires.yaml").write_text(textwrap.dedent("""\
        name: string-requires
        requires: code
    """))

    # Broken — unknown capability
    (mdir / "bad-cap.yaml").write_text(textwrap.dedent("""\
        name: bad-cap
        requires:
          - teleportation
    """))

    return mdir


# ---------------------------------------------------------------------------
# Fixture: temporary crews directory for party/spawn tests
# ---------------------------------------------------------------------------


@pytest.fixture()
def crews_dir(tmp_path):
    """Create temp crews dir with two crew YAMLs."""
    cdir = tmp_path / "crews"
    cdir.mkdir()

    (cdir / "alpha.yaml").write_text(yaml.dump({
        "project_dir": str(tmp_path),
        "agents": {
            "alice": {"role": "lead", "system": "lead agent"},
            "bob": {"role": "coder", "system": "coder agent"},
            "carol": {"role": "recon", "system": "recon agent"},
        },
    }))

    (cdir / "beta.yaml").write_text(yaml.dump({
        "project_dir": str(tmp_path),
        "agents": {
            "dave": {"role": "coder", "system": "coder 2"},
            "eve": {"role": "auditor", "system": "auditor agent"},
        },
    }))

    # Malformed crew YAML — agents value is not a dict
    (cdir / "broken.yaml").write_text(yaml.dump({
        "project_dir": str(tmp_path),
        "agents": "not a dict",
    }))

    return cdir


# ===========================================================================
# LOADER TESTS — Mission dataclass, load_mission, list_missions, _validate
# ===========================================================================


class TestMissionDataclass:
    """Tests for the Mission frozen dataclass."""

    def test_mission_fields(self):
        from minion.missions.loader import Mission
        m = Mission(name="test", description="desc", requires=["code"])
        assert m.name == "test"
        assert m.description == "desc"
        assert m.requires == ["code"]

    def test_mission_frozen(self):
        """Mission instances should be immutable (frozen=True)."""
        from minion.missions.loader import Mission
        m = Mission(name="test", description="desc", requires=["code"])
        with pytest.raises(AttributeError):
            m.name = "changed"  # type: ignore[misc]

    def test_mission_default_requires(self):
        """requires defaults to empty list."""
        from minion.missions.loader import Mission
        m = Mission(name="test", description="desc")
        assert m.requires == []

    def test_mission_default_description(self):
        """description defaults to empty string when loaded from YAML without it."""
        from minion.missions.loader import load_mission
        # minimal.yaml has no description key — loader should use ""
        # We test this via load_mission below


class TestLoadMission:
    """Tests for missions.loader.load_mission."""

    def test_load_valid_multi_cap(self, missions_dir):
        from minion.missions.loader import load_mission
        m = load_mission("full", missions_dir=missions_dir)
        assert m.name == "full"
        assert "manage" in m.requires
        assert "code" in m.requires
        assert "test" in m.requires
        assert m.description == "Full mission with multiple caps"

    def test_load_minimal_no_description(self, missions_dir):
        """Mission without description key gets empty string."""
        from minion.missions.loader import load_mission
        m = load_mission("minimal", missions_dir=missions_dir)
        assert m.name == "minimal"
        assert m.description == ""
        assert len(m.requires) == 1

    def test_load_missing_file_raises(self, missions_dir):
        from minion.missions.loader import load_mission
        with pytest.raises(FileNotFoundError, match="nonexistent"):
            load_mission("nonexistent", missions_dir=missions_dir)

    def test_load_missing_name_raises(self, missions_dir):
        from minion.missions.loader import load_mission
        with pytest.raises(ValueError, match="missing required key: name"):
            load_mission("no-name", missions_dir=missions_dir)

    def test_load_empty_requires_raises(self, missions_dir):
        from minion.missions.loader import load_mission
        with pytest.raises(ValueError, match="non-empty 'requires'"):
            load_mission("empty-requires", missions_dir=missions_dir)

    def test_load_string_requires_raises(self, missions_dir):
        """requires must be a list, not a scalar string."""
        from minion.missions.loader import load_mission
        with pytest.raises(ValueError, match="non-empty 'requires'"):
            load_mission("string-requires", missions_dir=missions_dir)

    def test_load_unknown_capability_raises(self, missions_dir):
        from minion.missions.loader import load_mission
        with pytest.raises(ValueError, match="teleportation"):
            load_mission("bad-cap", missions_dir=missions_dir)

    def test_load_with_path_object(self, missions_dir):
        """missions_dir accepts Path objects."""
        from minion.missions.loader import load_mission
        m = load_mission("full", missions_dir=Path(missions_dir))
        assert m.name == "full"

    def test_load_with_string_path(self, missions_dir):
        """missions_dir accepts string paths."""
        from minion.missions.loader import load_mission
        m = load_mission("full", missions_dir=str(missions_dir))
        assert m.name == "full"


class TestListMissions:
    """Tests for missions.loader.list_missions."""

    def test_list_returns_sorted(self, missions_dir):
        from minion.missions.loader import list_missions
        names = list_missions(missions_dir=missions_dir)
        assert names == sorted(names)
        # Should include all .yaml files regardless of validity
        assert "full" in names
        assert "minimal" in names
        assert "bad-cap" in names

    def test_list_empty_dir(self, tmp_path):
        from minion.missions.loader import list_missions
        empty = tmp_path / "empty"
        empty.mkdir()
        assert list_missions(missions_dir=empty) == []

    def test_list_nonexistent_dir(self, tmp_path):
        from minion.missions.loader import list_missions
        result = list_missions(missions_dir=tmp_path / "nope")
        assert result == []

    def test_list_ignores_non_yaml(self, tmp_path):
        """Non-.yaml files should not appear in listing."""
        from minion.missions.loader import list_missions
        mdir = tmp_path / "mix"
        mdir.mkdir()
        (mdir / "valid.yaml").write_text(f"name: valid\nrequires:\n  - {_valid_cap()}\n")
        (mdir / "readme.txt").write_text("not a mission")
        (mdir / "data.json").write_text("{}")
        names = list_missions(missions_dir=mdir)
        assert names == ["valid"]


class TestFindMissionsDir:
    """Tests for the _find_missions_dir search path logic."""

    def test_env_var_override(self, tmp_path, monkeypatch):
        """MINION_MISSIONS_DIR env var should be respected."""
        custom = tmp_path / "custom_missions"
        custom.mkdir()
        monkeypatch.setenv("MINION_MISSIONS_DIR", str(custom))

        # Need to reload to pick up env change
        import importlib
        import minion.missions.loader as loader_mod
        importlib.reload(loader_mod)

        result = loader_mod._find_missions_dir()
        assert result == custom

    def test_fallback_to_bundled(self, monkeypatch):
        """Without env var or user dir, falls back to bundled missions/."""
        monkeypatch.delenv("MINION_MISSIONS_DIR", raising=False)

        import importlib
        import minion.missions.loader as loader_mod
        importlib.reload(loader_mod)

        result = loader_mod._find_missions_dir()
        # Should point to the repo's missions/ directory
        assert result.name == "missions"
        assert result.exists()


# ===========================================================================
# RESOLVER TESTS — resolve_slots greedy set-cover
# ===========================================================================


class TestResolveSlots:
    """Tests for missions.resolver.resolve_slots."""

    def test_always_includes_lead(self):
        from minion.missions.resolver import resolve_slots
        slots = resolve_slots({"code"})
        assert "lead" in slots

    def test_empty_set_returns_lead_only(self):
        from minion.missions.resolver import resolve_slots
        assert resolve_slots(set()) == ["lead"]

    def test_manage_only_returns_lead(self):
        """manage is a lead capability — no extra classes needed."""
        from minion.missions.resolver import resolve_slots
        assert resolve_slots({"manage"}) == ["lead"]

    def test_result_is_sorted(self):
        from minion.missions.resolver import resolve_slots
        slots = resolve_slots({"code", "build", "test"})
        assert slots == sorted(slots)

    def test_unknown_capability_raises(self):
        from minion.missions.resolver import resolve_slots
        with pytest.raises(ValueError, match="Unknown capabilities"):
            resolve_slots({"flying"})

    def test_multiple_unknown_capabilities_all_listed(self):
        from minion.missions.resolver import resolve_slots
        with pytest.raises(ValueError, match="Unknown capabilities"):
            resolve_slots({"flying", "swimming"})

    def test_covers_all_requested_capabilities(self):
        """Returned slots must cover every requested capability."""
        import minion.auth as _auth
        from minion.missions.resolver import resolve_slots

        caps = {"manage", "code", "investigate", "review"}
        slots = resolve_slots(caps)

        covered = set()
        for cls in slots:
            covered |= _auth.CLASS_CAPABILITIES.get(cls, set())
        assert caps.issubset(covered)

    def test_all_valid_capabilities_covered(self):
        """Requesting ALL valid capabilities should still produce a valid result."""
        import minion.auth as _auth
        from minion.missions.resolver import resolve_slots

        all_caps = _all_caps()
        slots = resolve_slots(all_caps)
        assert "lead" in slots

        covered = set()
        for cls in slots:
            covered |= _auth.CLASS_CAPABILITIES.get(cls, set())
        assert all_caps.issubset(covered)

    def test_no_duplicate_slots(self):
        """Slots list should not contain duplicates."""
        from minion.missions.resolver import resolve_slots
        slots = resolve_slots({"code", "test", "build", "review"})
        assert len(slots) == len(set(slots))

    def test_greedy_minimality(self):
        """Result should use few classes — at most len(caps) + 1 (lead)."""
        from minion.missions.resolver import resolve_slots
        caps = {"code", "test"}
        slots = resolve_slots(caps)
        # Should not return more classes than capabilities + lead
        assert len(slots) <= len(caps) + 1


# ===========================================================================
# PARTY TESTS — _scan_all_characters, suggest_party
# ===========================================================================


class TestScanAllCharacters:
    """Tests for missions.party._scan_all_characters."""

    def test_scans_crew_yamls(self, crews_dir, tmp_path):
        from minion.missions.party import _scan_all_characters
        import minion.crew.spawn as spawn_mod

        original = spawn_mod.CREW_SEARCH_PATHS
        spawn_mod.CREW_SEARCH_PATHS = [str(crews_dir)]
        try:
            chars = _scan_all_characters(str(tmp_path))
            names = {c["name"] for c in chars}
            assert "alice" in names
            assert "bob" in names
            assert "dave" in names
        finally:
            spawn_mod.CREW_SEARCH_PATHS = original

    def test_character_metadata(self, crews_dir, tmp_path):
        """Each character should have name, crew, role, skills."""
        from minion.missions.party import _scan_all_characters
        import minion.crew.spawn as spawn_mod

        original = spawn_mod.CREW_SEARCH_PATHS
        spawn_mod.CREW_SEARCH_PATHS = [str(crews_dir)]
        try:
            chars = _scan_all_characters(str(tmp_path))
            for c in chars:
                assert "name" in c
                assert "crew" in c
                assert "role" in c
                assert "skills" in c
        finally:
            spawn_mod.CREW_SEARCH_PATHS = original

    def test_malformed_crew_skipped(self, crews_dir, tmp_path):
        """Malformed crew YAML should be skipped without raising."""
        from minion.missions.party import _scan_all_characters
        import minion.crew.spawn as spawn_mod

        original = spawn_mod.CREW_SEARCH_PATHS
        spawn_mod.CREW_SEARCH_PATHS = [str(crews_dir)]
        try:
            # broken.yaml has agents as string — should be skipped
            chars = _scan_all_characters(str(tmp_path))
            crew_names = {c["crew"] for c in chars}
            assert "broken" not in crew_names
        finally:
            spawn_mod.CREW_SEARCH_PATHS = original

    def test_empty_search_paths(self, tmp_path):
        """No crew dirs → empty list."""
        from minion.missions.party import _scan_all_characters
        import minion.crew.spawn as spawn_mod

        original = spawn_mod.CREW_SEARCH_PATHS
        spawn_mod.CREW_SEARCH_PATHS = [str(tmp_path / "nonexistent")]
        try:
            chars = _scan_all_characters(str(tmp_path))
            assert chars == []
        finally:
            spawn_mod.CREW_SEARCH_PATHS = original


class TestSuggestParty:
    """Tests for missions.party.suggest_party."""

    def test_returns_dict_keyed_by_slot(self, crews_dir, tmp_path):
        from minion.missions.party import suggest_party
        import minion.crew.spawn as spawn_mod

        original = spawn_mod.CREW_SEARCH_PATHS
        spawn_mod.CREW_SEARCH_PATHS = [str(crews_dir)]
        try:
            result = suggest_party(["lead", "coder"], project_dir=str(tmp_path))
            assert isinstance(result, dict)
            assert "lead" in result
            assert "coder" in result
        finally:
            spawn_mod.CREW_SEARCH_PATHS = original

    def test_correct_slot_assignment(self, crews_dir, tmp_path):
        """Characters should appear in slots matching their role."""
        from minion.missions.party import suggest_party
        import minion.crew.spawn as spawn_mod

        original = spawn_mod.CREW_SEARCH_PATHS
        spawn_mod.CREW_SEARCH_PATHS = [str(crews_dir)]
        try:
            result = suggest_party(["lead", "coder"], project_dir=str(tmp_path))
            lead_names = [c["name"] for c in result["lead"]]
            coder_names = [c["name"] for c in result["coder"]]
            assert "alice" in lead_names
            assert "bob" in coder_names
            assert "dave" in coder_names
        finally:
            spawn_mod.CREW_SEARCH_PATHS = original

    def test_filter_by_crew(self, crews_dir, tmp_path):
        """crews filter should restrict to named crews only."""
        from minion.missions.party import suggest_party
        import minion.crew.spawn as spawn_mod

        original = spawn_mod.CREW_SEARCH_PATHS
        spawn_mod.CREW_SEARCH_PATHS = [str(crews_dir)]
        try:
            result = suggest_party(["coder"], crews=["alpha"], project_dir=str(tmp_path))
            coder_names = [c["name"] for c in result["coder"]]
            assert "bob" in coder_names
            assert "dave" not in coder_names  # dave is in beta
        finally:
            spawn_mod.CREW_SEARCH_PATHS = original

    def test_empty_slots_returns_empty(self, tmp_path):
        from minion.missions.party import suggest_party
        assert suggest_party([], project_dir=str(tmp_path)) == {}

    def test_slot_with_no_eligible(self, crews_dir, tmp_path):
        """A slot with no matching characters returns empty list for that slot."""
        from minion.missions.party import suggest_party
        import minion.crew.spawn as spawn_mod

        original = spawn_mod.CREW_SEARCH_PATHS
        spawn_mod.CREW_SEARCH_PATHS = [str(crews_dir)]
        try:
            result = suggest_party(["planner"], project_dir=str(tmp_path))
            assert result["planner"] == []
        finally:
            spawn_mod.CREW_SEARCH_PATHS = original


# ===========================================================================
# SPAWN TESTS — resolve_and_spawn (suggest mode + error paths)
# ===========================================================================


class TestResolveAndSpawn:
    """Tests for missions.spawn.resolve_and_spawn."""

    @pytest.fixture(autouse=True)
    def _patch_missions_dir(self, missions_dir, monkeypatch):
        """Patch _DEFAULT_MISSIONS_DIR so resolve_and_spawn finds our test YAMLs."""
        import minion.missions.loader as loader_mod
        monkeypatch.setattr(loader_mod, "_DEFAULT_MISSIONS_DIR", missions_dir)

    def test_suggest_mode_no_party_str(self, crews_dir, tmp_path):
        """Empty party_str returns suggest response with eligible chars."""
        from minion.missions.spawn import resolve_and_spawn

        import minion.crew.spawn as spawn_mod
        original = spawn_mod.CREW_SEARCH_PATHS
        spawn_mod.CREW_SEARCH_PATHS = [str(crews_dir)]
        try:
            result = resolve_and_spawn(
                mission_type="full",
                party_str="",
                crew="alpha",
                project_dir=str(tmp_path),
            )
            assert result["status"] == "suggest"
            assert result["mission"] == "full"
            assert isinstance(result["slots"], list)
            assert "eligible" in result
        finally:
            spawn_mod.CREW_SEARCH_PATHS = original

    def test_unknown_party_member_returns_error(self, crews_dir, tmp_path):
        """Requesting a nonexistent character returns error dict."""
        from minion.missions.spawn import resolve_and_spawn

        import minion.crew.spawn as spawn_mod
        original = spawn_mod.CREW_SEARCH_PATHS
        spawn_mod.CREW_SEARCH_PATHS = [str(crews_dir)]
        try:
            result = resolve_and_spawn(
                mission_type="full",
                party_str="nonexistent_agent",
                crew="alpha",
                project_dir=str(tmp_path),
            )
            assert "error" in result
            assert "nonexistent_agent" in result["error"]
        finally:
            spawn_mod.CREW_SEARCH_PATHS = original

    def test_suggest_mode_returns_slots(self, crews_dir, tmp_path):
        """Suggest mode should return the resolved slot classes."""
        from minion.missions.spawn import resolve_and_spawn

        import minion.crew.spawn as spawn_mod
        original = spawn_mod.CREW_SEARCH_PATHS
        spawn_mod.CREW_SEARCH_PATHS = [str(crews_dir)]
        try:
            result = resolve_and_spawn(
                mission_type="full",
                party_str="",
                crew="alpha,beta",
                project_dir=str(tmp_path),
            )
            assert "lead" in result["slots"]
        finally:
            spawn_mod.CREW_SEARCH_PATHS = original

    def test_suggest_mode_multi_crew_filter(self, crews_dir, tmp_path):
        """Comma-separated crew names should filter to multiple crews."""
        from minion.missions.spawn import resolve_and_spawn

        import minion.crew.spawn as spawn_mod
        original = spawn_mod.CREW_SEARCH_PATHS
        spawn_mod.CREW_SEARCH_PATHS = [str(crews_dir)]
        try:
            result = resolve_and_spawn(
                mission_type="full",
                party_str="",
                crew="alpha,beta",
                project_dir=str(tmp_path),
            )
            assert result["status"] == "suggest"
            # Should have slots and eligible keys
            assert isinstance(result["slots"], list)
            assert isinstance(result["eligible"], dict)
            # At least one eligible character across all slots
            all_names = {
                c["name"]
                for chars in result["eligible"].values()
                for c in chars
            }
            assert len(all_names) >= 1
        finally:
            spawn_mod.CREW_SEARCH_PATHS = original


# ===========================================================================
# INTEGRATION TESTS — end-to-end across modules
# ===========================================================================


class TestMissionsIntegration:
    """Integration tests: load → resolve → suggest pipeline."""

    def test_load_and_resolve_bundled_bugfix(self):
        """Load bundled bugfix.yaml and resolve its slots."""
        from minion.missions.loader import load_mission
        from minion.missions.resolver import resolve_slots
        import minion.auth as _auth

        repo_missions = Path(__file__).resolve().parent.parent / "missions"
        if not repo_missions.exists():
            pytest.skip("bundled missions/ dir not found")

        m = load_mission("bugfix", missions_dir=repo_missions)
        assert m.name == "bugfix"
        assert len(m.requires) >= 3

        slots = resolve_slots(set(m.requires))
        assert "lead" in slots

        # All required capabilities should be covered
        covered = set()
        for cls in slots:
            covered |= _auth.CLASS_CAPABILITIES.get(cls, set())
        assert set(m.requires).issubset(covered)

    def test_load_and_resolve_all_bundled(self):
        """Every bundled mission should load and resolve without error."""
        from minion.missions.loader import load_mission, list_missions
        from minion.missions.resolver import resolve_slots

        repo_missions = Path(__file__).resolve().parent.parent / "missions"
        if not repo_missions.exists():
            pytest.skip("bundled missions/ dir not found")

        names = list_missions(missions_dir=repo_missions)
        assert len(names) >= 3

        for name in names:
            m = load_mission(name, missions_dir=repo_missions)
            slots = resolve_slots(set(m.requires))
            assert "lead" in slots, f"Mission {name}: lead not in slots"

    def test_public_api_exports(self):
        """Verify __init__.py exports all public symbols."""
        import minion.missions as missions
        assert hasattr(missions, "Mission")
        assert hasattr(missions, "load_mission")
        assert hasattr(missions, "list_missions")
        assert hasattr(missions, "resolve_slots")
        assert hasattr(missions, "suggest_party")
        assert hasattr(missions, "resolve_and_spawn")
