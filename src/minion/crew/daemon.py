"""Daemon transport — tmux pane with tail -f, in-process daemon management.

Purpose: Daemon transport — tmux pane with tail -f, in-process daemon management.
Rationale: Extracted into own module for single-responsibility crew lifecycle management.
Responsibility: Daemon transport — tmux pane with tail -f, in-process daemon management. NOT responsible for unrelated concerns.
Organization: Standalone functions and/or a single class. See source."""

from __future__ import annotations

import json
import logging
import os
import shutil
import signal
import subprocess
import sys
from datetime import datetime

log = logging.getLogger(__name__)


def _log_json(fp, agent: str, level: str, message: str, **extra) -> None:
    """Write a structured JSON log line to the given file handle."""
    entry = {
        "ts": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "agent": agent,
        "level": level,
        "source": "crew.daemon",
        "message": message,
    }
    entry.update(extra)
    fp.write(json.dumps(entry) + "\n")
    fp.flush()


def init_swarm(config_path: str, project_dir: str) -> None:
    """Create runtime directories for a swarm config (replaces minion-swarm init)."""
    from minion.crew.config import load_config
    cfg = load_config(config_path)
    cfg.ensure_runtime_dirs()


def start_agent_daemon(config_path: str, agent_name: str, db_path: str = "", instance_id: str | None = None) -> None:
    """Fork a daemon process for one agent (replaces minion-swarm start).

    instance_id: Optional instance suffix for multi-instance spawns. When set,
    log files use the instance-qualified name (e.g., redmage-jr-2.log) and
    MINION_INSTANCE_ID is set in the environment. When None, uses bare agent
    name (backward compatible).
    """
    from minion.crew.config import load_config
    from minion.instance import resolve_file_key
    cfg = load_config(config_path)
    file_key = resolve_file_key(agent_name, instance_id)
    log_file = cfg.logs_dir / f"{file_key}.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    log_fp = open(log_file, "a")

    resolved_db = db_path or str(cfg.comms_db)
    env = {**os.environ, "MINION_DB_PATH": resolved_db}
    env["MINION_AGENT_NAME"] = agent_name
    env["MINION_PROJECT_DIR"] = str(cfg.comms_db.parent.parent)  # .work/minion.db → project root
    if instance_id:
        env["MINION_INSTANCE_ID"] = instance_id
    if cfg.docs_dir:
        env["MINION_DOCS_DIR"] = str(cfg.docs_dir)

    # Resolve absolute path to minion binary so detached process finds it
    minion_bin = shutil.which("minion")
    if not minion_bin:
        _log_json(log_fp, agent_name, "FATAL", "'minion' not found in PATH", path=os.environ.get("PATH", ""))
        log_fp.close()
        raise FileNotFoundError("'minion' binary not found in PATH — is minion-factory installed?")

    _log_json(log_fp, agent_name, "INFO", "daemon-launch", bin=minion_bin, db=resolved_db, config=config_path, instance_id=instance_id)

    import time
    cmd = [minion_bin, "daemon-run", "--config", config_path, "--agent", agent_name]
    if instance_id:
        cmd.extend(["--instance-id", instance_id])
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.DEVNULL,
        stdout=log_fp,
        stderr=subprocess.STDOUT,
        start_new_session=True,
        env=env,
    )
    # Give the process a moment to crash on startup — catch instant death
    time.sleep(0.5)
    if proc.poll() is not None:
        log_fp.close()
        raise RuntimeError(
            f"daemon for {file_key} died immediately (exit code {proc.returncode}). "
            f"Check {log_file}"
        )
    log_fp.close()


def stop_swarm(config_path: str) -> None:
    """Stop all daemon agents for a config by reading PID from state files."""
    from minion.crew.config import load_config
    try:
        cfg = load_config(config_path)
    except (FileNotFoundError, ValueError):
        return
    state_dir = cfg.state_dir
    if not state_dir.is_dir():
        return
    for state_file in state_dir.glob("*.json"):
        try:
            state = json.loads(state_file.read_text())
            pid = state.get("pid")
            if pid and isinstance(pid, int):
                os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass  # Already dead — expected during cleanup
        except (OSError, json.JSONDecodeError) as exc:
            log.warning("stop_swarm failed to kill %s: %s", state_file.name, exc)


def spawn_pane(
    tmux_session: str,
    agent: str,
    project_dir: str,
    crew_config: str,
    session_exists: bool,
    pane_cmd: str = "",
    instance_id: str | None = None,
) -> bool:
    """Create a tmux pane. Uses tail -f <log> unless pane_cmd is given.

    Returns True if pane was created, error string if it didn't fit.

    instance_id: Optional instance suffix. When set, the log file uses the
    instance-qualified name so each instance gets its own tail pane.
    """
    if not pane_cmd:
        from minion.instance import resolve_file_key
        file_key = resolve_file_key(agent, instance_id)
        log_file = os.path.join(project_dir, ".minion-swarm", "logs", f"{file_key}.log")
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        open(log_file, "a").close()
        pane_cmd = f"tail -f {log_file}"

    if not session_exists:
        subprocess.run([
            "tmux", "new-session", "-d",
            "-s", tmux_session, "-n", agent,
            "-x", "300", "-y", "80",
            "bash", "-c", pane_cmd,
        ], check=True)
    else:
        # Rebalance layout before splitting so tmux has room for the new pane
        r = subprocess.run(
            ["tmux", "select-layout", "-t", tmux_session, "tiled"],
            capture_output=True, text=True,
        )
        if r.returncode != 0:
            log.warning("pre-split layout rebalance failed for %s: %s", tmux_session, r.stderr.strip())
        result = subprocess.run([
            "tmux", "split-window", "-t", tmux_session,
            "bash", "-c", pane_cmd,
        ], capture_output=True, text=True)
        if result.returncode != 0:
            return result.stderr.strip()
    return True


def _find_ts_daemon_dir() -> str:
    """Locate ts-daemon directory: env var, then sibling of minion-swarm package."""
    if os.environ.get("MINION_TS_DAEMON_DIR"):
        return os.environ["MINION_TS_DAEMON_DIR"]
    try:
        import minion_swarm
        candidate = os.path.join(os.path.dirname(os.path.dirname(minion_swarm.__file__)), "ts-daemon")
        if os.path.isdir(candidate):
            return candidate
    except ImportError:
        pass  # Optional dependency — fallback to default path
    return os.path.expanduser("~/.minion-swarm/ts-daemon")


def start_swarm(agent: str, crew_config: str, project_dir: str, runtime: str = "python", db_path: str = "", instance_id: str | None = None) -> None:
    """Start daemon watcher for an agent.

    runtime='python' uses in-process AgentDaemon.
    runtime='ts' uses the TypeScript SDK daemon.

    instance_id: Optional instance suffix for multi-instance spawns. Passed
    through to start_agent_daemon() for file isolation.
    """
    if runtime == "ts":
        from minion.instance import resolve_file_key
        file_key = resolve_file_key(agent, instance_id)
        log_file = os.path.join(project_dir, ".minion-swarm", "logs", f"{file_key}.log")
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        log_fp = open(log_file, "a")
        project_name = os.path.basename(os.path.abspath(project_dir))
        env = {**os.environ, "MINION_CLASS": "lead", "MINION_PROJECT": project_name}
        if instance_id:
            env["MINION_INSTANCE_ID"] = instance_id
        env.pop("CLAUDECODE", None)
        subprocess.Popen(
            ["npx", "tsx", "src/main.ts", "--config", crew_config, "--agent", agent],
            cwd=_find_ts_daemon_dir(),
            stdin=subprocess.DEVNULL,
            stdout=log_fp,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            env=env,
        )
        log_fp.close()
    else:
        start_agent_daemon(crew_config, agent, db_path=db_path, instance_id=instance_id)
