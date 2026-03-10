# Research: Technical Feasibility and Constraints

## Cross-Project Coordination (WS5.2)
- **Coordinator DB exists:** ~/.minion/coordinator.db stores agent registry with project_path and scope_mode. Global comms routing works.
- **Aggregated polling constraint:** Currently poll reads from one project's .work/minion.db. Polling across multiple projects requires either: (a) iterating multiple DBs in poll loop, or (b) a network-tier aggregation endpoint.
- **Feasibility:** Adding multi-project poll is straightforward — the coordinator DB knows all project paths. Each iteration checks all project DBs the agent is registered in. Performance concern: O(P * (M + T)) where P = projects.
- **Constraint:** SQLite cannot safely be accessed from multiple machines. Cross-machine coordination REQUIRES the network tier (API GLOBAL).

## Network API Evolution (WS5.1)
- **Composite agent key:** Current DB schema uses `name TEXT PRIMARY KEY` for agents. Changing to host/project/name composite key is a schema migration affecting every query referencing agents by name.
- **Feasibility:** High effort, breaks backward compat. Consider as a v3 item or implement as a supplementary index with FQN (fully qualified name) format (e.g., `host:project:name`). Note: `src/minion/network/fqn.py` already exists — may have partial implementation.
- **On-demand spawning:** scaling.py endpoints exist but need to be wired to router and tested. Feasibility depends on tmux availability on target hosts.

## DAG Self-Review Bypass (WS1.1)
- **Constraint:** transition_log records who triggered each transition. Checking "who implemented" requires querying the transition_log for the agent who completed the implementation stage.
- **Feasibility:** Straightforward — add query to complete_phase() checking if the calling agent was the implementer of the prior stage. Low risk.

## Bare Exception Cleanup (WS2.1)
- **Constraint:** 87 remaining broad exceptions. Each must be manually audited — some are intentional catch-alls at module boundaries (e.g., provider error classifiers that handle any subprocess failure).
- **Feasibility:** Incremental work. Estimate 2-3 exceptions per file, ~43 files. Can be parallelized across coder agents.
- **Risk:** Narrowing too aggressively in daemon code could cause crashes. Must test each change.

## Shell Completions (WS5.3)
- **Feasibility:** Click has built-in shell completion support via `_MINION_COMPLETE` env var. Implementation is ~10 lines in the CLI entry point plus documentation.
- **Constraint:** Requires click>=8.0 (already a dependency).

## Short Flags (WS4.3)
- **Feasibility:** Adding short flags to ~244 options is mechanical but tedious. Risk of conflicts between commonly used letters.
- **Constraint:** Must audit all option names to avoid -a/-b/-c collisions within the same command group.
