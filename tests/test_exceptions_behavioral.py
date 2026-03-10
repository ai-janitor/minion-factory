"""Behavioral tests for exceptions.py — exception hierarchy and Result TypedDict.

Purpose: Verify MinionError hierarchy catches correctly, subclasses preserve messages,
         and the Result TypedDict accepts expected keys.
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# MinionError — base class catch
# ---------------------------------------------------------------------------


def test_minion_error_is_base():
    """MinionError is a subclass of Exception."""
    from minion.exceptions import MinionError
    assert issubclass(MinionError, Exception)


def test_minion_error_carries_message():
    """MinionError carries its message as the first arg."""
    from minion.exceptions import MinionError
    err = MinionError("something broke")
    assert str(err) == "something broke"


# ---------------------------------------------------------------------------
# Subclass hierarchy — can catch with MinionError
# ---------------------------------------------------------------------------


def _subclasses():
    from minion.exceptions import (
        MinionNotFoundError,
        MinionPermissionError,
        MinionConfigError,
        MinionStateError,
        MinionDBError,
    )
    return [
        MinionNotFoundError,
        MinionPermissionError,
        MinionConfigError,
        MinionStateError,
        MinionDBError,
    ]


@pytest.mark.parametrize("ExcCls", _subclasses())
def test_subclass_caught_by_minion_error(ExcCls):
    """All MinionError subclasses can be caught as MinionError."""
    from minion.exceptions import MinionError
    with pytest.raises(MinionError):
        raise ExcCls("test message")


@pytest.mark.parametrize("ExcCls", _subclasses())
def test_subclass_is_subclass_of_minion_error(ExcCls):
    """Each subclass inherits from MinionError."""
    from minion.exceptions import MinionError
    assert issubclass(ExcCls, MinionError)


@pytest.mark.parametrize("ExcCls", _subclasses())
def test_subclass_carries_message(ExcCls):
    """Each subclass preserves the error message."""
    err = ExcCls("specific error")
    assert "specific error" in str(err)


# ---------------------------------------------------------------------------
# MinionNotFoundError — semantic use
# ---------------------------------------------------------------------------


def test_not_found_error_distinct_from_permission_error():
    """MinionNotFoundError and MinionPermissionError are distinct types."""
    from minion.exceptions import MinionNotFoundError, MinionPermissionError
    assert MinionNotFoundError is not MinionPermissionError


# ---------------------------------------------------------------------------
# Result TypedDict — structural check
# ---------------------------------------------------------------------------


def test_result_typed_dict_accepts_status_and_message():
    """Result TypedDict can be constructed with status and message."""
    from minion.exceptions import Result
    r: Result = {"status": "ok", "message": "done"}
    assert r["status"] == "ok"
    assert r["message"] == "done"


def test_result_typed_dict_partial_construction():
    """Result TypedDict allows partial construction (all keys total=False)."""
    from minion.exceptions import Result
    r: Result = {"status": "error", "error": "not found"}
    assert r["status"] == "error"
    assert r["error"] == "not found"
