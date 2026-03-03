"""CLI package — re-exports the Click group so `from minion.cli import cli` still works.

Entry point in pyproject.toml: minion = "minion.cli:cli"
"""

from minion.cli.main import cli

__all__ = ["cli"]
