"""Crew install — copy source crews/*.yaml to ~/.minion-swarm/.

Purpose: Refresh installed crew yamls from the minion-factory source checkout.
Rationale: Backlog #337 — without an install path, ~/.minion-swarm/<crew>.yaml
drifts from the source repo (e.g. set-status fixes from #326 didn't reach the
operator's installed copy until they manually `cp`'d). This module ships a
single `install_crews()` function exposed as `minion crew install`.
Responsibility: locate source crews dir, list yamls, compare timestamps,
copy when source is newer (or always with --force). NOT responsible for crew
yaml validation or schema migration.
Organization: one public function plus a private source-resolver helper.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any, Optional


def _resolve_source_dir(explicit: str = "") -> Optional[Path]:
    """Resolve the source crews/ directory.

    Resolution order:
      1. Explicit --source path passed by caller
      2. MINION_SOURCE_DIR env var (treated as repo root, append crews/)
      3. Walk up from this module's location to find a crews/ sibling
      4. None — caller must report.
    """
    if explicit:
        p = Path(explicit).expanduser().resolve()
        return p if p.is_dir() else None

    env = os.environ.get("MINION_SOURCE_DIR")
    if env:
        p = Path(env).expanduser().resolve() / "crews"
        if p.is_dir():
            return p

    # Walk up from this file looking for a crews/ sibling next to a src/ dir.
    here = Path(__file__).resolve()
    for parent in here.parents:
        cand = parent / "crews"
        if cand.is_dir() and (parent / "src" / "minion").is_dir():
            return cand
    return None


def install_crews(
    source: str = "",
    dest: str = "",
    force: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Copy source crew yamls to the destination, with drift reporting.

    Args:
        source: Override source crews/ dir. Empty = autodetect.
        dest: Override destination dir. Empty = ~/.minion-swarm/.
        force: Overwrite even when dest file mtime >= source mtime.
        dry_run: Report what would happen without writing.

    Returns:
        Status dict with copied/skipped/conflicts/source/dest fields.
    """
    src_dir = _resolve_source_dir(source)
    if src_dir is None:
        return {
            "error": "Could not locate source crews/ directory. "
            "Pass --source <path> or set MINION_SOURCE_DIR.",
        }

    dest_dir = Path(dest).expanduser().resolve() if dest else Path.home() / ".minion-swarm"
    if not dry_run:
        dest_dir.mkdir(parents=True, exist_ok=True)

    copied: list[str] = []
    skipped_unchanged: list[str] = []
    skipped_newer: list[str] = []  # dest is newer than source — don't clobber
    overwrote: list[str] = []

    yamls = sorted(p for p in src_dir.iterdir() if p.suffix == ".yaml")
    for src_file in yamls:
        dest_file = dest_dir / src_file.name

        if not dest_file.exists():
            if not dry_run:
                shutil.copy2(src_file, dest_file)
            copied.append(src_file.name)
            continue

        # Both exist — compare content first (cheap, exact)
        try:
            same = src_file.read_bytes() == dest_file.read_bytes()
        except OSError:
            same = False

        if same:
            skipped_unchanged.append(src_file.name)
            continue

        # Different content — decide whether to overwrite
        src_mtime = src_file.stat().st_mtime
        dest_mtime = dest_file.stat().st_mtime
        if dest_mtime > src_mtime and not force:
            skipped_newer.append(src_file.name)
            continue

        if not dry_run:
            shutil.copy2(src_file, dest_file)
        overwrote.append(src_file.name)

    return {
        "status": "dry-run" if dry_run else "installed",
        "source": str(src_dir),
        "dest": str(dest_dir),
        "copied": copied,
        "overwrote": overwrote,
        "skipped_unchanged": skipped_unchanged,
        "skipped_newer_in_dest": skipped_newer,
        "summary": (
            f"{len(copied)} new, {len(overwrote)} overwritten, "
            f"{len(skipped_unchanged)} unchanged, {len(skipped_newer)} kept "
            f"(dest newer — pass --force to overwrite)"
        ),
    }
