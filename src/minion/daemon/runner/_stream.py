"""Stream parsing — render stream-json lines, detect compaction markers.

Purpose: Stream parsing — render stream-json lines, detect compaction markers.
Rationale: Extracted into own module for single-responsibility daemon transport.
Responsibility: Stream parsing — render stream-json lines, detect compaction markers. NOT responsible for unrelated concerns.
Organization: Standalone functions and/or a single class. See source."""
from __future__ import annotations

import json
from typing import Any, List, Tuple, TYPE_CHECKING

from ..contracts import load_contract

if TYPE_CHECKING:
    from ..config import SwarmConfig


class StreamMixin:
    """Methods for parsing and rendering agent output streams."""

    config: SwarmConfig
    agent_name: str
    _invocation: int

    def _render_stream_line(self, line: str) -> Tuple[str, bool]:
        raw = line.rstrip("\n")
        if not raw:
            return "", False

        compaction = self._contains_compaction_marker(raw)

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return raw + "\n", compaction

        fragments = self._extract_text_fragments(payload)
        rendered = "".join(fragments)

        if not rendered:
            event_type = payload.get("type") if isinstance(payload, dict) else None
            if event_type in {"error", "warning"}:
                rendered = f"[{event_type}] {payload.get('message', '')}\n"

        if self._contains_compaction_marker(rendered):
            compaction = True

        if isinstance(payload, dict) and self._contains_compaction_marker(json.dumps(payload).lower()):
            compaction = True

        return rendered, compaction

    def _extract_text_fragments(self, payload: Any) -> List[str]:
        out: List[str] = []
        text_keys = {"text", "content", "delta", "output_text"}

        def walk(node: Any) -> None:
            if isinstance(node, dict):
                for key, value in node.items():
                    if key in text_keys and isinstance(value, str):
                        out.append(value)
                    else:
                        walk(value)
            elif isinstance(node, list):
                for item in node:
                    walk(item)

        walk(payload)
        return out

    def _contains_compaction_marker(self, text: str) -> bool:
        low = text.lower()
        contract = load_contract(self.config.docs_dir, "compaction-markers")
        markers = tuple(contract["substring_markers"]) if contract else (
            "compaction",
            "compacted",
            "context window",
            "summarized prior",
            "summarised prior",
            "auto-compact",
        )
        return any(marker in low for marker in markers)

    def _print_stream_start(self, command_name: str) -> None:
        self._invocation += 1
        self._log(f"stream_start: command={command_name} invocation={self._invocation}")

    def _print_stream_end(self, command_name: str, displayed_chars: int, hidden_chars: int) -> None:
        self._log(
            f"stream_end: command={command_name} invocation={self._invocation} "
            f"displayed_chars={displayed_chars} hidden_chars={hidden_chars}"
        )

    # Defined in other mixins
    def _log(self, message: str) -> None: ...
