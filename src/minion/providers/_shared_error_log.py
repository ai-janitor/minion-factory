"""Shared error log appender for all CLI providers.

Purpose: Single implementation of JSONL-style error log appending.
Rationale: SU-14 code deduplication — extracted from BaseProvider so that
           any module (providers, daemon, network) can log errors without
           importing the full provider class hierarchy.
Responsibility: append_error_log() — writes timestamped error entries to a file.
                Handles OSError/PermissionError gracefully (stderr warning, no crash).
Organization: One public function. No class dependencies.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path


def append_error_log(error_log: Path, content: str) -> None:
    """Append a timestamped error entry to the provider error log file.

    Pseudo-logic:
      1. Ensure parent directory exists (mkdir -p)
      2. Open file in append mode
      3. Write timestamp separator + content + newline
      4. On OSError/PermissionError: print warning to stderr, do not raise

    Args:
        error_log: Path to the log file (created if missing).
        content: Raw error content to append.
    """
    try:
        error_log.parent.mkdir(parents=True, exist_ok=True)
        with open(error_log, "a") as f:
            f.write(f"\n--- {datetime.now().isoformat()} ---\n")
            f.write(content)
            f.write("\n")
    except OSError as exc:
        print(f"WARNING: failed to write error log {error_log}: {exc}", file=sys.stderr)
