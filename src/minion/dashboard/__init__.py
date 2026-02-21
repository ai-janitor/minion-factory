"""Dashboard package — live TUI task board.

Re-exports run() for use by the CLI command.
No DB registration required — pure read-only consumer.
"""

from .loop import run

__all__ = ["run"]
