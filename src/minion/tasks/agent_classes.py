"""Load agent class registry from YAML — single source of truth for class definitions."""

from __future__ import annotations

from pathlib import Path

import yaml

# Populated on first access
_REGISTRY: dict | None = None
_CLASS_CAPABILITIES: dict[str, set[str]] | None = None
_CLASS_MODELS: dict[str, set[str]] | None = None
_VALID_CLASSES: set[str] | None = None
_VALID_CAPABILITIES: set[str] | None = None


def _find_registry_path() -> Path:
    """Same search order as loader._find_flows_dir()."""
    from .loader import _find_flows_dir

    return _find_flows_dir() / "_agent-classes.yaml"


def _load() -> None:
    """Load and validate the agent class registry. Hard fail on any error."""
    global _REGISTRY, _CLASS_CAPABILITIES, _CLASS_MODELS, _VALID_CLASSES, _VALID_CAPABILITIES

    path = _find_registry_path()
    if not path.exists():
        raise FileNotFoundError(f"Agent class registry not found at {path}")

    with open(path) as f:
        raw = yaml.safe_load(f)

    valid_caps = set(raw.get("capabilities", []))
    if not valid_caps:
        raise ValueError(f"agent-classes.yaml: 'capabilities' list is empty")

    classes = raw.get("classes", {})
    if not classes:
        raise ValueError(f"agent-classes.yaml: 'classes' dict is empty")

    caps: dict[str, set[str]] = {}
    models: dict[str, set[str]] = {}

    for cls_name, cfg in classes.items():
        cls_caps = set(cfg.get("capabilities", []))
        unknown = cls_caps - valid_caps
        if unknown:
            raise ValueError(
                f"agent-classes.yaml: class '{cls_name}' has unknown capabilities {unknown}"
            )
        caps[cls_name] = cls_caps
        models[cls_name] = set(cfg.get("models", []))

    _REGISTRY = raw
    _CLASS_CAPABILITIES = caps
    _CLASS_MODELS = models
    _VALID_CLASSES = set(classes.keys())
    _VALID_CAPABILITIES = valid_caps


def get_class_capabilities() -> dict[str, set[str]]:
    if _CLASS_CAPABILITIES is None:
        _load()
    return _CLASS_CAPABILITIES  # type: ignore[return-value]


def get_class_models() -> dict[str, set[str]]:
    if _CLASS_MODELS is None:
        _load()
    return _CLASS_MODELS  # type: ignore[return-value]


def get_valid_classes() -> set[str]:
    if _VALID_CLASSES is None:
        _load()
    return _VALID_CLASSES  # type: ignore[return-value]


def get_valid_capabilities() -> set[str]:
    if _VALID_CAPABILITIES is None:
        _load()
    return _VALID_CAPABILITIES  # type: ignore[return-value]


def classes_with(capability: str) -> set[str]:
    """Return all classes that have a given capability."""
    caps = get_class_capabilities()
    valid = get_valid_capabilities()
    if capability not in valid:
        raise ValueError(f"Unknown capability {capability!r}. Valid: {sorted(valid)}")
    return {cls for cls, cls_caps in caps.items() if capability in cls_caps}
