"""Validation constants for task flow YAML schema.

Purpose: Validation constants for task flow YAML schema.
Rationale: Extracted into own module for single-responsibility task management.
Responsibility: Validation constants for task flow YAML schema. NOT responsible for unrelated concerns.
Organization: Standalone functions and/or a single class. See source."""

REQUIRED_STAGE_KEYS = {"description"}
TERMINAL_STAGE_KEYS = {"description", "terminal", "workers", "protocol"}
VALID_STAGE_KEYS = {
    "description", "next", "fail", "alt_next",
    "workers", "requires", "terminal", "skip", "parked",
    "spawns", "protocol", "context", "context_template", "gate",
}
REQUIRED_TOP_KEYS = {"name", "description", "stages"}
VALID_TOP_KEYS = {"name", "description", "stages", "inherits", "dead_ends", "shortcuts"}
