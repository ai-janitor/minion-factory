"""Behavioral tests for auth.py — class gating, TOOL_CATALOG, staleness, triggers.

Purpose: Verify auth module's public surface: get_agent_class, get_tools_for_class,
         require_class decorator, TOOL_CATALOG membership, staleness constants,
         and classes_with capability lookups.
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# get_agent_class — reads MINION_CLASS env var, defaults to 'lead'
# ---------------------------------------------------------------------------


def test_get_agent_class_defaults_to_lead(monkeypatch):
    """When MINION_CLASS is not set, get_agent_class returns 'lead'."""
    monkeypatch.delenv("MINION_CLASS", raising=False)
    from minion.auth import get_agent_class
    assert get_agent_class() == "lead"


def test_get_agent_class_reads_env(monkeypatch):
    """When MINION_CLASS is set, get_agent_class returns that value."""
    monkeypatch.setenv("MINION_CLASS", "coder")
    from minion.auth import get_agent_class
    assert get_agent_class() == "coder"


# ---------------------------------------------------------------------------
# VALID_CLASSES — hardcoded fallback set
# ---------------------------------------------------------------------------


def test_valid_classes_contains_expected():
    """VALID_CLASSES contains the 7 canonical role names."""
    from minion.auth import VALID_CLASSES
    for cls in ("lead", "coder", "builder", "oracle", "recon", "planner", "auditor"):
        assert cls in VALID_CLASSES


# ---------------------------------------------------------------------------
# TOOL_CATALOG — class membership and structure
# ---------------------------------------------------------------------------


def test_tool_catalog_is_dict_with_tuples():
    """TOOL_CATALOG values are (set, str) tuples."""
    from minion.auth import TOOL_CATALOG
    for cmd, entry in TOOL_CATALOG.items():
        assert isinstance(entry, tuple), f"{cmd}: expected tuple, got {type(entry)}"
        classes, desc = entry
        assert isinstance(classes, set), f"{cmd}: classes should be set"
        assert isinstance(desc, str), f"{cmd}: description should be str"


def test_tool_catalog_lead_only_commands():
    """Commands marked lead-only are not accessible to coder."""
    from minion.auth import TOOL_CATALOG
    lead_only = [cmd for cmd, (classes, _) in TOOL_CATALOG.items() if classes == {"lead"}]
    assert len(lead_only) > 0, "expected some lead-only commands"
    for cmd in lead_only:
        classes, _ = TOOL_CATALOG[cmd]
        assert "coder" not in classes, f"{cmd} should not be accessible to coder"


def test_all_classes_can_check_inbox():
    """check-inbox is available to all registered classes."""
    from minion.auth import TOOL_CATALOG, VALID_CLASSES
    classes, _ = TOOL_CATALOG["check-inbox"]
    assert classes == VALID_CLASSES


# ---------------------------------------------------------------------------
# get_tools_for_class — returns filtered list of tool dicts
# ---------------------------------------------------------------------------


def test_get_tools_for_class_returns_list():
    """get_tools_for_class returns a non-empty list of dicts."""
    from minion.auth import get_tools_for_class
    tools = get_tools_for_class("lead")
    assert isinstance(tools, list)
    assert len(tools) > 0


def test_get_tools_for_class_dicts_have_command_and_description():
    """Each tool dict has 'command' and 'description' keys."""
    from minion.auth import get_tools_for_class
    for tool in get_tools_for_class("coder"):
        assert "command" in tool
        assert "description" in tool


def test_get_tools_for_class_coder_excludes_lead_only():
    """coder class does not see lead-only commands."""
    from minion.auth import get_tools_for_class
    coder_commands = {t["command"] for t in get_tools_for_class("coder")}
    lead_commands = {t["command"] for t in get_tools_for_class("lead")}
    # lead-only commands like 'minion rename' should be absent from coder's list
    assert "minion rename" not in coder_commands
    # but all coder commands should be in lead's list (lead is superset)
    # (lead has VALID_CLASSES which includes itself)
    assert len(lead_commands) >= len(coder_commands)


# ---------------------------------------------------------------------------
# CLASS_STALENESS_SECONDS — reasonable values
# ---------------------------------------------------------------------------


def test_staleness_seconds_all_positive():
    """All staleness thresholds are positive integers."""
    from minion.auth import CLASS_STALENESS_SECONDS
    for cls, secs in CLASS_STALENESS_SECONDS.items():
        assert isinstance(secs, int) and secs > 0, f"{cls}: {secs}"


def test_staleness_seconds_coder_shorter_than_lead():
    """Coder has shorter staleness window than lead (coders must be more responsive)."""
    from minion.auth import CLASS_STALENESS_SECONDS
    assert CLASS_STALENESS_SECONDS["coder"] < CLASS_STALENESS_SECONDS["lead"]


# ---------------------------------------------------------------------------
# TASK_STATUSES — expected states present
# ---------------------------------------------------------------------------


def test_task_statuses_contains_lifecycle_states():
    """TASK_STATUSES includes all expected DAG states."""
    from minion.auth import TASK_STATUSES
    for status in ("open", "assigned", "in_progress", "fixed", "verified", "closed"):
        assert status in TASK_STATUSES


# ---------------------------------------------------------------------------
# BATTLE_PLAN_STATUSES — valid set
# ---------------------------------------------------------------------------


def test_battle_plan_statuses_non_empty():
    """BATTLE_PLAN_STATUSES is a non-empty set of strings."""
    from minion.auth import BATTLE_PLAN_STATUSES
    assert isinstance(BATTLE_PLAN_STATUSES, set)
    assert len(BATTLE_PLAN_STATUSES) > 0
    assert "active" in BATTLE_PLAN_STATUSES


# ---------------------------------------------------------------------------
# classes_with — capability → class set
# ---------------------------------------------------------------------------


def test_classes_with_known_capability():
    """classes_with returns a non-empty set for a known capability."""
    from minion.auth import classes_with, CAP_CODE
    result = classes_with(CAP_CODE)
    assert isinstance(result, set)
    assert len(result) > 0
    assert "coder" in result


def test_classes_with_unknown_capability_raises():
    """classes_with raises ValueError for an unknown capability."""
    from minion.auth import classes_with
    with pytest.raises(ValueError, match="Unknown capability"):
        classes_with("totally_fake_capability_xyz")


# ---------------------------------------------------------------------------
# SCOPE_RESTRICTIONS — structure check
# ---------------------------------------------------------------------------


def test_scope_restrictions_has_sys_scope():
    """SCOPE_RESTRICTIONS has 'sys' scope with non-empty restriction set."""
    from minion.auth import SCOPE_RESTRICTIONS
    assert "sys" in SCOPE_RESTRICTIONS
    assert isinstance(SCOPE_RESTRICTIONS["sys"], set)
    assert len(SCOPE_RESTRICTIONS["sys"]) > 0


def test_scope_restrictions_project_is_empty():
    """'project' scope has no restrictions (all commands allowed)."""
    from minion.auth import SCOPE_RESTRICTIONS
    assert SCOPE_RESTRICTIONS.get("project", set()) == set()
