"""Capability-level prompt injection.

Each subdirectory owns prompts for one capability (code, build, test, etc.).
Agents get prompts injected for every capability their class grants.
"""

from __future__ import annotations

from pathlib import Path
from typing import List


def load_capability_prompts(capabilities: set[str]) -> str:
    """Load and merge prompt text for all given capabilities.

    Reads prompt.md from each capability's directory. Returns
    concatenated text, one section per capability, empty string
    if no prompts found.
    """
    cap_dir = Path(__file__).parent
    sections: List[str] = []
    for cap in sorted(capabilities):
        prompt_file = cap_dir / cap / "prompt.md"
        if prompt_file.exists():
            text = prompt_file.read_text().strip()
            if text:
                sections.append(text)
    return "\n\n".join(sections)
