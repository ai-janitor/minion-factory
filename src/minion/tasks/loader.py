"""YAML loading, inheritance resolution, and validation for task flow DAGs.

Purpose: YAML loading, inheritance resolution, and validation for task flow DAGs.
Rationale: Extracted into own module for single-responsibility task management.
Responsibility: YAML loading, inheritance resolution, and validation for task flow DAGs. NOT responsible for unrelated concerns.
Organization: Standalone functions and/or a single class. See source.

ASSUMPTIONS:
- Flow YAML search order: MINION_FLOWS_DIR env > ~/.minion/task-flows/ > bundled
  package dir > repo root task-flows/. The FIRST existing directory wins — there is
  no merge across directories. If a user overrides with env var, bundled flows are
  completely invisible.
- _DEFAULT_FLOWS_DIR is resolved at module import time and cached. If the flows
  directory is created after the first import, it won't be found until process restart.
- Flow inheritance (_resolve_inheritance) is single-parent only. A flow can inherit
  from one parent via the 'inherits' key. There is no multiple inheritance or mixin
  support. Circular inheritance will cause infinite recursion (no cycle detection).
- Stage merging during inheritance: override stages REPLACE base stage keys entirely
  at the per-key level (shallow merge per stage). If a base stage has 5 keys and the
  override specifies 2, the result has all 5 with 2 overridden. But nested dicts
  within stage values are NOT deep-merged — they're replaced wholesale.
- _FLOW_CACHE is never invalidated. Flows are loaded once per process. Hot-reloading
  flow YAML requires process restart.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import yaml

from ._schema import REQUIRED_TOP_KEYS, VALID_STAGE_KEYS, VALID_TOP_KEYS
from .dag import Stage, TaskFlow

log = logging.getLogger(__name__)

# Search order: env var, ~/.minion/task-flows/, bundled with package
def _find_flows_dir() -> Path:
    from minion.defaults import resolve_flows_dir
    env = resolve_flows_dir()
    if env:
        return Path(env)
    user_dir = Path.home() / ".minion" / "task-flows"
    if user_dir.exists():
        return user_dir
    # Bundled inside the installed package (force-included by pyproject.toml)
    bundled = Path(__file__).resolve().parent.parent / "task-flows"
    if bundled.exists():
        return bundled
    # Dev fallback: task-flows/ at repo root
    return Path(__file__).resolve().parent.parent.parent.parent / "task-flows"


_DEFAULT_FLOWS_DIR = _find_flows_dir()


def _bundled_protocols_dir() -> Path:
    """Return the bundled protocols directory from the installed package."""
    bundled = Path(__file__).resolve().parent.parent / "task-flows" / "protocols"
    if bundled.exists():
        return bundled
    # Dev fallback
    return Path(__file__).resolve().parent.parent.parent.parent / "task-flows" / "protocols"


def get_protocols_dir() -> Path:
    """Return the resolved protocols directory.

    Search order:
    1. .work/protocols/ in project root (project-local, editable)
    2. Bundled package (seed source — copied to .work/protocols/ on first access)

    If .work/protocols/ doesn't exist, seed it from the bundled package so the
    project has its own editable copy.
    """
    import shutil
    from minion.defaults import resolve_db_path

    # Resolve project .work/ dir from DB path
    db_path = resolve_db_path()
    work_dir = Path(db_path).parent  # .work/
    local_protocols = work_dir / "protocols"

    if local_protocols.exists():
        return local_protocols

    # Seed from bundled package
    bundled = _bundled_protocols_dir()
    if bundled.exists():
        shutil.copytree(bundled, local_protocols)
        return local_protocols

    # Fallback to bundled if copy failed
    return _DEFAULT_FLOWS_DIR / "protocols"

# Runtime cache — loaded once, kept in memory
_FLOW_CACHE: dict[str, TaskFlow] = {}
_FLOWS_LOADED = False


def _load_yaml(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def _merge_stages(base_stages: dict, override_stages: dict | None) -> dict:
    """Deep-merge override stages into base. Override keys replace base keys per-stage."""
    if not override_stages:
        return dict(base_stages)
    merged = {}
    for name, base_cfg in base_stages.items():
        if name in override_stages:
            merged[name] = {**base_cfg, **override_stages[name]}
        else:
            merged[name] = dict(base_cfg)
    for name, cfg in override_stages.items():
        if name not in merged:
            merged[name] = dict(cfg)
    return merged


def _resolve_inheritance(raw: dict, flows_dir: Path) -> dict:
    """If flow has `inherits`, load the parent and merge."""
    parent_name = raw.get("inherits")
    if not parent_name:
        return raw
    parent_path = flows_dir / f"{parent_name}.yaml"
    if not parent_path.exists():
        raise FileNotFoundError(f"Parent flow '{parent_name}' not found at {parent_path}")
    parent_raw = _load_yaml(parent_path)
    parent_raw = _resolve_inheritance(parent_raw, flows_dir)
    merged_stages = _merge_stages(parent_raw.get("stages", {}), raw.get("stages"))
    result = {**parent_raw, **raw}
    result["stages"] = merged_stages
    result.pop("inherits", None)
    return result


def _validate(raw: dict, name: str, flows_dir: Path | None = None) -> None:
    """Validate flow YAML — hard fail on any structural error."""
    # Top-level keys
    missing = REQUIRED_TOP_KEYS - set(raw.keys())
    if missing:
        raise ValueError(f"Flow '{name}' missing required keys: {missing}")
    unknown_top = set(raw.keys()) - VALID_TOP_KEYS
    if unknown_top:
        raise ValueError(f"Flow '{name}' has unknown top-level keys: {unknown_top}")

    stages = raw.get("stages", {})
    if not stages:
        raise ValueError(f"Flow '{name}' has no stages")

    stage_names = set(stages.keys())
    resolve_dir = flows_dir or _DEFAULT_FLOWS_DIR

    for stage_name, cfg in stages.items():
        _pfx = f"Flow '{name}', stage '{stage_name}'"

        # Every stage must have description
        if not cfg.get("description"):
            raise ValueError(f"{_pfx}: missing 'description'")

        # Unknown keys
        unknown = set(cfg.keys()) - VALID_STAGE_KEYS
        if unknown:
            raise ValueError(f"{_pfx}: unknown keys {unknown}")

        # Skip/terminal/parked stages don't need next
        if cfg.get("skip") or cfg.get("terminal") or cfg.get("parked"):
            continue

        if "next" not in cfg:
            raise ValueError(f"{_pfx}: non-terminal stage must have 'next'")

        # Validate stage references point to existing stages
        for ref_key in ("next", "fail", "alt_next"):
            ref = cfg.get(ref_key)
            if ref and ref not in stage_names:
                raise ValueError(f"{_pfx}: '{ref_key}' references unknown stage '{ref}'")

        # spawns must reference a loadable flow YAML
        spawns = cfg.get("spawns")
        if spawns:
            spawns_path = resolve_dir / f"{spawns}.yaml"
            if not spawns_path.exists():
                # Also check _base pattern
                spawns_base = resolve_dir / f"_{spawns}.yaml"
                if not spawns_base.exists():
                    raise ValueError(
                        f"{_pfx}: 'spawns' references unknown flow '{spawns}' "
                        f"(no {spawns_path} found)"
                    )

        # protocol must reference an existing file
        protocol = cfg.get("protocol")
        if protocol:
            protocol_path = resolve_dir / protocol
            if not protocol_path.exists():
                raise ValueError(
                    f"{_pfx}: 'protocol' file not found: {protocol}"
                )

        # context_template must reference an existing file
        ctx_tmpl = cfg.get("context_template")
        if ctx_tmpl:
            tmpl_path = resolve_dir / ctx_tmpl
            if not tmpl_path.exists():
                raise ValueError(
                    f"{_pfx}: 'context_template' file not found: {ctx_tmpl}"
                )

        # workers class names must exist in agent class registry
        workers = cfg.get("workers")
        if workers:
            from .agent_classes import get_valid_classes

            valid_classes = get_valid_classes()
            if isinstance(workers, list):
                unknown_cls = set(workers) - valid_classes
                if unknown_cls:
                    raise ValueError(f"{_pfx}: unknown agent classes in 'workers': {unknown_cls}")
            elif isinstance(workers, dict):
                for key, class_list in workers.items():
                    if key != "default" and key not in valid_classes:
                        raise ValueError(f"{_pfx}: unknown class_required key '{key}' in 'workers'")
                    if isinstance(class_list, list):
                        unknown_cls = set(class_list) - valid_classes
                        if unknown_cls:
                            raise ValueError(
                                f"{_pfx}: unknown agent classes in 'workers.{key}': {unknown_cls}"
                            )

    # --- Cycle detection ---
    # After all per-stage validation, check for cycles in the DAG using DFS.
    # Edges: next, fail, alt_next. A cycle means the flow can never terminate.
    _detect_cycles(stages, name)


def _detect_cycles(stages: dict, flow_name: str) -> None:
    """Detect cycles in the forward-progress edges of the stage graph using 3-color DFS.

    Only checks 'next' and 'alt_next' edges — 'fail' edges intentionally point
    backward for rework/retry and are excluded from cycle detection.
    If a back-edge is found (gray node visited again), raises ValueError with the cycle path.
    """
    # Build adjacency list from forward-progress edges only (next, alt_next)
    adj: dict[str, list[str]] = {s: [] for s in stages}
    for stage_name, cfg in stages.items():
        for edge_key in ("next", "alt_next"):
            target = cfg.get(edge_key)
            if target and target in stages:
                adj[stage_name].append(target)

    # DFS with 3 colors: white=unvisited, gray=in-stack, black=done
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {s: WHITE for s in stages}
    parent: dict[str, str | None] = {s: None for s in stages}

    def _dfs(node: str) -> list[str] | None:
        """Returns cycle path if found, else None."""
        color[node] = GRAY
        for neighbor in adj[node]:
            if color[neighbor] == GRAY:
                # Back-edge found — reconstruct cycle
                cycle = [neighbor, node]
                cursor = node
                while cursor != neighbor:
                    cursor = parent[cursor]  # type: ignore[assignment]
                    if cursor is None:
                        break
                    cycle.append(cursor)
                cycle.reverse()
                return cycle
            if color[neighbor] == WHITE:
                parent[neighbor] = node
                result = _dfs(neighbor)
                if result is not None:
                    return result
        color[node] = BLACK
        return None

    for stage_name in stages:
        if color[stage_name] == WHITE:
            cycle = _dfs(stage_name)
            if cycle is not None:
                cycle_str = " -> ".join(cycle)
                raise ValueError(
                    f"Flow '{flow_name}' contains a cycle: {cycle_str}. "
                    f"DAG flows must be acyclic — check next/fail/alt_next edges."
                )


def _build_stage(name: str, cfg: dict) -> Stage:
    return Stage(
        name=name,
        description=cfg.get("description", ""),
        next=cfg.get("next"),
        fail=cfg.get("fail"),
        alt_next=cfg.get("alt_next"),
        workers=cfg.get("workers"),
        requires=cfg.get("requires", []),
        terminal=cfg.get("terminal", False),
        skip=cfg.get("skip", False),
        parked=cfg.get("parked", False),
        spawns=cfg.get("spawns"),
        protocol=cfg.get("protocol"),
        context=cfg.get("context"),
        context_template=cfg.get("context_template"),
        gate=cfg.get("gate"),
    )


def _load_all_flows(flows_dir: Path | None = None) -> None:
    """Load all flows from disk into memory cache. Called once."""
    global _FLOWS_LOADED
    flows_path = flows_dir or _DEFAULT_FLOWS_DIR
    if not flows_path.exists():
        _FLOWS_LOADED = True
        return
    for p in sorted(flows_path.glob("*.yaml")):
        name = p.stem
        if name.startswith("_"):
            continue  # skip _base.yaml (only used for inheritance)
        try:
            flow = _load_flow_from_disk(name, flows_path)
            _FLOW_CACHE[name] = flow
        except (ValueError, FileNotFoundError, KeyError) as exc:
            log.warning("failed to load flow %r: %s", name, exc)
    _FLOWS_LOADED = True


def _load_flow_from_disk(task_type: str, flows_path: Path) -> TaskFlow:
    """Load a single flow from YAML, resolving inheritance."""
    filename = f"_{task_type}.yaml" if task_type == "base" else f"{task_type}.yaml"
    flow_path = flows_path / filename
    if not flow_path.exists():
        raise FileNotFoundError(f"Task flow '{task_type}' not found at {flow_path}")
    raw = _load_yaml(flow_path)
    raw = _resolve_inheritance(raw, flows_path)
    _validate(raw, task_type, flows_dir=flows_path)
    stages = {name: _build_stage(name, cfg) for name, cfg in raw["stages"].items()}
    return TaskFlow(
        name=raw["name"],
        description=raw.get("description", ""),
        stages=stages,
        dead_ends=raw.get("dead_ends", []),
    )


def load_flow(task_type: str, flows_dir: str | Path | None = None) -> TaskFlow:
    """Load a task flow DAG by type name. Returns from cache if already loaded."""
    # Precondition assertion — backlog #63
    assert task_type, "task_type must not be empty"

    if not _FLOWS_LOADED:
        _load_all_flows(Path(flows_dir) if flows_dir else None)
    if task_type in _FLOW_CACHE:
        return _FLOW_CACHE[task_type]
    # Not in cache — try loading from disk (custom type added after startup)
    flows_path = Path(flows_dir) if flows_dir else _DEFAULT_FLOWS_DIR
    flow = _load_flow_from_disk(task_type, flows_path)
    _FLOW_CACHE[task_type] = flow
    return flow


def list_flows(flows_dir: str | Path | None = None) -> list[str]:
    """List available task type names."""
    if not _FLOWS_LOADED:
        _load_all_flows(Path(flows_dir) if flows_dir else None)
    return sorted(_FLOW_CACHE.keys())


def list_flows_detailed(flows_dir: str | Path | None = None) -> list[dict]:
    """List all flows with description, stage pipeline, and use-case guidance."""
    if not _FLOWS_LOADED:
        _load_all_flows(Path(flows_dir) if flows_dir else None)
    result = []
    for name in sorted(_FLOW_CACHE.keys()):
        flow = _FLOW_CACHE[name]
        # Build ordered stage pipeline (skip → resolved, show only non-skip)
        pipeline = [
            s.name for s in flow.stages.values()
            if not s.skip
        ]
        result.append({
            "name": flow.name,
            "description": flow.description,
            "pipeline": " → ".join(pipeline),
            "stages": len(pipeline),
        })
    return result
