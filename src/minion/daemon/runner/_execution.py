"""Agent execution — run commands, handle resume, process prompts."""
from __future__ import annotations

import os
import queue
import subprocess
import threading
import time
from typing import Any, List, Optional, TYPE_CHECKING

from minion.defaults import ENV_CLASS, ENV_DB_PATH, ENV_DOCS_DIR

from ._constants import AgentRunResult, MAX_CONSOLE_STREAM_CHARS

from ..triggers import handle_phoenix_down

if TYPE_CHECKING:
    from ..config import SwarmConfig, AgentConfig
    from ..buffer import RollingBuffer
    from minion.providers.base import BaseProvider


class ExecutionMixin:
    """Methods for running the agent subprocess and processing results."""

    config: SwarmConfig
    agent_cfg: AgentConfig
    agent_name: str
    buffer: RollingBuffer
    resume_ready: bool
    inject_history_next_turn: bool
    consecutive_failures: int
    last_error: Optional[str]
    _stop_event: threading.Event
    _child_pid: int | None
    _invocation_row_id: int | None
    _session_input_tokens: int
    _session_output_tokens: int
    _tool_overhead_tokens: int
    _context_window: int
    _provider: BaseProvider
    _error_log: Any

    def _run_agent(self, prompt: str) -> AgentRunResult:
        provider = self._provider
        cmd = provider.build_command(prompt, use_resume=False)
        if provider.supports_resume:
            return self._run_with_optional_resume(
                resume_cmd=provider.build_command(prompt, use_resume=True),
                fresh_cmd=cmd,
                resume_label=provider.resume_label,
            )
        return self._run_command(cmd)

    def _run_with_optional_resume(self, resume_cmd: List[str], fresh_cmd: List[str], resume_label: str) -> AgentRunResult:
        if self.resume_ready:
            resumed = self._run_command(resume_cmd)
            if resumed.timed_out or resumed.exit_code == 0:
                return resumed
            self.resume_ready = False
            self._log(f"{resume_label} failed with exit {resumed.exit_code}; retrying without resume")

        return self._run_command(fresh_cmd)

    def _run_command(self, cmd: List[str]) -> AgentRunResult:
        self._log(f"exec: {cmd[0]} ({self.agent_cfg.provider})")
        self._print_stream_start(cmd[0])

        # Strip CLAUDECODE env var so nested claude sessions don't refuse to start
        env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
        env[ENV_CLASS] = self.agent_cfg.role or "coder"
        env[ENV_DB_PATH] = str(self.config.comms_db)
        env[ENV_DOCS_DIR] = str(self.config.docs_dir)

        try:
            proc = subprocess.Popen(
                cmd,
                cwd=str(self.config.project_dir),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env=env,
            )
            self._child_pid = proc.pid
            self._update_child_pid_in_db()
            self._invocation_row_id = self._insert_invocation_start()
        except FileNotFoundError:
            self._log(f"command not found: {cmd[0]}")
            return AgentRunResult(exit_code=127, timed_out=False, compaction_detected=False, command_name=cmd[0])
        except Exception as exc:
            self._log(f"failed to launch {cmd[0]}: {exc}")
            return AgentRunResult(exit_code=127, timed_out=False, compaction_detected=False, command_name=cmd[0])

        q: "queue.Queue[Optional[str]]" = queue.Queue()

        def _reader() -> None:
            assert proc.stdout is not None
            for line in proc.stdout:
                q.put(line)
            q.put(None)

        t = threading.Thread(target=_reader, daemon=True)
        t.start()

        # Raw stream log — full stream-json for context inspection
        stream_log = self.config.logs_dir / f"{self.agent_name}.stream.jsonl"
        stream_fp = open(stream_log, "a")

        timed_out = False
        interrupted = False
        compaction_detected = False
        last_output_at = time.monotonic()
        last_interrupt_check = time.monotonic()
        displayed_chars = 0
        hidden_chars = 0
        total_input_tokens = 0
        total_output_tokens = 0

        while True:
            try:
                line = q.get(timeout=1.0)
            except queue.Empty:
                if proc.poll() is not None and q.empty():
                    break
                if time.monotonic() - last_output_at > self.agent_cfg.no_output_timeout_sec:
                    timed_out = True
                    proc.terminate()
                    break
                # Check interrupt flag every ~2s to avoid DB spam
                if time.monotonic() - last_interrupt_check > 2.0:
                    last_interrupt_check = time.monotonic()
                    if self._check_interrupt():
                        self._log("interrupt flag detected — terminating child process")
                        interrupted = True
                        proc.terminate()
                        break
                continue

            if line is None:
                break

            last_output_at = time.monotonic()
            self.buffer.append(line)
            stream_fp.write(line)  # Full unfiltered line to stream log
            stream_fp.flush()

            # Filter through provider before rendering (catches verbose errors)
            filtered_line = self._provider.filter_log_line(line, self._error_log)
            rendered, has_compaction = self._render_stream_line(filtered_line)

            # Extract token usage from stream-json (last value wins —
            # result event comes last with full totals including cache)
            inp, out = self._extract_usage(line)
            if inp > 0:
                total_input_tokens = inp
            if out > 0:
                total_output_tokens = out

            if rendered:
                remaining = MAX_CONSOLE_STREAM_CHARS - displayed_chars
                if remaining > 0:
                    chunk = rendered[:remaining]
                    print(chunk, end="", flush=True)
                    displayed_chars += len(chunk)
                else:
                    chunk = ""
                hidden_chars += len(rendered) - len(chunk)
            if has_compaction:
                compaction_detected = True

        stream_fp.close()

        if (timed_out or interrupted) and proc.poll() is None:
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

        try:
            exit_code = proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            proc.kill()
            exit_code = proc.wait(timeout=5)

        self._print_stream_end(cmd[0], displayed_chars=displayed_chars, hidden_chars=hidden_chars)
        result = AgentRunResult(
            exit_code=exit_code,
            timed_out=timed_out,
            compaction_detected=compaction_detected,
            command_name=cmd[0],
            input_tokens=total_input_tokens,
            output_tokens=total_output_tokens,
            interrupted=interrupted,
        )
        self._finalize_invocation(result)
        return result

    def _process_prompt(self, prompt: str) -> bool:
        """Run the agent with a prompt and handle the result."""
        result = self._run_agent(prompt)

        # Track session-cumulative HP and write to DB
        if result.input_tokens > 0 or result.output_tokens > 0:
            self._session_input_tokens += result.input_tokens
            self._session_output_tokens += result.output_tokens
            self._update_hp(
                self._session_input_tokens, self._session_output_tokens,
                turn_input=result.input_tokens, turn_output=result.output_tokens,
            )

            # Context death detection — agent burned through context window
            ctx = self._context_window if self._context_window > 0 else 200_000
            turn_used = result.input_tokens
            if self._tool_overhead_tokens > 0:
                turn_used = max(0, turn_used - self._tool_overhead_tokens)
            hp_pct = max(0.0, 100 - (turn_used / ctx * 100)) if ctx > 0 else 0.0
            if hp_pct <= 5:
                handle_phoenix_down(
                    self.agent_name, hp_pct,
                    self._write_state, self._stop_event, self._alert_lead_poll,
                )
                return True  # invocation itself succeeded, but agent is cooked

        if result.interrupted:
            self._log("invocation interrupted by lead — returning to poll loop")
            return True

        if result.compaction_detected:
            self.inject_history_next_turn = True
            self._log("detected context compaction marker; history will be re-injected next cycle")
            # Log compaction event with token counts
            self._log_compaction(
                tokens_pre=self._session_input_tokens,
                tokens_post=result.input_tokens,
            )

        if result.timed_out:
            self.last_error = f"{self.agent_cfg.provider} produced no output for {self.agent_cfg.no_output_timeout_sec}s"
            return False

        if result.exit_code != 0:
            self.last_error = f"{result.command_name} exited with code {result.exit_code}"
            return False

        self.resume_ready = True
        return True

    # Defined in other mixins
    def _log(self, message: str) -> None: ...
    def _write_state(self, status: str, **extra: Any) -> None: ...
    def _alert_lead_poll(self, message: str) -> None: ...
    def _update_hp(self, input_tokens: int, output_tokens: int, turn_input: int | None = None, turn_output: int | None = None) -> None: ...
    def _extract_usage(self, line: str) -> tuple: ...
    def _render_stream_line(self, line: str) -> tuple: ...
    def _print_stream_start(self, command_name: str) -> None: ...
    def _print_stream_end(self, command_name: str, displayed_chars: int, hidden_chars: int) -> None: ...
    def _update_child_pid_in_db(self) -> None: ...
    def _insert_invocation_start(self) -> int | None: ...
    def _finalize_invocation(self, result: AgentRunResult) -> None: ...
    def _check_interrupt(self) -> bool: ...
    def _log_compaction(self, tokens_pre: int, tokens_post: int) -> None: ...
