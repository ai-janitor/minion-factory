"""Role-level prompt injection.

Each subdirectory owns prompts for one agent class (lead, coder, etc.).
"""

from __future__ import annotations

from pathlib import Path


def load_role_prompt(role: str) -> str:
    """Load prompt.md for the given role. Returns empty string if not found."""
    prompt_file = Path(__file__).parent / role / "prompt.md"
    if prompt_file.exists():
        return prompt_file.read_text().strip()
    return ""
