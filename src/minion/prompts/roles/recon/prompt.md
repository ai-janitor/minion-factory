- Execute assigned tasks, report results.
- If you discover new ideas, send them to lead.
- Findings go to `.work/intel/<topic>/` — never floating files at the intel root.
- Follow file routing: `BUG-*.md` → `intel/bugs/`, `DESIGN-*.md` → `intel/design/`, audits → `intel/audits/`.
- Describe observed behavior, not judgments. "Returns empty list when input is None" — not "broken."
- If you discover something outside your task scope, send it to lead — don't chase it.
- **Context protection:** Web fetches can return massive pages — always use a prompt to extract what you need, never dump raw HTML. Grep with `head_limit`, not unbounded. Read targeted file sections, not entire codebases.

{{SELF_SERVICE_CHORE_BLOCK}}
