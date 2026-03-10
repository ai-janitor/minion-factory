# Stage 7g — Cross-Reference Reconciliation: File Map vs Boundary Dependency Map

Verifying every edge in boundary-dependency-map.md has BOTH sides mapped in the file map.

## Edge Verification

### E-01: SU-01 → SU-08 (convention: error handling)
- **SU-01 side:** `.work/pattern-registry.md` — Error Handling section. MAPPED.
- **SU-08 side:** ~43 files narrowing `except Exception`. MAPPED.
- **Contract artifact:** `.work/pattern-registry.md` section "Error Handling" — both sides reference it.
- **STATUS:** BOTH SIDES MAPPED.

### E-02: SU-01 → SU-09 (convention: assertions)
- **SU-01 side:** `.work/pattern-registry.md` — Contracts and Assertions section. MAPPED.
- **SU-09 side:** ~15 files adding assertions. MAPPED.
- **Contract artifact:** `.work/pattern-registry.md` section "Contracts and Assertions".
- **STATUS:** BOTH SIDES MAPPED.

### E-03: SU-01 → SU-10 (convention: documentation)
- **SU-01 side:** `.work/pattern-registry.md` — Documentation Conventions section. MAPPED.
- **SU-10 side:** ~10 files adding ASSUMPTION and Big-O comments. MAPPED.
- **Contract artifact:** `.work/pattern-registry.md` section "Documentation Conventions".
- **STATUS:** BOTH SIDES MAPPED.

### E-04: SU-01 → SU-14 (convention: canonical patterns for dedup)
- **SU-01 side:** `.work/pattern-registry.md` — DB Access, Provider Error Classification, Logging sections. MAPPED.
- **SU-14 side:** 3 new shared modules + provider file modifications. MAPPED.
- **Contract artifact:** `.work/pattern-registry.md` multiple sections.
- **STATUS:** BOTH SIDES MAPPED.

### E-05: SU-04 → SU-19 (data-shape: cross-repo message delivery)
- **SU-04 side:** `src/minion/comms/delivery.py` — `route_cross_repo()` fix. MAPPED.
- **SU-19 side:** `src/minion/polling.py` — `multi_project_poll()` uses cross-repo delivery. MAPPED.
- **Contract artifact:** `route_cross_repo()` function signature and return shape.
- **STATUS:** BOTH SIDES MAPPED.

### E-06: SU-03 → SU-21 (state-transition: complete_phase() modifications)
- **SU-03 side:** `src/minion/tasks/update_task.py` — self-review check. MAPPED.
- **SU-21 side:** `src/minion/tasks/update_task.py` — scaffolding gate. MAPPED.
- **Contract artifact:** `complete_phase()` function — both add checks sequentially.
- **Coordination note:** Pseudo-logic documents the ordering: class check → SU-03 self-review → SU-21 scaffolding → DAG transition.
- **STATUS:** BOTH SIDES MAPPED. Coordination documented.

### E-07: SU-11 → SU-12 (naming: pytest markers)
- **SU-11 side:** `pyproject.toml` — marker registration. MAPPED.
- **SU-12 side:** New test files use markers from SU-11. MAPPED.
- **Contract artifact:** `pyproject.toml` `[tool.pytest.ini_options] markers` section.
- **STATUS:** BOTH SIDES MAPPED.

### E-08: SU-14 → SU-13 (naming: extracted module paths)
- **SU-14 side:** Creates `src/minion/providers/_shared_error_log.py` and `_shared_error_classifier.py`. MAPPED.
- **SU-13 side:** Uses knowledge of extracted module locations to verify import directions. MAPPED.
- **Contract artifact:** Module paths documented in SU-14 pseudo-logic.
- **STATUS:** BOTH SIDES MAPPED.

### E-09: SU-17 → SU-18 (naming: scaling endpoints resolved)
- **SU-17 side:** `src/minion/network/handlers/scaling.py` — wire or remove decision. MAPPED.
- **SU-18 side:** `src/minion/network/router.py` — register new routes knowing scaling state. MAPPED.
- **Contract artifact:** SU-17 documents decision: "scaling endpoints WIRED/REMOVED".
- **STATUS:** BOTH SIDES MAPPED.

### E-10: SU-18 → SU-22 (naming + data-shape: API endpoints for dashboard)
- **SU-18 side:** New handlers with defined endpoint paths and response JSON shapes. MAPPED.
- **SU-22 side:** Dashboard views call API endpoints / shared query functions. MAPPED.
- **Contract artifact:** `src/minion/network/router.py` (paths), handler return types (shapes).
- **STATUS:** BOTH SIDES MAPPED.

### E-11: SU-05 → SU-02 (state-transition: stale in TERMINAL_STATUSES)
- **SU-05 side:** `src/minion/tasks/dag.py` — add "stale" to TERMINAL_STATUSES. MAPPED.
- **SU-02 side:** Test for 2.5 (state machines) should account for stale. MAPPED in pseudo-logic (note about SU-05 ordering).
- **Contract artifact:** `TERMINAL_STATUSES` frozenset in dag.py.
- **STATUS:** BOTH SIDES MAPPED. Soft dependency noted.

### E-12: SU-07 → SU-19 (naming: auth permissions for coordinator)
- **SU-07 side:** `src/minion/auth.py` — `is_cross_project()` helper, backlog auth checks. MAPPED.
- **SU-19 side:** `src/minion/auth.py` — coordinator class exempt from cross-project auth. MAPPED.
- **Contract artifact:** `src/minion/auth.py` class permissions mapping.
- **STATUS:** BOTH SIDES MAPPED.

## Non-Edge Boundaries

### B-01: SU-05 internal — dag.py ↔ rollup.py
- Both files mapped in SU-05. rollup.py imports TERMINAL_STATUSES from dag.py. MAPPED.

### B-02: SU-15 internal — cli command names ↔ help text
- All cli/*.py files mapped in SU-15. CLAUDE.md update noted. MAPPED.

### B-03: SU-19 internal — auth.py ↔ agent_classes.py
- Both files mapped in SU-19. MAPPED.

## Corrections from specs to file map

| Spec Reference | Actual File |
|----------------|-------------|
| `routes.py` | `src/minion/network/router.py` |
| `agent-classes.yaml` | `src/minion/tasks/agent_classes.py` |
| `src/minion/prompts/roles/*.py` | `src/minion/prompts/roles/<role>/prompt.md` (+ `__init__.py` loader) |
| `crew/stand_down.py` | `src/minion/crew/lifecycle.py` (stand_down is likely in lifecycle) |

## Gaps Found

**NONE.** All 12 edges and 3 non-edge boundaries have both sides mapped in the file map with specific file paths and change summaries. The pseudo-logic documents coordination points for edges E-06 (SU-03/SU-21 sharing complete_phase) and E-12 (SU-07/SU-19 sharing auth.py).
