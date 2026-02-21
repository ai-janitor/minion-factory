"""Stream parsing — render stream-json lines, detect compaction markers."""
from __future__ import annotations

import json
from datetime import datetime
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
        ts = datetime.now().strftime("%H:%M:%S")
        print(
            f"\n=== model-stream start: agent={self.agent_name} cmd={command_name} v={self._invocation} ts={ts} ===",
            flush=True,
        )

    def _print_stream_end(self, command_name: str, displayed_chars: int, hidden_chars: int) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        if hidden_chars > 0:
            print(f"\n[model-stream abbreviated: {hidden_chars} chars hidden]", flush=True)
        print(
            f"=== model-stream end: agent={self.agent_name} cmd={command_name} v={self._invocation} ts={ts} shown={displayed_chars} chars ===",
            flush=True,
        )
