# Iterative Decomposition DAG

**This file contains directives only. Do not add justifications, rationale, history, or editorial. Every sentence must be a directive, constraint, or definition. If a rule needs a "why", put it in FINDINGS.md.**

## Stages

1. **Raw requirements** — Capture user's words verbatim. Do not modify after initial capture.
2. **Clean requirements** — Derive from raw requirements first, unbiased. Then reconcile against previous clean requirements and upstream feedback. Organize by domain. Write WHAT, not HOW.
3. **Research** — Survey existing code, tools, skills, prior art, and technical constraints. Write findings to disk.
4. **Decomposition** — Map requirements to spec units. Identify dependencies. Sequence build order. Produce: spec unit list with dependency graph. Produce: **boundary dependency map** — for every edge in the dependency graph, name the shared boundary and its contract type (naming contract, data shape, event type, state transition, route path). The boundary dependency map is a living artifact — create it here, refine it at every reflect gate through Stage 9.
5. **Spec tree** — Express architecture as filesystem hierarchy. The tree must be reviewable from `tree` output alone.
6. **Specifications** — Fill each spec with behavior, constraints, and edge cases. Write WHAT, not HOW. Leave zero judgment calls for the implementer. After specs are approved, a **separate agent** (not the spec-writing agents) reads each spec and extracts every testable behavioral contract to `test-contracts.md` — input/output pairs, precondition/postcondition pairs, edge case expected outcomes. Vague behavior ("handles errors appropriately") is not a contract — rewrite the spec. `test-contracts.md` is a **living artifact**: behavioral contracts (Stage 6) → test file stubs (Stage 7) → test pseudo-logic (Stage 7d) → implemented tests (Stage 8) → reconciled (Stage 8b). **Reflect gate: cross-spec contract reconciliation.** After all specs are written, assign one agent per boundary edge (from the dependency map). That agent reads both specs and extracts the contract each side assumes — function name, event type, DOM ID, state name, route path. Mismatches are findings. Append newly discovered boundaries to the dependency map.
7. **Scaffolding** — Create stubs, file headers, pseudo-logic per project conventions. Execute in two phases: tree first (biased generalist), then content (unbiased specialists per spec). The tree agent also produces: test file stubs for every contract in `test-contracts.md`, and a **pattern registry** (`pattern-registry.md`) declaring the one chosen pattern per cross-cutting concern (HTTP client, error handling, data access, logging, config, template rendering). **Convergence gate:** zero tree mutations across specialist passes. After specialist passes converge, run **cross-reference reconciliation**: extract every string-based cross-reference (template names, DOM IDs, CSS classes, route paths, config keys) from all scaffold files and verify both sides agree. Run **pattern consistency check**: verify all scaffold files follow the pattern registry — deviations are findings. Run **test contract coverage check**: verify every contract in `test-contracts.md` has a test stub in the scaffold. Name mismatches between scaffold files are findings that block Stage 8. Use the boundary dependency map from Stage 4 (refined at Stage 6) as input — check every named edge. Append newly discovered file-level boundaries to the map.
8. **Implementation** — Write code between scaffold comments. Implementation agents may only create or modify files that exist in the scaffold tree. Implement tests alongside production code, not after. Follow the pattern registry for every cross-cutting concern.
8b. **Scaffold Reconciliation** — For every file in the scaffold tree, classify as IMPLEMENTED, SUPERSEDED (name the replacement), INTENTIONAL-EMPTY (state the rationale), or MISSING (this is a finding). Diff scaffold file list against implementation file list. Any file in one but not the other is a finding. MISSING entries block Stage 9. **Wiring check**: for every coordinator/orchestrator/bridge file, verify it actually calls the sub-packages it references. A file that imports a package but never calls its functions is a finding. **Test contract reconciliation**: for every contract in `test-contracts.md`, verify a test function exists with actual assertions (not stubs). Contracts without tests block Stage 9. **Pattern drift check**: verify all implementation files follow `pattern-registry.md`. No package may use a different approach than the registered pattern for the same concern. **Dependency map update**: append newly discovered function-level boundaries. The map now has three layers: spec-to-spec (Stage 4/6), file-to-file (Stage 7), function-to-function (Stage 8b).
9. **Verify** — Two layers. Layer 1 (static): run build, vet, and test, including frontend assertions — template manifest completeness, CSS link validation, orphan template detection. Layer 2 (runtime): run smoke tests — app boot, primary flow, moving parts connect. Coordinator writes runbook, spawns verify agent.

## Gating

- Each stage gates the next. Do not begin stage N+1 until stage N is reviewed and approved.
- Apply /husband protocol at every stage: listen, record, clarify, draw out. Do not solution ahead of the current stage.

## Inputs

Two immutable inputs feed the DAG:

1. **REQUIREMENTS-RAW.md** — What the user said. Do not modify.
2. **upstream-feedback.md** — Accumulated HOW from every stage: every design decision, bug fix, gap discovered, correction applied. Classify each entry by the upstream layer that was wrong.

`upstream-feedback.md` is the single artifact that survives regeneration. When v(N+1) starts, agents read raw requirements + upstream feedback and re-derive everything.

## Convergence-Divergence Boundary

- **Stages 1-6:** Convergent. Single agent (or sequential per-spec fan-out for Stage 6), sequential, full context.
- **Stages 7-8:** Divergent. Fan-out across spec units. Coordinator assembles context blob. Agents claim specs via registry. Work per-spec. Run reflect gate between each wave.
- **Stage 8b:** Convergent. Single reconciliation pass.
- **Stage 9:** Convergent. Single verify agent with runbook.

## Rules

### Stage Discipline
- Every stage gates the next. Do not skip. Do not blend.
- Write WHAT not HOW until Stage 7. Requirements and specs describe behavior. HOW decisions go to `upstream-feedback.md`, not into specs.
- Trace everything. Every spec traces to requirements. Every scaffold traces to a spec. Every implemented file traces to a scaffold file. Untraced artifacts are ungrounded.
- Conventions that shape output are requirements. If a constraint in agent instructions affects the product, it must also appear in clean requirements.

### Derivation Discipline
- Derive fresh, then reconcile. Do not patch incrementally. Derive from upstream inputs first, then diff against prior output.
- Raw is immutable. New information goes to `upstream-feedback.md`. Do not modify raw.
- Nothing downstream is precious. If the DAG says regenerate, regenerate.
- Do not read prior specs when deriving new specs. Agents derive from upstream inputs only.
- A stage is done when independent agents stop finding new gaps, not when all agents finish.

### Grounding Discipline
- On context resumption, re-read artifacts from disk. Do not rely on conversation summaries.
- Write execution checklists to disk. Execute from the checklist. Mark items `[done]` or `[blocked]`.
- Blocked means blocked. Do not improvise workarounds. Mark the item, record why, stop, report.
- Do not decompose without research. No specs without surveying existing code, tools, and prior art.
- DAG changes invalidate downstream artifacts. Regenerate checklists and playbooks from the new DAG.

### Manifesto Enforcement (Stages 7-9)
- `MANIFESTO.md` is active at stages 7, 8, 8b, and 9. Violations are findings.
- Scaffold agents apply manifesto rules structurally: filesystem-as-DB naming, reference integrity design, machine-readable outputs, config cascade. Bake these into the scaffold.
- Scaffold cross-reference reconciliation is mandatory. After specialist scaffold passes converge, extract all string-based naming contracts between scaffold files (template name ↔ Execute() call, DOM ID ↔ OOB target, CSS class ↔ HTML class, route path ↔ handler registration). Both sides must agree. Mismatches block implementation.
- Verify agents check manifesto compliance. Each manifesto rule must have a checkable artifact or test. "We followed it" is not evidence.
- Run two-pass audit at verify. Pass 1 (broad sweep): one agent scans the full project against all manifesto rules, produces a triage list of failing rules and violation counts. Pass 2 (deep dive): one agent per spec reads the spec's behavioral guarantees and the implementing code line by line, checks whether the code delivers what the spec promises. Do not skip Pass 1. Do not stop at Pass 1.

### Implementation Discipline
- The scaffold file list IS the implementation checklist. Do not create files outside the scaffold tree. If the scaffold structure is wrong, that is a finding → write to upstream feedback → update scaffold → then implement.
- Implementation agents read scaffold stubs and write code between the comments. They do not need the full upstream context chain.
- Stage 8b classifies every scaffold file as IMPLEMENTED, SUPERSEDED (with named replacement), INTENTIONAL-EMPTY (with rationale), or MISSING (finding). No silent survivors.
- Stage 8b checks wiring, not just existence. For every coordinator, orchestrator, or bridge file: verify it calls the sub-packages and functions it references. Import without invocation is a finding. Handler that bypasses its orchestrator is a finding.
- Empty stubs satisfy compilers. Only the reconciliation manifest and runtime smoke tests catch silent gaps.

### Feedback Discipline
- Identify which upstream layer was wrong. Record in `upstream-feedback.md`. Fix upstream and regenerate. Do not patch downstream.
- Classify findings as PROJECT or METHODOLOGY. Project findings go to `upstream-feedback.md`. Methodology findings go to this repo. Do not mix.
- All reflect gate resolutions go to `upstream-feedback.md` — resolved and unresolved. Tag by stage and wave.

### Coordinator Discipline
- Coordinator manages context, not content. Do not write specs, scaffold, or code. Spawn agents with scoped context.
- Write coordinator playbook to disk: agent prompt template, per-spec file ownership, wave dependencies, reflect protocol. A fresh coordinator picks up from the playbook.
- Include explicit file ownership in every agent prompt: YOUR FILES (specific scaffold files) and OFF-LIMITS (everything else, including files that do not exist).
- Do not spawn an agent without a task checklist on disk. Derive the prompt from the checklist.
- Enforce claim ordering: use sequential spawn or coordinator pre-marking. Verify wave dependencies before claiming.
- Coordinator never idles. Spot-check output, update claims, write manifests, prep next wave, log findings.
- Wave context is the file tree, not a source dump. Agents read specific files on-demand.

## Stage Gate Cross-References

External skill rules that apply at each stage gate. Agents check these alongside DAG rules. Rule definitions live in their source skill — do not duplicate here. Record YES/NO/N/A per rule at each gate.

Source: `~/.skills/pragmatic-programmer/SKILL.md` (prefix `PP-`), `~/.skills/clean-architecture/SKILL.md` (prefix `CA-`), `~/.skills/implementation-coding-core/SKILL.md` (prefix `IC-`), `~/.skills/test-driven-development/SKILL.md` (prefix `TDD-`), `~/.skills/cs-foundations/SKILL.md` (prefix `CS-`)

### Stages 1-2 (Requirements)
- PP-REQ-1, PP-REQ-2, PP-REQ-3, PP-REQ-4 (discover with users, feedback loops, policy as metadata, glossary)
- PP-APPROACH-4 (keep options reversible — don't lock in HOW decisions)

### Stage 3 (Research)
- PP-APPROACH-1 (tracer bullets — thin end-to-end when surveying unknowns)
- PP-APPROACH-2 (prototypes to learn — disposable explorations before committing)

### Stage 4 (Decomposition)
- **CS-SEP-1 through CS-SEP-5** (full pass — read/write split, command/query, layers, bounded contexts, API surface)
- **CS-DATA-1 through CS-DATA-6** (full pass — ownership, state model, storage, schema, lifecycle, derived data)
- **CS-COMM-1 through CS-COMM-5** (full pass — sync/async, integrations, events, API style, serialization)
- **CS-CONSIST-1 through CS-CONSIST-5** (full pass — consistency model, transactions, concurrency, idempotency, ordering)
- **CS-SCALE-1 through CS-SCALE-5** (full pass — load, hot path, caching, Big-O, resource bounds)
- **CS-SEC-1 through CS-SEC-5** (full pass — trust boundaries, authn, authz, secrets, input validation)
- **CS-ERR-1 through CS-ERR-5** (full pass — failure taxonomy, retry, partial failure, degradation, observability)
- PP-ORTH-1, PP-ORTH-3 (decomposed specs are self-contained, changes don't ripple)
- PP-DRY-1 (no duplicated knowledge across spec units)
- CA-COMP-1 (no cycles in dependency graph)
- CA-COMP-4, CA-COMP-5 (classes that change together / are used together belong in same component)

### Stage 5 (Spec Tree)
- CA-SCRM-1, CA-SCRM-2 (tree communicates use cases, stranger understands domain from `tree`)
- PP-CRAFT-5 (names reveal intent)

### Stage 6 (Specifications)
- CS-* spot check (verify specs are consistent with Stage 4 decisions — new questions are findings)
- PP-CONTRACT-1 (preconditions, postconditions, invariants defined)
- PP-REQ-3 (policy is metadata — specs don't hardcode business rules)
- PP-REQ-4 (glossary — terms consistent across specs)
- TDD-COV-1, TDD-COV-2, TDD-COV-3 (contracts cover happy path, edge cases, error cases)
- CA-BOUND-3 (data crossing boundaries is simple structures)

### Stage 7 (Scaffolding)
- CS-* verify scaffold embodies Stage 4 decisions (event types exist if async, separate read/write models if CQRS, etc.)
- PP-APPROACH-3 (no broken windows — fix bad naming/structure immediately)
- PP-DRY-1, PP-DRY-2 (single source of truth, no inter-developer duplication)
- PP-ORTH-1 (components self-contained)
- IC-LAY-1, IC-LAY-2, IC-LAY-3 (layering discipline — structure before headers before signatures)
- IC-HDR-1 through IC-HDR-5 (every file has PURPOSE, RESPONSIBILITIES, NOT RESPONSIBLE FOR, DEPENDENCIES; headers permanent)
- CA-DEP-1, CA-DEP-2, CA-DEP-5 (dependencies inward, entities clean, DIP at boundaries)

### Stage 8 (Implementation)
- PP-CRAFT-1 (no programming by coincidence)
- PP-CRAFT-2 (Big-O considered)
- PP-CRAFT-3 (refactor on duplication or non-orthogonality)
- PP-CRAFT-4 (test-first drives design)
- PP-CRAFT-6 (small steps, check feedback)
- PP-CONTRACT-2 (crash early)
- PP-CONTRACT-3 (assertions for impossible conditions)
- PP-CONTRACT-4 (finish what you start)
- PP-DECOUPLE-1 through PP-DECOUPLE-5 (no train wrecks, Tell Don't Ask, Demeter, interfaces over inheritance, config externalized)
- TDD-CYC-1 through TDD-CYC-6 (full Red-Green-Refactor cycle)
- IC-SCALE-1 through IC-SCALE-4 (10x/100x/1000x, timeouts, streaming, assumptions documented)
- IC-DATA-1 through IC-DATA-5 (schema validation at boundaries)

### Stage 8b (Reconciliation)
- PP-DELIVER-4 (find bugs once — every bug gets a test)
- PP-DRY-2 (no inter-developer duplication across implemented specs)
- PP-ORTH-3 (change to one module doesn't ripple)
- IC-VER-1 through IC-VER-4 (compiles, imports correct, tests pass, verified before declaring done)
- TDD-QUAL-1 (tests verify behavior not implementation)

### Stage 9 (Verify)
- PP-DELIVER-1 (version control drives builds/tests/releases)
- PP-DELIVER-2 (no manual procedures)
- PP-DELIVER-3 (not done until all tests pass)
- PP-DELIVER-5 (state coverage, not just code coverage)
- CA-TEST-1, CA-TEST-2 (behavior not implementation, structured by use case)
- TDD-BUG-1 through TDD-BUG-4 (bug fix protocol — reproduce, confirm, fix, full suite)

## Iteration Lifecycle

Each pass through the DAG produces a complete snapshot:

```
.planning/
├── raw/REQUIREMENTS-RAW.md          # immutable
├── v1/
│   ├── dag.md                       # DAG definition for this iteration
│   ├── upstream-feedback.md         # findings from this iteration
│   ├── clean-requirements.md
│   ├── decomposition.md
│   └── spec-tree/
├── v2/
│   ├── dag.md                       # may differ from v1
│   ├── upstream-feedback.md         # includes v1 findings + new
│   └── ...
```

- Complete `upstream-feedback.md` before tagging an iteration closed. Classify and write back all verify fix log entries.
- To start v(N+1): read raw requirements + all `upstream-feedback.md` files. Re-derive everything. The DAG itself may evolve.
- Surgical iterations: when the codebase is stable and the addition is orthogonal, a single-spec streamlined path is permitted — no full fan-out required.
