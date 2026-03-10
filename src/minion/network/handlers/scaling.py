"""Elastic scaling endpoints — POST /spawn, GET /capacity.

Purpose: Enable dynamic agent provisioning and machine capacity monitoring.
Rationale: Leads need to spawn agents on demand — especially on remote machines
           with GPU capacity. The capacity endpoint lets them see where slots
           are available before deciding where to spawn.
Responsibility: Spawn orchestration (501 stub for now), capacity aggregation
                from network DB agent data.
Organization: Two endpoints — spawn (write, future) and capacity (read, now).

Implementation order: 9th (last — spawn is a stub, capacity reads network DB).

SU-17 decision: KEPT but not wired to router. Scaling is deferred to v3.
Not registered in router.py — endpoints are unreachable by design.
"""

from __future__ import annotations


def register(router) -> None:
    """Register scaling endpoints with the router dispatch table.

    POST /spawn    → handle_spawn
    GET  /capacity → handle_capacity
    """
    router.add_post("/spawn", handle_spawn)
    router.add_get("/capacity", handle_capacity)


def handle_spawn(handler, db_path: str, **kwargs) -> None:
    """POST /spawn — spawn an agent on a target machine (501 NOT IMPLEMENTED stub).

    Request body: {"class": "coder", "capabilities": [...], "crew": "...",
                   "target_machine": "...", "task_id": N, "project_path": "..."}
    Required: class. Optional: capabilities, crew, target_machine, task_id, project_path.

    Returns 501 with schema-valid response shape — contract defined now,
    implementation deferred until SSH remote spawn is built.

    Constraints (for future implementation):
    - Max concurrent agents per machine: MINION_MAX_AGENTS (default 5)
    - Spawn cooldown: 30s between spawns on same machine
    - HP budget: won't spawn if estimated token cost exceeds budget
    - Remote spawn: requires SSH access + minion installed on target
    """
    # PSEUDO: parse JSON body → 400 if invalid
    # PSEUDO: validate required field: class → 400 if missing
    # PSEUDO: return 501 with stub response:
    #   {"status": "not_implemented",
    #    "message": "Elastic spawn is not yet available",
    #    "schema": {"agent": "string", "machine": "string", "estimated_boot_time_s": "int"}}
    handler._json_response(501, {
        "status": "not_implemented",
        "message": "Elastic spawn is not yet available",
        "schema": {"agent": "string", "machine": "string", "estimated_boot_time_s": "int"},
    })


def handle_capacity(handler, db_path: str, **kwargs) -> None:
    """GET /capacity — machine capacity for agent spawning decisions.

    Aggregates from network DB agents table:
    - Group agents by machine_id
    - Count running agents per machine
    - Read machine_specs for hardware info
    - Compute available_slots = MINION_MAX_AGENTS - running_count

    Response: {"machines": [{"machine_id": "...", "running_agents": N,
               "max_agents": N, "available_slots": N, "specs": {...}}]}
    """
    # PSEUDO: max_agents = int(os.environ.get("MINION_MAX_AGENTS", "5"))
    # PSEUDO: with DB_LOCK:
    #   SELECT machine_id, COUNT(*) as running, machine_specs
    #   FROM agents
    #   WHERE last_seen > now - 5min  (only online agents count)
    #   GROUP BY machine_id
    # PSEUDO: for each machine:
    #   specs = json.loads(machine_specs) if machine_specs else {}
    #   available_slots = max_agents - running
    # PSEUDO: return {"machines": [...]}
    handler._json_response(501, {
        "status": "not_implemented",
        "message": "Capacity endpoint is not yet available",
        "schema": {"machines": [{"machine_id": "string", "running_agents": "int",
                    "max_agents": "int", "available_slots": "int", "specs": "object"}]},
    })
