"""Parse YAML frontmatter from intel markdown docs."""

from __future__ import annotations

import logging
import re

log = logging.getLogger(__name__)

_FM_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)

_DEFAULTS: dict[str, object] = {
    "tags": [],
    "linked_tasks": [],
    "linked_reqs": [],
    "author": "",
    "date": "",
}


def _parse_frontmatter(path: str) -> dict[str, object]:
    """Extract YAML frontmatter from a markdown file and return typed fields.

    Returns defaults for any missing key. Never raises — logs and returns
    defaults on parse error or missing file.
    """
    result: dict[str, object] = {k: list(v) if isinstance(v, list) else v for k, v in _DEFAULTS.items()}
    try:
        with open(path, encoding="utf-8") as fh:
            content = fh.read()
    except OSError as exc:
        log.warning("_parse_frontmatter: cannot read %s: %s", path, exc)
        return result

    m = _FM_PATTERN.match(content)
    if not m:
        return result

    try:
        import yaml  # pyyaml — confirmed in pyproject.toml deps
        data = yaml.safe_load(m.group(1)) or {}
    except Exception as exc:
        log.warning("_parse_frontmatter: YAML parse error in %s: %s", path, exc)
        return result

    if not isinstance(data, dict):
        return result

    # tags — list[str]
    tags = data.get("tags", [])
    result["tags"] = [str(t) for t in tags] if isinstance(tags, list) else []

    # linked_tasks — list[int]
    lt = data.get("linked_tasks", [])
    result["linked_tasks"] = [int(x) for x in lt if str(x).isdigit()] if isinstance(lt, list) else []

    # linked_reqs — list[int]
    lr = data.get("linked_reqs", [])
    result["linked_reqs"] = [int(x) for x in lr if str(x).isdigit()] if isinstance(lr, list) else []

    result["author"] = str(data.get("author", ""))
    result["date"] = str(data.get("date", ""))

    return result
