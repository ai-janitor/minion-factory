"""Validation constants for task flow YAML schema."""

REQUIRED_STAGE_KEYS = {"description"}
TERMINAL_STAGE_KEYS = {"description", "terminal", "workers", "protocol"}
VALID_STAGE_KEYS = {
    "description", "next", "fail", "alt_next",
    "workers", "requires", "terminal", "skip", "parked",
    "spawns", "protocol", "context", "context_template",
}
REQUIRED_TOP_KEYS = {"name", "description", "stages"}
VALID_TOP_KEYS = {"name", "description", "stages", "inherits", "dead_ends", "shortcuts"}
