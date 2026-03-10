# Research: WS5 Features — Existing Code Survey

## 5.1 Network API Evolution
- **CLI parity:** Network API has handlers for core, projects, backlog, requirements, flows, overview, scaling, compat. ~10 CLI commands may still lack network equivalents.
- **Agent presence:** `src/minion/network/handlers/overview.py` exists — provides aggregated data across projects. GET /who filtering needs verification.
- **Agent registry schema:** Coordinator DB has agents table with project_path, scope_mode columns. Basic cross-machine awareness exists.
- **Composite agent key:** Currently name-only in most places. host/project/name composite key NOT implemented.
- **6 sys-lead gaps:** overview.py was added in v1 but 6 specific gaps (lineage, alerts, query params, DB policy, full agent view) need verification.
- **On-demand spawning:** scaling.py handler exists but may be unreachable.

## 5.2 Cross-Project Coordination
- **Cross-project lead:** Coordinator DB exists (~/.minion/coordinator.db). `send_global()` routes through coordinator. But aggregated polling at parent dir does NOT exist.
- **Project leads to sys-lead:** Global comms work via `minion comms send global`. Auth scope system exists (SCOPE_RESTRICTIONS in auth.py with "sys" scope). PARTIALLY IMPLEMENTED.
- **Coordinator agent class:** Not in agent-classes.yaml yet. Auth.py has "sys" scope mode but no "coordinator" class.

## 5.3 Agent Experience
- **Context refresh:** `minion refresh` command exists (lightweight mid-session state refresh). IMPLEMENTED.
- **Cold-start auto-generate:** `minion cold-start` exists. Returns onboarding info but unclear if it auto-generates live briefing vs static files.
- **Error remediation hints:** `src/minion/output.py` has `_add_remediation_hint()` with pattern-matching hints. IMPLEMENTED.
- **Fuzzy matching:** `src/minion/cli/main.py` FuzzyGroup class exists with difflib.get_close_matches. IMPLEMENTED.
- **Shell completions:** NOT IMPLEMENTED. Click supports it natively but no `_MINION_COMPLETE` setup found.
- **Research prompt assembly:** Prompt system exists in `src/minion/prompts/` with roles, boot, inbox, protocol modules. Specific "research prompt assembly strategy" needs clarification.

## 5.4 System Integrity
- **Auth scope narrowing:** SCOPE_RESTRICTIONS dict in auth.py with require_scope() decorator. IMPLEMENTED.
- **DAG scaffolding enforcement:** NOT IMPLEMENTED mechanically (prompt-level only).
- **Cycle detection at YAML load:** `src/minion/tasks/loader.py` has `_detect_cycles()` called on flow load. IMPLEMENTED.

## 5.5 Dashboard and UI
- **Dashboard:** `src/minion/dashboard/` exists with loop.py, queries.py, render.py. Basic dashboard exists.
- **GUI merge into network server:** `src/minion/network/dashboard.py` exists. Status unclear — may be stub or partial.
