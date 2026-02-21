"""Agent log tailing — read and follow daemon log files."""
from __future__ import annotations

import sys
import time
from collections import deque

import click

from minion.defaults import resolve_swarm_runtime_dir


def tail_agent_log(agent: str, lines: int = 80, follow: bool = False) -> None:
    """Show (and optionally follow) one agent's log. Streams directly to stdout."""
    log_file = resolve_swarm_runtime_dir() / "logs" / f"{agent}.log"
    if not log_file.exists():
        click.echo(f"Log file not found: {log_file}", err=True)
        sys.exit(1)
    with log_file.open("r") as fp:
        if lines > 0:
            tail = deque(fp, maxlen=lines)
            for line in tail:
                click.echo(line, nl=False)
        if not follow:
            return
        while True:
            line = fp.readline()
            if line:
                click.echo(line, nl=False)
            else:
                time.sleep(0.5)
