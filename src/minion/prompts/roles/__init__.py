"""Role-level prompt injection.
Each subdirectory owns prompts for one agent class (lead, coder, etc.).

Purpose: Role-level prompt injection.
Rationale: Extracted into own module following single-responsibility principle.
Responsibility: Role-level prompt injection. NOT responsible for unrelated concerns.
Organization: Re-exports public API symbols. Imports only, no logic."""

from __future__ import annotations

from pathlib import Path


def load_role_prompt(role: str) -> str:
    """Load prompt.md for the given role. Returns empty string if not found."""
    prompt_file = Path(__file__).parent / role / "prompt.md"
    if prompt_file.exists():
        return prompt_file.read_text().strip()
    return ""
