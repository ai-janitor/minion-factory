"""Entry point for `python -m minion.daemon --config ... --agent ...`."""

import argparse

from .config import load_config
from .runner import AgentDaemon


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a single agent daemon")
    parser.add_argument("--config", required=True, help="Path to crew YAML config")
    parser.add_argument("--agent", required=True, help="Agent name to run")
    args = parser.parse_args()

    cfg = load_config(args.config)
    daemon = AgentDaemon(cfg, args.agent)
    daemon.run()


if __name__ == "__main__":
    main()
