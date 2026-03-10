# Boundary Dependency Map — v2

Living artifact. Created at Stage 4 (Decompose). Refined at every reflect gate through Stage 9.

For every edge in the dependency graph: name both specs, name the contract type, mark status.

## Contract Types

- **naming**: shared identifiers (function names, constants, config keys)
- **data-shape**: shared data structures (dict keys, DB row format, return types)
- **state-transition**: shared state machine definitions (valid states, valid transitions)
- **signal**: shared trigger/event (message types, trigger words, hook names)
- **convention**: shared behavioral pattern (how to handle errors, how to access DB)

---

## Edges

### E-01: SU-01 (pattern registry) → SU-08 (bare exception narrowing)
- **Contract type:** convention
- **Contract:** Pattern registry defines the error handling convention: when to raise typed exceptions vs return error dicts. SU-08 must narrow exceptions to follow this convention.
- **Shared artifact:** `.work/pattern-registry.md` section "Error Handling"
- **Status:** [pending]

### E-02: SU-01 (pattern registry) → SU-09 (assertion expansion)
- **Contract type:** convention
- **Contract:** Pattern registry defines assertion convention: what preconditions to assert, where postconditions go, what exception type failed assertions raise.
- **Shared artifact:** `.work/pattern-registry.md` section "Contracts and Assertions"
- **Status:** [pending]

### E-03: SU-01 (pattern registry) → SU-10 (assumption/Big-O documentation)
- **Contract type:** convention
- **Contract:** Pattern registry defines documentation convention: format of ASSUMPTION comments, format of Big-O annotations, what constitutes a "magic number."
- **Shared artifact:** `.work/pattern-registry.md` section "Documentation Conventions"
- **Status:** [pending]

### E-04: SU-01 (pattern registry) → SU-14 (code deduplication)
- **Contract type:** convention
- **Contract:** Pattern registry defines the canonical pattern for each cross-cutting concern (DB access, error classification, logging). SU-14 deduplicates toward these patterns, not toward arbitrary shared code.
- **Shared artifact:** `.work/pattern-registry.md` sections "DB Access", "Provider Error Classification", "Logging"
- **Status:** [pending]

### E-05: SU-04 (global comms fix) → SU-19 (cross-project coordination)
- **Contract type:** data-shape
- **Contract:** `route_cross_repo()` must reliably deliver messages to foreign project DBs. SU-19 depends on the messages table existing (or being auto-created) in target projects. The data shape is: `(id, from_agent, to_agent, message, msg_type, timestamp)`.
- **Shared artifact:** `src/minion/comms/delivery.py` — `route_cross_repo()` function signature and return value
- **Status:** [pending]

### E-06: SU-03 (DAG self-review bypass) → SU-21 (DAG scaffolding enforcement)
- **Contract type:** state-transition
- **Contract:** Both modify DAG phase advancement logic in `complete_phase()`. SU-03 adds agent-identity check. SU-21 adds scaffolding-completion check. Both gate the same function. Must not conflict — checks are additive (AND, not OR).
- **Shared artifact:** `src/minion/tasks/update_task.py` — `complete_phase()` function, specifically the validation block before phase advancement
- **Status:** [pending]

### E-07: SU-11 (test infrastructure) → SU-12 (missing tests + verification)
- **Contract type:** naming
- **Contract:** SU-11 defines pytest marker names (unit, integration, smoke) and registers them in pyproject.toml. SU-12 must use these exact marker names on new test files.
- **Shared artifact:** `pyproject.toml` — `[tool.pytest.ini_options] markers` section
- **Status:** [pending]

### E-08: SU-14 (code deduplication) → SU-13 (dependency layer fixes)
- **Contract type:** naming
- **Contract:** SU-14 may extract shared modules (e.g., shared error classifier for providers, shared DB access helper). SU-13 must know where these shared modules land to verify import directions are correct. The contract is: extracted module locations and their import paths.
- **Shared artifact:** Module paths created by SU-14 (e.g., `src/minion/providers/_shared_error_classifier.py`)
- **Status:** [pending]

### E-09: SU-17 (dead code cleanup) → SU-18 (network API parity)
- **Contract type:** naming
- **Contract:** SU-17 resolves whether scaling endpoints are kept or removed. SU-18 must know the final state of `src/minion/network/handlers/scaling.py` and its router registration before adding new endpoints.
- **Shared artifact:** `src/minion/network/routes.py` — registered route list
- **Status:** [pending]

### E-10: SU-18 (network API parity) → SU-22 (dashboard consolidation)
- **Contract type:** naming + data-shape
- **Contract:** SU-18 finalizes network API endpoints. SU-22 builds dashboard views that call these endpoints. The contract is: endpoint paths (naming) and response JSON shapes (data-shape).
- **Shared artifact:** `src/minion/network/routes.py` (paths), handler return types (shapes)
- **Status:** [pending]

### E-11: SU-05 (stale terminal status) → SU-02 (verify-only, specifically 2.5 state machines)
- **Contract type:** state-transition
- **Contract:** SU-05 adds "stale" to TERMINAL_STATUSES. SU-02 verifies state machines (2.5). The verification must account for the new stale state. SU-02 should run after SU-05 for the state machine verification portion, or verify against the updated constant.
- **Shared artifact:** `src/minion/tasks/dag.py` — `TERMINAL_STATUSES` frozenset
- **Status:** [pending]
- **Note:** This is a soft dependency — SU-02 can verify other items in parallel, but the 2.5 verification should account for SU-05's change.

### E-12: SU-07 (backlog auth) → SU-19 (cross-project coordination)
- **Contract type:** naming
- **Contract:** SU-07 hardens auth checks on `-C` flag operations. SU-19 adds coordinator class. Both modify auth behavior — coordinator class must have appropriate backlog permissions.
- **Shared artifact:** `src/minion/auth.py` — class permissions mapping
- **Status:** [pending]

---

## Non-Edge Boundaries (within-unit, for tracking)

### B-01: SU-05 internal — dag.py ↔ rollup.py
- **Contract type:** state-transition
- **Contract:** rollup.py reads TERMINAL_STATUSES from dag.py. Adding "stale" changes rollup behavior for parent tasks with stale children.
- **Status:** [pending]

### B-02: SU-15 internal — cli command names ↔ help text
- **Contract type:** naming
- **Contract:** Renamed/moved commands must update help text, CLAUDE.md, and any hardcoded command references.
- **Status:** [pending]

### B-03: SU-19 internal — auth.py ↔ agent-classes.yaml
- **Contract type:** naming
- **Contract:** New coordinator class must appear in both auth.py permissions and agent-classes.yaml definitions.
- **Status:** [pending]

---

## Layers (to be refined at later stages)

- **Stage 4 (current):** Spec-to-spec boundaries (this document)
- **Stage 6 (specs):** Refined with function-level contracts after specs are written
- **Stage 7 (scaffold):** File-to-file boundaries added
- **Stage 8b (reconciliation):** Function-to-function boundaries added
