"""Role-level prompt injection.
Each subdirectory owns prompts for one agent class (lead, coder, etc.).
Shared blocks (like self-service chore instructions) live as _*.md partials
in this directory and are expanded via {{TEMPLATE_NAME}} markers in prompt.md files.

Purpose: Role-level prompt injection.
Rationale: Extracted into own module following single-responsibility principle.
Responsibility: Role-level prompt injection. NOT responsible for unrelated concerns.
Organization: Re-exports public API symbols. Imports only, no logic."""

from __future__ import annotations

from pathlib import Path

# Cache for shared partial content to avoid re-reading on every prompt load
_PARTIALS_CACHE: dict[str, str] = {}

_ROLES_DIR = Path(__file__).parent


def _load_partial(name: str) -> str:
    """Load a shared partial template from _<name>.md in the roles directory."""
    if name not in _PARTIALS_CACHE:
        partial_file = _ROLES_DIR / f"_{name}.md"
        if partial_file.exists():
            _PARTIALS_CACHE[name] = partial_file.read_text().strip()
        else:
            _PARTIALS_CACHE[name] = ""
    return _PARTIALS_CACHE[name]


def _expand_partials(text: str) -> str:
    """Replace {{PARTIAL_NAME}} markers with content from _partial_name.md files.

    Marker format: {{SELF_SERVICE_CHORE_BLOCK}} → loads _self_service_chore_block.md.
    Unknown markers are left as-is.
    """
    import re
    def _replacer(match):
        marker = match.group(1)
        # Convert UPPER_SNAKE to lower_snake for filename lookup
        partial_name = marker.lower()
        content = _load_partial(partial_name)
        return content if content else match.group(0)
    return re.sub(r"\{\{([A-Z_]+)\}\}", _replacer, text)


def load_role_prompt(role: str) -> str:
    """Load prompt.md for the given role, expanding shared partials.

    Returns empty string if the role directory or prompt.md is not found.
    """
    prompt_file = _ROLES_DIR / role / "prompt.md"
    if prompt_file.exists():
        raw = prompt_file.read_text().strip()
        return _expand_partials(raw)
    return ""
