"""Tests for daemon permission_mode default — bypassPermissions when not set.

Purpose: Verify that _parse_agents() defaults permission_mode to bypassPermissions
for daemon agents that don't explicitly set it in the crew YAML. This prevents
headless daemons from hitting permission prompts with no human to approve.

Rationale: Regression test for bug crew-spawn-daemons-blocked-by-permission-prompts.
Responsibility: Tests for permission_mode defaulting logic. NOT responsible for
other config parsing concerns."""

from __future__ import annotations

import pytest

from minion.crew.config import _parse_agents

pytestmark = pytest.mark.unit


def test_permission_mode_defaults_to_bypass_when_not_set():
    """Agents without explicit permission_mode get bypassPermissions."""
    agents_raw = {
        "worker1": {
            "role": "coder",
            "provider": "claude",
        },
    }
    result = _parse_agents(agents_raw, system_prefix="")
    assert result["worker1"].permission_mode == "bypassPermissions"


def test_permission_mode_preserved_when_explicitly_set():
    """Agents that explicitly set permission_mode keep their value."""
    agents_raw = {
        "worker1": {
            "role": "coder",
            "provider": "claude",
            "permission_mode": "allowedTools",
        },
    }
    result = _parse_agents(agents_raw, system_prefix="")
    assert result["worker1"].permission_mode == "allowedTools"


def test_permission_mode_defaults_when_set_to_empty_string():
    """Empty string permission_mode falls through to the default."""
    agents_raw = {
        "worker1": {
            "role": "coder",
            "provider": "claude",
            "permission_mode": "",
        },
    }
    result = _parse_agents(agents_raw, system_prefix="")
    assert result["worker1"].permission_mode == "bypassPermissions"


def test_permission_mode_defaults_when_set_to_whitespace():
    """Whitespace-only permission_mode falls through to the default."""
    agents_raw = {
        "worker1": {
            "role": "coder",
            "provider": "claude",
            "permission_mode": "   ",
        },
    }
    result = _parse_agents(agents_raw, system_prefix="")
    assert result["worker1"].permission_mode == "bypassPermissions"


def test_multiple_agents_each_get_default():
    """All agents without explicit permission_mode get the default."""
    agents_raw = {
        "coder1": {"role": "coder", "provider": "claude"},
        "builder1": {"role": "builder", "provider": "claude"},
        "lead1": {
            "role": "lead",
            "provider": "claude",
            "permission_mode": "allowedTools",
        },
    }
    result = _parse_agents(agents_raw, system_prefix="")
    assert result["coder1"].permission_mode == "bypassPermissions"
    assert result["builder1"].permission_mode == "bypassPermissions"
    assert result["lead1"].permission_mode == "allowedTools"
