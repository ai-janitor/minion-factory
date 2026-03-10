"""CLI package — re-exports the Click group so `from minion.cli import cli` still works.
Entry point in pyproject.toml: minion = "minion.cli:cli"

Purpose: CLI package — re-exports the Click group so `from minion.cli import cli` still works.
Rationale: Extracted into own module for single-responsibility CLI command grouping.
Responsibility: CLI package — re-exports the Click group so `from minion.cli import cli` still works. NOT responsible for unrelated concerns.
Organization: Click command group with subcommands."""

from minion.cli.main import cli

__all__ = ["cli"]
