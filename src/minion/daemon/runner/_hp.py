"""HP tracking — extract token usage from stream-json, update HP in DB."""
from __future__ import annotations

import json
import os
import subprocess
from typing import Any, Optional, Tuple, TYPE_CHECKING

from minion.defaults import ENV_CLASS, ENV_DB_PATH, ENV_DOCS_DIR

from ._constants import (
    CLAUDE_CODE_SYSTEM_TOKENS,
    CLAUDE_CODE_TOOL_TOKENS,
    CLAUDE_CODE_PROJECT_OVERHEAD,
)

if TYPE_CHECKING:
    from ..config import SwarmConfig, AgentConfig
    from minion.providers.base import BaseProvider


class HPMixin:
    """Methods for tracking agent context health (HP)."""

    config: SwarmConfig
    agent_cfg: AgentConfig
    agent_name: str
    _context_window: int
    _tool_overhead_tokens: int
    _provider: BaseProvider
    _child_pid: int | None

    def _extract_usage(self, line: str) -> Tuple[int, int]:
        """Extract token usage from a stream-json line. Returns (input_tokens, output_tokens).

        Claude Code stream-json reports tokens split across fields:
        - input_tokens: non-cached prompt tokens (often tiny)
        - cache_creation_input_tokens: system prompt tokens being cached
        - cache_read_input_tokens: system prompt tokens read from cache
        Total context consumed = input + cache_creation + cache_read.

        The 'result' event also has modelUsage with contextWindow — we extract
        that to set the HP limit accurately.
        """
        raw = line.strip()
        if not raw or "tokens" not in raw:
            return 0, 0
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return 0, 0
        if not isinstance(data, dict):
            return 0, 0

        # Prefer modelUsage from result event — it has contextWindow too
        if data.get("type") == "result":
            # Capture session ID for resume support
            sid = data.get("session_id") or data.get("sessionId")
            if sid and isinstance(sid, str):
                self._update_session_id(sid)

            model_usage = data.get("modelUsage")
            if isinstance(model_usage, dict):
                for model_info in model_usage.values():
                    if isinstance(model_info, dict):
                        inp = (model_info.get("inputTokens", 0) or 0) + \
                              (model_info.get("cacheCreationInputTokens", 0) or 0) + \
                              (model_info.get("cacheReadInputTokens", 0) or 0)
                        out = model_info.get("outputTokens", 0) or 0
                        # Extract context window for accurate HP limit
                        ctx_window = model_info.get("contextWindow", 0)
                        if ctx_window > 0:
                            self._context_window = ctx_window
                        return inp, out

        # Fall back to usage dict in assistant/message events
        usage = self._find_usage_dict(data)
        if not usage:
            return 0, 0
        inp = (usage.get("input_tokens", 0) or 0) + \
              (usage.get("cache_creation_input_tokens", 0) or 0) + \
              (usage.get("cache_read_input_tokens", 0) or 0)
        out = usage.get("output_tokens", 0) or 0
        return inp, out

    def _find_usage_dict(self, obj: Any) -> Optional[dict]:
        """Recursively find a dict containing 'input_tokens' in a JSON structure."""
        if not isinstance(obj, dict):
            return None
        if "input_tokens" in obj:
            return obj
        for v in obj.values():
            if isinstance(v, dict):
                found = self._find_usage_dict(v)
                if found:
                    return found
        return None

    def _estimate_tool_overhead(self) -> int:
        """Estimate Claude Code system prompt + tool definition token overhead."""
        total = CLAUDE_CODE_SYSTEM_TOKENS + CLAUDE_CODE_PROJECT_OVERHEAD

        allowed = self.agent_cfg.allowed_tools
        if allowed:
            # Parse allowed tools list — e.g. "Bash Edit Read Glob Grep"
            tool_names = [t.split("(")[0].strip() for t in allowed.replace(",", " ").split()]
            for name in tool_names:
                total += CLAUDE_CODE_TOOL_TOKENS.get(name, 300)  # 300 default for unknown tools
        else:
            # All tools enabled — sum everything
            total += sum(CLAUDE_CODE_TOOL_TOKENS.values())

        return total

    def _update_hp(
        self, input_tokens: int, output_tokens: int,
        turn_input: int | None = None, turn_output: int | None = None,
    ) -> None:
        """Call minion update-hp to write observed HP to SQLite."""
        # Use API-reported context window, fall back to 200k default
        limit = self._context_window if self._context_window > 0 else 200_000
        # Subtract fixed Claude Code system prompt/tool overhead so HP% reflects
        # conversation-accumulated tokens only, not the constant bootstrap cost.
        if turn_input is not None and self._tool_overhead_tokens > 0:
            turn_input = max(0, turn_input - self._tool_overhead_tokens)
        env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
        env[ENV_CLASS] = "lead"  # Daemon has permission to write HP
        env[ENV_DB_PATH] = str(self.config.comms_db)
        env[ENV_DOCS_DIR] = str(self.config.docs_dir)
        cmd = [
            "minion", "update-hp",
            "--agent", self.agent_name,
            "--input-tokens", str(input_tokens),
            "--output-tokens", str(output_tokens),
            "--limit", str(limit),
        ]
        if turn_input is not None:
            cmd.extend(["--turn-input", str(turn_input)])
        if turn_output is not None:
            cmd.extend(["--turn-output", str(turn_output)])
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10, env=env)
            if result.returncode != 0:
                import sys
                msg = f"UPDATE-HP ERROR: exit {result.returncode} stderr={result.stderr[:200]}"
                self._log(msg)
                print(f"WARNING: [{self.agent_name}] {msg}", file=sys.stderr, flush=True)
        except Exception as exc:
            import sys
            msg = f"UPDATE-HP ERROR: {type(exc).__name__}: {exc}"
            self._log(msg)
            print(f"WARNING: [{self.agent_name}] {msg}", file=sys.stderr, flush=True)

    def _record_boot_hp(self, boot_prompt: str, result: Any) -> None:
        """Log boot token usage. Overhead estimate is input_tokens minus chars/4 — not accurate."""
        prompt_tokens = len(boot_prompt) // 4  # rough char-to-token ratio, not measured
        self._tool_overhead_tokens = max(0, result.input_tokens - prompt_tokens)
        ctx = self._context_window if self._context_window > 0 else 200_000
        self._log(
            f"boot HP: {result.input_tokens // 1000}k/{ctx // 1000}k context, "
            f"overhead≈{self._tool_overhead_tokens // 1000}k (estimate, not accurate), "
            f"prompt≈{prompt_tokens} tokens (chars/4)"
        )
        self._session_input_tokens += result.input_tokens
        self._session_output_tokens += result.output_tokens
        self._update_hp(
            self._session_input_tokens, self._session_output_tokens,
            turn_input=result.input_tokens, turn_output=result.output_tokens,
        )

    # These are defined in other mixins but referenced here for type checking
    def _update_session_id(self, session_id: str) -> None: ...
    def _log(self, message: str) -> None: ...
