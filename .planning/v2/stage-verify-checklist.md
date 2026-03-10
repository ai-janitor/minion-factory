# Stage 9 Checklist — v2 Verify

## 9a: Static Checks
- [x] `uv run pytest` — all tests pass, 0 failures (576 passed in 11.75s)
- [x] Record test count and any warnings — 576 tests, 0 warnings

## 9b: Runtime Smoke Tests
- [x] `minion --version` — CLI responds (v0.4.1)
- [x] `minion who` — returns agent list (no ghosts; only active session agents)
- [x] `minion agent register --name smoke-test --class coder` — succeeds
- [x] `minion set-context --agent smoke-test --context "smoke test" --hp 90` — succeeds
- [x] `minion task define --agent verify-lead --title "smoke" --description "test"` — creates task (note: requires lead agent, not coder)
- [x] `minion task list` — shows the task
- [x] `minion comms send local --from verify-lead --to smoke-test --message "ping"` — sends (self-send blocked by design; used cross-agent send)
- [x] `minion comms check-inbox --agent smoke-test` — receives the ping
- [x] `minion agent deregister --name smoke-test` — cleans up
- [x] `minion backlog list --status open` — responds without error (empty list)
- [x] `minion sitrep` — fused COP renders (agents, tasks, claims, flags, battle plan, comms)
- [x] `minion dashboard` — TUI command exists and responds to --help (non-interactive env, visual verify N/A)

## 9c: New Feature Smoke Tests (Stage 8 additions)
- [x] `minion completions show` — outputs shell completion script (SU-20)
- [FAIL] Coordinator class: `minion agent register --name coord-test --class coordinator` — FAILS (SU-19). CLI click.Choice on agent_cmds.py:27 omits "coordinator". See UF-V2-004.
- [x] Scaffolding gate: verify complete_phase blocks when files missing (SU-21) — code verified in update_task.py:192-215
- [x] Network handlers exist: check imports don't crash (SU-18) — `from minion.network import handlers` succeeds
- [x] Shared provider modules importable (SU-14) — both _shared_error_classifier and _shared_error_log import OK

## 9d: Record Findings
- [x] All findings written to .planning/v2/upstream-feedback.md (UF-V2-004, UF-V2-005)
- [ ] Task #88 closed
- [ ] All agents deregistered
