"""Load shared contract JSON files from docs/contracts/."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional


def load_contract(docs_dir: str | Path, name: str) -> Optional[dict[str, Any]]:
    """Read {docs_dir}/contracts/{name}.json, return parsed dict or None."""
    path = Path(docs_dir) / "contracts" / f"{name}.json"
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
