"""Verify the minion console script entry point resolves.

Purpose: Verify the minion console script entry point resolves.
Rationale: Test coverage for the corresponding module.
Responsibility: Verify the minion console script entry point resolves. NOT responsible for unrelated concerns.
Organization: One TestClass per concern, or standalone test functions."""
import pytest
from minion.cli import cli

pytestmark = pytest.mark.unit


def test_cli_callable():
    assert callable(cli)


def test_entrypoint_metadata():
    """Verify the 'minion' entry point is declared in package metadata."""
    import sys
    if sys.version_info >= (3, 12):
        from importlib.metadata import entry_points
        eps = entry_points(group="console_scripts")
        names = [ep.name for ep in eps]
    else:
        from importlib.metadata import entry_points
        eps = entry_points().get("console_scripts", [])
        names = [ep.name for ep in eps]
    assert "minion" in names, f"'minion' entry point not found in: {names}"
