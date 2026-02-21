"""Build the history block for post-compaction context recovery."""

from __future__ import annotations

from pathlib import Path

from minion.daemon.contracts import load_contract


def build_history_block(docs_dir: Path, snapshot: str) -> str:
    """Format rolling buffer snapshot as a history block."""
    contract = load_contract(docs_dir, "compaction-markers")
    if contract and "history_block" in contract:
        hb = contract["history_block"]
        return "\n".join([
            hb["header"],
            hb["preamble"],
            snapshot,
            hb["footer"],
        ])
    return "\n".join(
        [
            "════════════════════ RECENT HISTORY (rolling buffer) ════════════════════",
            "The following is your captured stream-json history from before compaction.",
            "Use it to restore recent context and avoid redoing completed work.",
            "══════════════════════════════════════════════════════════════════════════",
            snapshot,
            "═══════════════════════ END RECENT HISTORY ═════════════════════════════",
        ]
    )
