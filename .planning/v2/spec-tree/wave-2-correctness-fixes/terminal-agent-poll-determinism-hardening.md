# SU-06: Terminal Agent Poll Determinism Hardening

**Wave:** 2 (parallel correctness cluster)
**Requirements:** 1.6
**Dependencies:** None
**Dependents:** None

## Domain Preamble

Terminal agents (claude-code sessions) don't deterministically poll after completing work — the single biggest operational issue. Agents go deaf after finishing a task. This spec hardens the Stop hook installation, poll-on-stop.sh behavior, and considers mechanical poll auto-restart if the hook proves insufficient. Single operational concern focused on poll reliability.

## Scope

- Verify Stop hook installation and behavior
- Harden `poll-on-stop.sh` script for edge cases
- Consider mechanical poll auto-restart fallback
- Test poll determinism under various completion scenarios

## Affected Files

- `scripts/poll-on-stop.sh`
- `src/minion/polling.py`
- `tests/test_polling*.py`

## Boundary Edges

- None
