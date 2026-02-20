"""Greedy set-cover: required capabilities → minimum class slots."""

from __future__ import annotations

from minion.auth import CLASS_CAPABILITIES, VALID_CAPABILITIES


def resolve_slots(capabilities: set[str]) -> list[str]:
    """Find minimum set of classes covering all required capabilities.

    1. Always start with lead
    2. Remove capabilities covered by lead
    3. Greedy: pick class covering most uncovered, repeat
    4. Return sorted list of class names
    """
    invalid = capabilities - VALID_CAPABILITIES
    if invalid:
        raise ValueError(f"Unknown capabilities: {sorted(invalid)}")

    slots: list[str] = ["lead"]
    uncovered = capabilities - CLASS_CAPABILITIES["lead"]

    while uncovered:
        best_class = ""
        best_count = 0
        # Deterministic tiebreak: alphabetical
        for cls in sorted(CLASS_CAPABILITIES):
            if cls == "lead":
                continue
            overlap = len(uncovered & CLASS_CAPABILITIES[cls])
            if overlap > best_count:
                best_count = overlap
                best_class = cls
        if best_count == 0:
            break  # shouldn't happen with valid capabilities
        slots.append(best_class)
        uncovered -= CLASS_CAPABILITIES[best_class]

    return sorted(slots)
