# Raw-to-Clean Traceability — v1

Every item in REQUIREMENTS-RAW.md mapped to its clean requirement or out-of-scope entry.

## Reconciliation Notes

- Existing REQUIREMENTS.md at project root describes the original BUILD scope (merge 3 repos into one). It is not audit requirements — it is **context for the audit** (tells us what the system was designed to do).
- No upstream-feedback.md exists (this is v1). No prior clean requirements for audit scope.
- Unbiased derivation is the final clean — no reconciliation changes needed.

## Trace

| Raw Item | Clean Requirement | Notes |
|----------|-------------------|-------|
| "Audit the minion-factory codebase against codified skill checklists" | §1 Audit Objective | Verbatim intent |
| "The codebase is written and working — not greenfield" | §6 Constraints (audit only) | Constraint on scope |
| Skill list (8 skills, 218 rules) | §2.1 Skill Checklists table | All 8 captured with rule counts |
| "Completed YES/NO/N/A checklist per skill" | §5.1 Completed Checklists | Direct map |
| "Findings list: every NO with severity" | §5.2 Findings List | Direct map |
| "Prioritized remediation backlog" | §5.3 Remediation Backlog | Direct map, added prioritization criteria |
| "Identification of patterns already strong" | §5.4 Strengths Report | Direct map |
| "This is an audit, not a rewrite" | §6 Constraints | Direct map |
| "~150 Python source files, 20 tests..." | §2.2 Codebase Under Audit | Direct map |
| "CLI is primary interface" | §2.2 + D1 primary skills | Direct map |
| "Network API server (FastAPI)" | §2.2 + D7 primary skills | Direct map |
| "Follows own CLAUDE.md conventions" | §6 Constraints (respect existing conventions) | Direct map |
| "Two-pass audit per MANIFESTO.md" | §4.1 Two-Pass Audit | Direct map |
| 15 domains for decomposition | §3 Audit Domains table (D1-D15) | All 15 captured, added primary skills per domain |
| (implicit) evidence per rule | §4.2 Evidence Requirements | Derived from checklist format — not explicitly stated but required by checklist pattern |

## Coverage

- **All raw items traced:** YES
- **Items added by derivation (not in raw):** §4.2 Evidence Requirements (implicit in checklist format), prioritization criteria in §5.3 (effort + blast radius added to severity)
- **Out-of-scope items:** None
