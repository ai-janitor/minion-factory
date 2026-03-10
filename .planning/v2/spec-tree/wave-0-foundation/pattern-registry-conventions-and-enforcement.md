# SU-01: Pattern Registry — Conventions and Enforcement

**Wave:** 0 (foundation — blocks waves 3, 5)
**Requirements:** 2.9
**Dependencies:** None
**Dependents:** SU-08, SU-09, SU-10, SU-14

## Domain Preamble

The pattern registry is a documentation artifact that establishes decided conventions for error handling (raise vs return dict), DB access (get_db + cursor + try/finally), config resolution (defaults.py), logging setup, auth decoration, and message delivery patterns. It must exist before any code modification work begins because all subsequent spec units reference it for consistency. This is the single source of truth for "how we do X in this codebase." No code changes — pure documentation targeting `.work/pattern-registry.md`.

## Scope

- Create `.work/pattern-registry.md` documenting each cross-cutting convention
- Sections: Error Handling, DB Access, Config Resolution, Logging, Auth Decoration, Message Delivery, Contracts and Assertions, Documentation Conventions, Provider Error Classification
- Each section: current pattern (with code example), rationale, when to deviate

## Affected Files

- `.work/pattern-registry.md` (new)

## Boundary Edges

- E-01: → SU-08 (convention: error handling)
- E-02: → SU-09 (convention: assertion patterns)
- E-03: → SU-10 (convention: documentation format)
- E-04: → SU-14 (convention: canonical patterns for deduplication)
