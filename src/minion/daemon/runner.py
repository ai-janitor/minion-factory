from __future__ import annotations

import json
import os
import platform
import queue
import resource
import signal
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from minion.defaults import ENV_CLASS, ENV_DB_PATH, ENV_DOCS_DIR

from .buffer import RollingBuffer
from .config import SwarmConfig
from .contracts import load_contract
from .watcher import CommsWatcher
from minion.providers import get_provider

# Load max_console_stream_chars from contract, fallback to 12k
_cfg_defaults = load_contract(
    os.getenv("MINION_DOCS_DIR", os.path.expanduser("~/.minion_work/docs")),
    "config-defaults",
)
MAX_CONSOLE_STREAM_CHARS = (_cfg_defaults or {}).get("max_console_stream_chars", 12_000)

# Claude Code system prompt + tool definitions token costs (approximate).
# Each tool's JSON schema + description consumes context tokens.
# These are injected by Claude Code before the agent's prompt.
CLAUDE_CODE_SYSTEM_TOKENS = 3_500   # Base system prompt (instructions, rules, formatting)
CLAUDE_CODE_TOOL_TOKENS: dict[str, int] = {
    "Bash":             400,
    "Read":             350,
    "Write":            250,
    "Edit":             400,
    "Glob":             200,
    "Grep":             500,
    "WebFetch":         300,
    "WebSearch":        250,
    "Task":             2_500,  # Largest — includes all agent type descriptions
    "NotebookEdit":     300,
    "AskUserQuestion":  500,
    "EnterPlanMode":    800,
    "ExitPlanMode":     300,
    "TaskCreate":       500,
    "TaskUpdate":       500,
    "TaskList":         300,
    "TaskGet":          200,
    "TeamCreate":       1_500,
    "TeamDelete":       100,
    "SendMessage":      800,
    "Skill":            300,
    "TaskOutput":       200,
    "TaskStop":         100,
}
# Total with all tools: ~3500 + ~10550 ≈ 14k. With MCP tools, add per-tool.
# Claude Code also injects CLAUDE.md, rules, MEMORY.md — varies per project.
CLAUDE_CODE_PROJECT_OVERHEAD = 4_000  # Rough estimate for CLAUDE.md + rules


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_rss_bytes(pid: int | None = None) -> int:
    """RSS in bytes for a given PID. Falls back to self if pid is None or stale.

    macOS `ps -o rss=` returns KB. Linux `/proc/<pid>/statm` page 1 is pages.
    """
    target = pid or os.getpid()
    try:
        if platform.system() == "Linux":
            with open(f"/proc/{target}/statm") as f:
                pages = int(f.read().split()[1])
            return pages * resource.getpagesize()
        else:
            # macOS / BSD — ps returns KB
            result = subprocess.run(
                ["ps", "-o", "rss=", "-p", str(target)],
                capture_output=True, text=True, timeout=2,
            )
            if result.returncode == 0 and result.stdout.strip():
                return int(result.stdout.strip()) * 1024
    except (OSError, ValueError, subprocess.TimeoutExpired):
        pass
    # Fallback: measure self (daemon)
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if platform.system() == "Linux":
        rss *= 1024
    return rss


from dataclasses import dataclass


@dataclass
class AgentRunResult:
    exit_code: int
    timed_out: bool
    compaction_detected: bool
    command_name: str
    input_tokens: int = 0
    output_tokens: int = 0
    interrupted: bool = False


class AgentDaemon:
    def __init__(self, config: SwarmConfig, agent_name: str) -> None:
        if agent_name not in config.agents:
            raise KeyError(f"Unknown agent '{agent_name}' in config")

        self.config = config
        self.agent_cfg = config.agents[agent_name]
        self.agent_name = agent_name

        self.buffer = RollingBuffer(self.agent_cfg.max_history_tokens)

        self.inject_history_next_turn = False
        self.consecutive_failures = 0
        self.last_error: Optional[str] = None

        self._stop_event = threading.Event()
        self._invocation = 0
        self._session_input_tokens = 0
        self._session_output_tokens = 0
        self._tool_overhead_tokens = 0  # Claude Code system prompt/tools overhead, measured at boot
        self._context_window = 0        # Set from modelUsage.contextWindow in stream-json

        self._child_pid: int | None = None
        self._generation = 0
        self._invocation_row_id: int | None = None

        self.state_path = self.config.state_dir / f"{self.agent_name}.json"
        self.resume_ready = self._load_resume_ready()

        # watcher mode uses direct DB access for backward compat
        self._use_poll = self._comms_name() == "minion-comms"
        self._watcher: Any = None

        self._provider = get_provider(
            self.agent_cfg.provider, self.agent_name, self.agent_cfg, self._use_poll,
        )
        self._error_log = self.config.logs_dir / f"{self.agent_name}.error.log"

    def _get_watcher(self) -> Any:
        """Lazy-init watcher for legacy watcher mode only."""
        if self._watcher is None:
            self._watcher = CommsWatcher(self.agent_name, self.config.comms_db)
        return self._watcher

    def run(self) -> None:
        self.config.ensure_runtime_dirs()

        if self._use_poll:
            self._run_poll_mode()
        else:
            self._run_watcher_mode()

    def _run_poll_mode(self) -> None:
        """minion-comms mode: poll.sh + claude invocations. No direct DB access.

        Outer loop handles auto-respawn on context death (phoenix_down).
        Inner loop handles message polling and agent invocations.
        Only SIGTERM/SIGINT or stand_down exits the outer loop.
        """
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

        # Write PID + crew to DB so observability doesn't depend on state files
        crew_name = self.config.config_path.stem if self.config.config_path else None
        self._write_agent_runtime(crew=crew_name)

        self._log(f"starting daemon for {self.agent_name}")
        self._log(f"provider: {self.agent_cfg.provider} (resume_ready={self.resume_ready})")
        self._log(f"db: {self.config.comms_db}")
        self._log(f"project_dir: {self.config.project_dir}")
        self._log("mode: poll (minion poll)")

        self._generation = 0
        while not self._stop_event.is_set():
            self._generation += 1
            generation = self._generation
            exit_reason = self._poll_generation(generation)
            if exit_reason == "phoenix_down" and not self._stop_event.is_set():
                self._log(f"🔄 auto-respawn: generation {generation} died (context exhausted), rebooting as generation {generation + 1}")
                self._reset_for_respawn()
                continue
            break

        self._write_state("stopped")
        self._log("daemon stopped")

    def _reset_for_respawn(self) -> None:
        """Reset daemon state for a fresh generation after context death."""
        self._stop_event.clear()
        self._session_input_tokens = 0
        self._session_output_tokens = 0
        self._tool_overhead_tokens = 0
        self._context_window = 0
        self._invocation = 0
        self.resume_ready = False
        self.consecutive_failures = 0
        self.last_error = None
        self.buffer = RollingBuffer(self.agent_cfg.max_history_tokens)
        self.inject_history_next_turn = False

    def _poll_generation(self, generation: int) -> str:
        """Run one boot + poll cycle. Returns exit reason: 'phoenix_down', 'signal', or 'stand_down'."""
        self._write_state("idle", generation=generation)

        # Reset stale HP from previous generation
        self._update_hp(0, 0, turn_input=0, turn_output=0)

        # Boot: invoke claude directly to run ON STARTUP instructions
        self._log(f"boot (gen {generation}): invoking agent for ON STARTUP")
        self._write_state("working", generation=generation)
        boot_prompt = self._build_boot_prompt()
        result = self._run_agent(boot_prompt)
        if result.exit_code == 0:
            self.resume_ready = True
            if result.input_tokens > 0:
                prompt_tokens = len(boot_prompt) // 4
                self._tool_overhead_tokens = max(0, result.input_tokens - prompt_tokens)
                ctx = self._context_window if self._context_window > 0 else 200_000
                self._log(f"boot HP: {result.input_tokens // 1000}k/{ctx // 1000}k context, overhead≈{self._tool_overhead_tokens // 1000}k, prompt≈{prompt_tokens} tokens")
                self._session_input_tokens += result.input_tokens
                self._session_output_tokens += result.output_tokens
                self._update_hp(
                    self._session_input_tokens, self._session_output_tokens,
                    turn_input=result.input_tokens, turn_output=result.output_tokens,
                )
            self._log(f"boot (gen {generation}): complete")
        else:
            self._log(f"boot (gen {generation}): failed (exit {result.exit_code})")

        self._write_state("idle", generation=generation)

        while not self._stop_event.is_set():
            self._log("polling for messages...")
            poll_data = self._poll_inbox()

            if self._stop_event.is_set():
                # Check if we're stopping due to phoenix_down vs signal/stand_down
                state = self._read_state()
                if state.get("status") == "phoenix_down":
                    return "phoenix_down"
                return "signal"

            if not poll_data:
                self._stop_event.wait(timeout=5.0)
                continue

            self._write_state("working", generation=generation)
            messages = poll_data.get("messages", [])
            tasks = poll_data.get("tasks", [])
            for msg in messages:
                sender = msg.get("from_agent", "?")
                content = msg.get("content", "")
                preview = content[:200].replace("\n", " ")
                self._log(f"📨 from {sender}: {preview}")
            for task in tasks:
                self._log(f"📋 task #{task.get('task_id')}: {task.get('title', '?')}")
            if not messages and not tasks:
                self._log("messages detected, invoking agent")
            prompt = self._build_inbox_prompt(poll_data)
            ok = self._process_prompt(prompt)

            if ok:
                self.consecutive_failures = 0
                self.last_error = None
                # Check if _process_prompt triggered phoenix_down
                state = self._read_state()
                if state.get("status") == "phoenix_down":
                    return "phoenix_down"
                self._write_state("idle", generation=generation)
            else:
                self.consecutive_failures += 1
                self._write_state(
                    "error",
                    failures=self.consecutive_failures,
                    last_error=self.last_error,
                    generation=generation,
                )
                backoff = min(
                    self.agent_cfg.retry_backoff_sec * (2 ** (self.consecutive_failures - 1)),
                    self.agent_cfg.retry_backoff_max_sec,
                )
                self._log(f"failure #{self.consecutive_failures}; backing off {backoff}s ({self.last_error or 'unknown'})")
                if self.consecutive_failures >= 3:
                    self._alert_lead_poll(
                        f"agent {self.agent_name} has {self.consecutive_failures} "
                        f"consecutive failures. Last error: {self.last_error or 'unknown'}"
                    )
                self._stop_event.wait(timeout=float(backoff))

        return "signal"

    def _poll_inbox(self) -> Optional[Dict[str, Any]]:
        """Run minion poll as a subprocess. Returns poll data dict or None.
        Sets stop_event if stand_down detected (exit code 3).
        """
        try:
            env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
            env[ENV_DB_PATH] = str(self.config.comms_db)
            env[ENV_DOCS_DIR] = str(self.config.docs_dir)
            proc = subprocess.run(
                ["minion", "poll", "--agent", self.agent_name, "--interval", "5", "--timeout", "30"],
                capture_output=True,
                text=True,
                env=env,
            )
            if proc.returncode == 3:
                self._log("stand_down detected — leader dismissed the party")
                self._stop_event.set()
                return None
            if proc.returncode == 0 and proc.stdout.strip():
                try:
                    return json.loads(proc.stdout.strip())
                except json.JSONDecodeError:
                    self._log(f"POLL ERROR: non-JSON output: {proc.stdout[:200]}")
                    return None
            if proc.returncode not in (0, 1):
                # 0=content, 1=timeout — anything else is unexpected
                stderr_tail = (proc.stderr or "")[:300] if hasattr(proc, "stderr") else ""
                self._log(f"POLL ERROR: exit code {proc.returncode} stderr={stderr_tail}")
            return None
        except FileNotFoundError:
            self._log("FATAL: 'minion' binary not found in PATH — daemon cannot poll")
            self._stop_event.set()
            return None
        except Exception as exc:
            self._log(f"POLL ERROR: {type(exc).__name__}: {exc}")
            self._stop_event.wait(timeout=5.0)
            return None

    def _build_boot_prompt(self) -> str:
        """Prompt for the first invocation — agent registers and sets up.

        Note: agent_cfg.system is passed via --append-system-prompt by the
        provider, so we exclude it here to avoid duplication.
        """
        from minion.prompts import build_boot_prompt as _build_boot
        return _build_boot(
            docs_dir=self.config.docs_dir,
            agent=self.agent_name,
            role=self.agent_cfg.role or "coder",
            guardrails=self._build_provider_section(),
            capabilities=self.agent_cfg.capabilities,
        )

    def _build_inbox_prompt(self, poll_data: Dict[str, Any]) -> str:
        """Prompt with messages/tasks already inline — no need to fetch.

        Note: agent_cfg.system is passed via --append-system-prompt by the
        provider, so we exclude it here to avoid duplication.
        """
        history_snapshot = None
        if self.inject_history_next_turn and len(self.buffer) > 0:
            history_snapshot = self.buffer.snapshot()
            self.inject_history_next_turn = False

        from minion.prompts import build_inbox_prompt as _build_inbox
        return _build_inbox(
            docs_dir=self.config.docs_dir,
            agent=self.agent_name,
            role=self.agent_cfg.role or "coder",
            poll_data=poll_data,
            guardrails=self._build_provider_section(),
            history_snapshot=history_snapshot,
            capabilities=self.agent_cfg.capabilities,
        )

    @staticmethod
    def _strip_on_startup(text: str) -> str:
        """Remove ON STARTUP block from system prompt for subsequent invocations."""
        import re
        # Match "ON STARTUP ..." through to the next blank line or end of string
        return re.sub(
            r"ON STARTUP[^\n]*\n(?:[ \t]+\d+\..*\n)*(?:[ \t]+Then .*\n?)?",
            "",
            text,
        ).strip()

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
                self._alert_lead_poll(
                    f"agent {self.agent_name} at {hp_pct:.0f}% HP — context exhausted. "
                    f"Stopping daemon. Respawn to continue from assessment matrix."
                )
                self._write_state("phoenix_down", hp_pct=hp_pct)
                self._stop_event.set()
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

    # ── legacy watcher mode ──────────────────────────────────────────────

    def _run_watcher_mode(self) -> None:
        """Legacy watcher mode: direct DB access."""
        watcher = self._get_watcher()
        watcher.start()
        watcher.register_agent(
            role=self.agent_cfg.role,
            description=f"minion-swarm daemon agent ({self.agent_cfg.zone})",
            status="online",
        )

        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

        self._log(f"starting daemon for {self.agent_name}")
        self._log(f"provider: {self.agent_cfg.provider} (resume_ready={self.resume_ready})")
        self._log(f"mode: watcher (DB: {self.config.comms_db})")
        self._write_state("idle")

        try:
            while not self._stop_event.is_set():
                message = watcher.pop_next_message()

                if message is None:
                    watcher.set_agent_status("idle")
                    self._write_state("idle")
                    watcher.wait_for_update(timeout=5.0)
                    continue

                watcher.set_agent_status("working")
                self._write_state(
                    "working",
                    current_message_id=message.id,
                    from_agent=message.from_agent,
                    received_at=message.timestamp,
                )
                self._log(f"processing message {message.id} from {message.from_agent}")

                prompt = self._build_watcher_prompt(message)
                ok = self._process_prompt(prompt)

                if ok:
                    watcher.set_agent_status("online")
                    self._write_state("idle", last_message_id=message.id)
                    continue

                self._write_state(
                    "error",
                    failures=self.consecutive_failures,
                    last_error=self.last_error,
                    failed_message_id=message.id,
                )

                backoff = min(
                    self.agent_cfg.retry_backoff_sec * (2 ** (self.consecutive_failures - 1)),
                    self.agent_cfg.retry_backoff_max_sec,
                )
                self._log(f"failure #{self.consecutive_failures}; backing off {backoff}s ({self.last_error or 'unknown'})")

                if self.consecutive_failures >= 3:
                    self._alert_lead_watcher(watcher)

                self._stop_event.wait(timeout=float(backoff))

        finally:
            watcher.set_agent_status("offline")
            self._write_state("stopped")
            watcher.stop()
            self._log("daemon stopped")

    def _build_watcher_prompt(self, message: Any) -> str:
        """Build prompt with message content baked in (watcher mode).

        Note: agent_cfg.system is passed via --append-system-prompt by the
        provider, so we exclude it here to avoid duplication.
        """
        max_prompt_chars = self.agent_cfg.max_prompt_chars

        history_snapshot = None
        if self.inject_history_next_turn and len(self.buffer) > 0:
            history_snapshot = self.buffer.snapshot()
            self.inject_history_next_turn = False

        from minion.prompts import build_watcher_prompt as _build_watcher
        prompt = _build_watcher(
            docs_dir=self.config.docs_dir,
            agent=self.agent_name,
            role=self.agent_cfg.role or "coder",
            message_section=self._build_incoming_section(message),
            history_snapshot=history_snapshot,
            capabilities=self.agent_cfg.capabilities,
        )

        if len(prompt) > max_prompt_chars:
            prompt = prompt[:max_prompt_chars]
            self._log("hard-truncated prompt to max_prompt_chars")

        return prompt

    def _build_incoming_section(self, message: Any) -> str:
        return "\n".join(
            [
                "Incoming message:",
                f"- id: {message.id}",
                f"- from: {message.from_agent}",
                f"- timestamp: {message.timestamp}",
                f"- broadcast: {message.is_broadcast}",
                "",
                message.content,
            ]
        )

    def _alert_lead_poll(self, message: str) -> None:
        """Send alert to lead via minion CLI (poll mode — no direct DB access)."""
        import sys
        env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
        env[ENV_CLASS] = "lead"
        env[ENV_DB_PATH] = str(self.config.comms_db)
        env[ENV_DOCS_DIR] = str(self.config.docs_dir)
        try:
            result = subprocess.run(
                ["minion", "send", "--from", self.agent_name, "--to", "commander",
                 "--message", message],
                capture_output=True, text=True, timeout=10, env=env,
            )
            if result.returncode != 0:
                # Fall back to any lead
                r2 = subprocess.run(
                    ["minion", "send", "--from", self.agent_name, "--to", "lead",
                     "--message", message],
                    capture_output=True, text=True, timeout=10, env=env,
                )
                if r2.returncode != 0:
                    print(f"ALERT SEND FAILED: both commander and lead unreachable. stderr={r2.stderr[:200]}", file=sys.stderr, flush=True)
        except Exception as exc:
            print(f"ALERT SEND FAILED: {exc}", file=sys.stderr, flush=True)
        self._log(f"ALERT: {message}")
        print(f"🚨 [{self.agent_name}] {message}", file=sys.stderr, flush=True)

    def _alert_lead_watcher(self, watcher: Any) -> None:
        lead = watcher.find_lead_agent() or "lead"
        content = (
            f"minion-swarm alert: agent {self.agent_name} has {self.consecutive_failures} "
            f"consecutive failures. Last error: {self.last_error or 'unknown'}."
        )
        try:
            watcher.send_message(self.agent_name, lead, content)
            self._log(f"alerted lead '{lead}' about repeated failures")
        except Exception as exc:
            self._log(f"ALERT ERROR: failed to message lead '{lead}': {type(exc).__name__}: {exc}")

    # ── shared ─────────────────────────────────────────────────────────────

    def _handle_signal(self, signum: int, _frame: Any) -> None:
        self._log(f"received signal {signum}, shutting down")
        self._stop_event.set()

    def _comms_name(self) -> str:
        """Poll mode is the default. Watcher mode only for explicit legacy paths."""
        db = str(self.config.comms_db)
        if ".minion-comms" in db:
            return "legacy"
        return "minion-comms"

    def _build_provider_section(self) -> str:
        """Provider-specific prompt guardrails — delegated to provider module."""
        return self._provider.prompt_guardrails()

    def _truncate_tail(self, text: str, max_chars: int, prefix: str) -> str:
        if max_chars <= 0:
            return ""
        if len(text) <= max_chars:
            return text
        if len(prefix) >= max_chars:
            return prefix[:max_chars]
        keep = max_chars - len(prefix)
        return f"{prefix}{text[-keep:]}"

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

    def _load_resume_ready(self) -> bool:
        if not self.state_path.exists():
            return False
        try:
            payload = json.loads(self.state_path.read_text())
        except (OSError, json.JSONDecodeError, TypeError):
            return False
        return bool(payload.get("resume_ready", False))

    def _read_state(self) -> dict[str, Any]:
        if not self.state_path.exists():
            return {}
        try:
            return json.loads(self.state_path.read_text())
        except (OSError, json.JSONDecodeError, TypeError):
            return {}

    def _write_agent_runtime(self, crew: str | None = None) -> None:
        """Write PID, crew to the agents table. Child PID + RSS written per-invocation."""
        import sqlite3
        try:
            conn = sqlite3.connect(str(self.config.comms_db), timeout=5)
            conn.execute("PRAGMA busy_timeout=5000")
            conn.execute(
                "UPDATE agents SET pid = ?, crew = ? WHERE name = ?",
                (self._child_pid, crew, self.agent_name),
            )
            conn.commit()
            conn.close()
        except Exception as exc:
            self._log(f"WARNING: _write_agent_runtime failed: {exc}")

    def _update_child_pid_in_db(self) -> None:
        """Write the current child PID + its RSS to agents (current state)."""
        import sqlite3
        try:
            rss = _get_rss_bytes(self._child_pid)
            conn = sqlite3.connect(str(self.config.comms_db), timeout=5)
            conn.execute("PRAGMA busy_timeout=5000")
            conn.execute(
                "UPDATE agents SET pid = ?, rss_bytes = ? WHERE name = ?",
                (self._child_pid, rss, self.agent_name),
            )
            conn.commit()
            conn.close()
        except Exception as exc:
            self._log(f"WARNING: _update_child_pid_in_db failed: {exc}")

    def _insert_invocation_start(self) -> int | None:
        """INSERT a row into invocation_log when child spawns. Returns row id."""
        import sqlite3
        try:
            conn = sqlite3.connect(str(self.config.comms_db), timeout=5)
            conn.execute("PRAGMA busy_timeout=5000")
            cur = conn.execute(
                """INSERT INTO invocation_log
                   (agent_name, pid, model, generation, rss_bytes, started_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    self.agent_name,
                    self._child_pid,
                    self.agent_cfg.model,
                    self._generation,
                    _get_rss_bytes(self._child_pid),
                    utc_now_iso(),
                ),
            )
            row_id = cur.lastrowid
            conn.commit()
            conn.close()
            return row_id
        except Exception as exc:
            self._log(f"WARNING: _insert_invocation_start failed: {exc}")
            return None

    def _finalize_invocation(self, result: "AgentRunResult") -> None:
        """UPDATE the invocation_log row with end-of-run data."""
        row_id = getattr(self, "_invocation_row_id", None)
        if not row_id:
            return
        import sqlite3
        try:
            rss = _get_rss_bytes(self._child_pid)
            conn = sqlite3.connect(str(self.config.comms_db), timeout=5)
            conn.execute("PRAGMA busy_timeout=5000")
            conn.execute(
                """UPDATE invocation_log SET
                   rss_bytes = ?, input_tokens = ?, output_tokens = ?,
                   exit_code = ?, timed_out = ?, interrupted = ?,
                   compacted = ?, ended_at = ?
                   WHERE id = ?""",
                (
                    rss,
                    result.input_tokens,
                    result.output_tokens,
                    result.exit_code,
                    int(result.timed_out),
                    int(result.interrupted),
                    int(result.compaction_detected),
                    utc_now_iso(),
                    row_id,
                ),
            )
            conn.commit()
            conn.close()
        except Exception as exc:
            self._log(f"WARNING: _finalize_invocation failed: {exc}")
        finally:
            self._invocation_row_id = None

    def _check_interrupt(self) -> bool:
        """Check agent_interrupt table. Returns True if flag is set, and clears it."""
        import sqlite3
        try:
            conn = sqlite3.connect(str(self.config.comms_db), timeout=2)
            conn.execute("PRAGMA busy_timeout=2000")
            cur = conn.cursor()
            cur.execute("SELECT agent_name FROM agent_interrupt WHERE agent_name = ?", (self.agent_name,))
            row = cur.fetchone()
            if row:
                cur.execute("DELETE FROM agent_interrupt WHERE agent_name = ?", (self.agent_name,))
                conn.commit()
                conn.close()
                return True
            conn.close()
        except Exception:
            pass
        return False

    def _log_compaction(self, tokens_pre: int, tokens_post: int) -> None:
        """INSERT a compaction event into compaction_log."""
        import sqlite3
        try:
            rss = _get_rss_bytes(self._child_pid)
            conn = sqlite3.connect(str(self.config.comms_db), timeout=5)
            conn.execute("PRAGMA busy_timeout=5000")
            conn.execute(
                """INSERT INTO compaction_log
                   (agent_name, model, pid, rss_pre_bytes, tokens_pre, tokens_post, generation, compacted_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    self.agent_name,
                    self.agent_cfg.model,
                    os.getpid(),
                    rss,
                    tokens_pre,
                    tokens_post,
                    self._generation,
                    utc_now_iso(),
                ),
            )
            conn.commit()
            conn.close()
        except Exception as exc:
            self._log(f"WARNING: _log_compaction failed: {exc}")

    def _update_session_id(self, session_id: str) -> None:
        """Store session_id on provider and in DB."""
        self._provider.session_id = session_id
        import sqlite3
        try:
            conn = sqlite3.connect(str(self.config.comms_db), timeout=5)
            conn.execute("PRAGMA busy_timeout=5000")
            conn.execute(
                "UPDATE agents SET session_id = ? WHERE name = ?",
                (session_id, self.agent_name),
            )
            conn.commit()
            conn.close()
        except Exception as exc:
            self._log(f"WARNING: _update_session_id failed: {exc}")

    def _write_state(self, status: str, **extra: Any) -> None:
        payload = {
            "agent": self.agent_name,
            "provider": self.agent_cfg.provider,
            "pid": os.getpid(),
            "status": status,
            "updated_at": utc_now_iso(),
            "consecutive_failures": self.consecutive_failures,
            "resume_ready": self.resume_ready,
        }
        payload.update(extra)
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(payload, indent=2))

        # Piggyback RSS update — measure child if alive, else last known
        if self._child_pid:
            import sqlite3
            try:
                rss = _get_rss_bytes(self._child_pid)
                conn = sqlite3.connect(str(self.config.comms_db), timeout=5)
                conn.execute("PRAGMA busy_timeout=5000")
                conn.execute(
                    "UPDATE agents SET rss_bytes = ? WHERE name = ?",
                    (rss, self.agent_name),
                )
                conn.commit()
                conn.close()
            except Exception:
                pass

    def _log(self, message: str) -> None:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{ts}] [{self.agent_name}] {message}", flush=True)
