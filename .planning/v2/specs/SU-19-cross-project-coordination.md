# SU-19: Cross-Project Coordination — Polling, Coordinator Class, Reporting

**Wave:** 6 (depends on SU-04)
**Requirements:** 5.2
**Dependencies:** SU-04, SU-07 (soft — coordinator auth)
**Dependents:** None

---

## Purpose

Implement the cross-project coordination layer: aggregated multi-project polling, coordinator agent class, and project lead -> sys-lead reporting via global comms.

## Requirements Traceability

- **5.2 (Cross-Project Coordination):** "Cross-project lead with aggregated polling, project leads report to sys-lead, coordinator agent class."

## Dependencies

- **SU-04 (Global Comms):** Cross-project coordination requires reliable cross-repo message delivery. SU-04 must fix edge cases first.
- **SU-07 (Backlog Auth):** Coordinator class needs appropriate permissions. SU-07 hardens auth — coordinator class must be included.

## Behavior

### Aggregated Multi-Project Polling

**Current state:** Each agent polls within one project. No mechanism for a coordinator to poll across multiple projects simultaneously.

**Target:**
- New function: `multi_project_poll(agent_name: str, project_paths: list[str]) -> dict`
- Iterates coordinator DB to find all projects where the agent (or their subordinates) have registered agents
- For each project: check for unread messages and available tasks (same logic as single-project poll, but against each project's `.work/minion.db`)
- Returns aggregated results: `{"projects": [{"path": "/path/a", "messages": [...], "tasks": [...]}, ...]}`
- Falls back to single-project poll if coordinator DB is unavailable

**Discovery of project paths:**
- Primary: query coordinator DB `agents` table for distinct `project_path` values where scope_mode matches the coordinator's scope
- Fallback: `MINION_PROJECTS` env var (colon-separated list of paths)

### Coordinator Agent Class

**Current state:** No "coordinator" class in agent-classes.yaml. Auth.py has "sys" scope mode but scope is about visibility, not class.

**Target:**
- Add `coordinator` to `src/minion/crew/agent-classes.yaml`:
  ```yaml
  coordinator:
    capabilities: [manage, monitor, investigate, plan]
    models: [claude-opus-4, claude-sonnet-4]
    description: "System-wide lead over multiple project leads"
  ```
- Auth.py: coordinator class gets same permissions as lead PLUS cross-project capabilities
- The coordinator class can: register/deregister agents across projects, send global messages, view aggregated status, spawn parties in multiple projects
- Update VALID_CLASSES fallback set to include "coordinator"

**Contract (E-12):** Coordinator class has all lead permissions plus: `backlog add/update/close` on any project (no -C auth block for coordinators).

### Project Lead -> Sys-Lead Reporting

**Current state:** Global comms work via `minion comms send global`. Leads can send to sys-lead manually.

**Target:**
- Formalize reporting: when a project lead completes a milestone (all tasks in a wave closed), automatically send a sitrep to sys-lead via global comms
- Trigger: `complete_phase()` on the last task in a wave could trigger the report
- Message format: `{"msg_type": "sitrep", "content": "Wave N complete. Summary: X tasks closed, Y blocked."}`
- This is advisory — the report is sent, not required. If global comms fail, the lead continues working.

**Alternatively:** Provide a `minion sitrep --to sys-lead --scope global` command that project leads run manually. This is simpler and doesn't require automatic triggers.

## Constraints

- Must not break single-project polling (multi-project is additive)
- Coordinator class must be backward-compatible with existing auth checks
- Global comms must be reliable (SU-04) before this work begins
- Performance: multi-project poll iterates N projects with N DB queries. Keep N reasonable (< 20 projects).

## Edge Cases

1. **Project DB missing:** A project path in coordinator DB points to a deleted directory. Skip gracefully, log warning.
2. **Agent not registered in some projects:** Coordinator polls projects where they have no agents. Return empty results for those projects, don't error.
3. **Coordinator DB locked:** If coordinator DB is locked during multi-project poll, retry once after 1s, then fail gracefully.
4. **Circular reporting:** Sys-lead is both the coordinator and a project lead. Reporting to self should be detected and skipped.
5. **No coordinator DB:** If `~/.minion/coordinator.db` doesn't exist, multi-project poll falls back to current single-project behavior.

## Current State

- Coordinator DB exists (~/.minion/coordinator.db)
- Global comms work via send_global()
- SCOPE_RESTRICTIONS in auth.py support "sys" scope
- No coordinator class in agent-classes.yaml
- No multi-project polling

## Test Contract

- **Test 1:** `multi_project_poll()` with 2 project paths returns aggregated results from both.
- **Test 2:** Register agent with class "coordinator". Assert valid registration.
- **Test 3:** Coordinator can `backlog add` on a foreign project without auth block.
- **Test 4:** `multi_project_poll()` with one invalid project path skips it gracefully.
- **Test 5:** `minion sitrep --to sys-lead --scope global` sends a global message.
