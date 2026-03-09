# Raw Requirements — Minion Factory Codebase Audit

Captured: 2026-03-09

## What the user said

Audit the minion-factory codebase against the codified skill checklists. The codebase is written and working — this is not greenfield planning, it's a retrospective audit of an existing system.

### Audit scope

Run every applicable skill checklist against the minion-factory codebase and produce findings. The skills with mandatory compliance checklists are:

1. **cs-foundations** (37 rules) — SEP, DATA, COMM, CONSIST, SCALE, SEC, ERR
2. **clean-architecture** (25 rules) — DEP, SOLID, COMP, BOUND, SCRM, TEST
3. **pragmatic-programmer** (33 rules) — DRY, ORTH, DECOUPLE, CONTRACT, CRAFT, DELIVER, REQ, APPROACH
4. **implementation-coding-core** (24 rules) — LAY, HDR, SCALE, DATA, VER
5. **test-driven-development** (19 rules) — CYC, QUAL, COV, BUG
6. **fast-api** (24 rules) — ARC, ERR, DI, PRD, REF (if applicable — minion-factory has a network API server)
7. **ai-first-cli** (19 rules) — CMD, OUT, DISC, CFG, AGENT (minion is a CLI tool consumed by AI agents)
8. **ai-first-api** (37 rules) — ROUTE, CONF, TOK, CLI, SPEC, INFRA, DOC, PLAN (if applicable — network API)

Total: 218 rules across 8 skills.

### What we want out of this

- A completed YES/NO/N/A checklist per skill, with evidence for every rule
- Findings list: every NO with severity (critical / major / minor), affected files, and what needs to change
- A prioritized remediation backlog — what to fix first based on impact
- Identification of patterns that are already strong (what the codebase gets right)

### Constraints

- This is an audit, not a rewrite. Findings should be actionable without redesigning the system
- The codebase is ~150 Python source files, 20 tests, 11 mission templates, 7 agent roles, 10 capabilities
- The CLI is the primary interface — AI agents consume it via `minion` commands
- There is a network API server (`src/minion/network/`) — FastAPI-based
- The codebase already follows its own CLAUDE.md conventions (scaffold-first, filesystem-as-db, comment headers)
- Use two-pass audit per MANIFESTO.md: Pass 1 (broad sweep) then Pass 2 (deep dive per domain)

### Domains for decomposition

Natural audit units based on the codebase structure:

- **CLI layer** — `src/minion/cli/` (17 command files)
- **Database layer** — `src/minion/db/` (schema, migrations, connection, agents, messages)
- **Comms system** — `src/minion/comms/` (send, inbox, routing, delivery)
- **Task engine** — `src/minion/tasks/` (DAG, gates, flow, create/update/close)
- **Crew & lifecycle** — `src/minion/crew/`, `src/minion/lifecycle.py` (spawn, terminal, daemon)
- **Daemon runtime** — `src/minion/daemon/` (runner, watcher, buffer, triggers)
- **Network API** — `src/minion/network/` (server, router, handlers, auth, discovery)
- **Intel system** — `src/minion/intel/` (docs, search, linking, war plans)
- **Providers** — `src/minion/providers/` (claude, codex, gemini, opencode)
- **Prompts** — `src/minion/prompts/` (roles, capabilities, boot, system)
- **Requirements** — `src/minion/requirements/` (crud, decompose, findings)
- **Tests** — `tests/` (coverage, quality, naming)
- **Backlog** — `src/minion/backlog/` (items, lineage, promote)
- **Missions** — `src/minion/missions/`, `missions/` (loader, resolver, YAML templates)
- **Cross-cutting** — auth.py, monitoring.py, filesafety.py, output.py, triggers.py, defaults.py, fs.py
