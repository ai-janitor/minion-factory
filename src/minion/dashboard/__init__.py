"""Dashboard package — live TUI task board.
Re-exports run() for use by the CLI command.
No DB registration required — pure read-only consumer.

Purpose: Dashboard package — live TUI task board.
Rationale: Extracted into own module following single-responsibility principle.
Responsibility: Dashboard package — live TUI task board. NOT responsible for unrelated concerns.
Organization: Re-exports public API symbols. Imports only, no logic."""

from .loop import run

__all__ = ["run"]
