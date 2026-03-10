"""Behavioral tests for missions/ — loader, resolver, party.

Purpose: Verify mission loading, slot resolution, and party suggestion
         work correctly with valid and invalid inputs.
"""

from __future__ import annotations

import os
import textwrap
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Fixture: ensure auth capabilities are loaded before resolver imports
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def ensure_auth_loaded():
    """Force auth module to load capabilities from YAML before each test."""
    import minion.auth as _auth
    _auth._REGISTRY_LOADED = False
    _auth._ensure_loaded()
    yield


def _get_valid_caps():
    """Return valid capabilities set after loading."""
    import minion.auth as _auth
    return _auth.VALID_CAPABILITIES


# ---------------------------------------------------------------------------
# Resolver — resolve_slots (pure function, no DB needed)
# ---------------------------------------------------------------------------


def test_resolve_slots_always_includes_lead():
    """resolve_slots always starts with 'lead' in the result."""
    caps = _get_valid_caps()
    cap = next(iter(caps))  # pick any valid capability
    # Re-import resolver after auth is loaded so it picks up VALID_CAPABILITIES
    import importlib
    import minion.missions.resolver as _resolver
    importlib.reload(_resolver)
    slots = _resolver.resolve_slots({cap})
    assert "lead" in slots


def test_resolve_slots_returns_sorted_list():
    """resolve_slots returns a sorted list of class names."""
    caps = _get_valid_caps()
    cap = next(iter(caps))
    import importlib
    import minion.missions.resolver as _resolver
    importlib.reload(_resolver)
    slots = _resolver.resolve_slots({cap})
    assert slots == sorted(slots)


def test_resolve_slots_unknown_capability_raises():
    """resolve_slots raises ValueError for unknown capabilities."""
    import importlib
    import minion.missions.resolver as _resolver
    importlib.reload(_resolver)
    with pytest.raises(ValueError, match="Unknown capabilities"):
        _resolver.resolve_slots({"imaginary_capability_xyz"})


def test_resolve_slots_empty_set_returns_lead_only():
    """resolve_slots with empty set returns ['lead']."""
    import importlib
    import minion.missions.resolver as _resolver
    importlib.reload(_resolver)
    slots = _resolver.resolve_slots(set())
    assert slots == ["lead"]


def test_resolve_slots_covers_all_requested():
    """resolve_slots returns enough classes to cover all requested capabilities."""
    import importlib
    import minion.missions.resolver as _resolver
    import minion.auth as _auth
    importlib.reload(_resolver)
    caps = _get_valid_caps()
    # Pick two valid capabilities
    cap_list = list(caps)[:2]
    req_caps = set(cap_list)
    slots = _resolver.resolve_slots(req_caps)
    # All requested capabilities should be covered by returned classes
    covered = set()
    for cls in slots:
        covered |= _auth.CLASS_CAPABILITIES.get(cls, set())
    assert req_caps.issubset(covered)


# ---------------------------------------------------------------------------
# Loader — mission file loading
# ---------------------------------------------------------------------------


def test_mission_loader_finds_bundled_missions():
    """Mission loader can find bundled mission YAML files."""
    from minion.missions.loader import _find_missions_dir
    missions_dir = _find_missions_dir()
    assert missions_dir.exists(), f"missions dir not found: {missions_dir}"


def test_mission_loader_loads_valid_yaml(tmp_path, monkeypatch):
    """load_mission() loads a valid mission YAML file."""
    from minion.auth import _ensure_loaded, VALID_CAPABILITIES
    _ensure_loaded()
    # Pick first valid capability
    cap = next(iter(VALID_CAPABILITIES))

    mission_yaml = textwrap.dedent(f"""\
        name: test-mission
        description: A test mission
        requires:
          - {cap}
    """)
    missions_dir = tmp_path / "missions"
    missions_dir.mkdir()
    (missions_dir / "test-mission.yaml").write_text(mission_yaml)
    monkeypatch.setenv("MINION_MISSIONS_DIR", str(missions_dir))

    from minion.missions import loader
    # Reload to pick up env var change
    import importlib
    importlib.reload(loader)

    mission = loader.load_mission("test-mission")
    assert mission.name == "test-mission"
    assert cap in mission.requires


def test_mission_loader_missing_name_raises(tmp_path, monkeypatch):
    """Loader raises ValueError when 'name' key is missing from YAML."""
    from minion.auth import _ensure_loaded, VALID_CAPABILITIES
    _ensure_loaded()
    cap = next(iter(VALID_CAPABILITIES))

    mission_yaml = textwrap.dedent(f"""\
        description: No name field
        requires:
          - {cap}
    """)
    missions_dir = tmp_path / "missions2"
    missions_dir.mkdir()
    (missions_dir / "no-name.yaml").write_text(mission_yaml)
    monkeypatch.setenv("MINION_MISSIONS_DIR", str(missions_dir))

    from minion.missions import loader
    import importlib
    importlib.reload(loader)

    with pytest.raises(ValueError, match="missing required key"):
        loader.load_mission("no-name")


def test_mission_loader_unknown_capability_raises(tmp_path, monkeypatch):
    """Loader raises ValueError for unknown capabilities in YAML."""
    mission_yaml = textwrap.dedent("""\
        name: bad-mission
        description: Bad caps
        requires:
          - nonexistent_capability_xyz
    """)
    missions_dir = tmp_path / "missions3"
    missions_dir.mkdir()
    (missions_dir / "bad-mission.yaml").write_text(mission_yaml)
    monkeypatch.setenv("MINION_MISSIONS_DIR", str(missions_dir))

    from minion.missions import loader
    import importlib
    importlib.reload(loader)

    with pytest.raises(ValueError, match="unknown capability"):
        loader.load_mission("bad-mission")


def test_list_missions_returns_list(tmp_path, monkeypatch):
    """list_missions() returns a list of available mission names."""
    from minion.auth import _ensure_loaded, VALID_CAPABILITIES
    _ensure_loaded()
    cap = next(iter(VALID_CAPABILITIES))

    missions_dir = tmp_path / "missions4"
    missions_dir.mkdir()
    for name in ("alpha", "beta"):
        (missions_dir / f"{name}.yaml").write_text(
            f"name: {name}\ndescription: {name} mission\nrequires:\n  - {cap}\n"
        )
    monkeypatch.setenv("MINION_MISSIONS_DIR", str(missions_dir))

    from minion.missions import loader
    import importlib
    importlib.reload(loader)

    missions = loader.list_missions()
    assert isinstance(missions, list)
    assert len(missions) >= 2
