# Review Capability

1. Read the code as-is. Do not suggest rewrites or style preferences. Review for correctness — does it do what it claims to do?
2. Check that the code matches its comments and docstrings. If the WHY layer says one thing and the code does another, flag it.
3. For each issue found, state the file, line, what's wrong, and why it matters. No vague "consider refactoring" — be specific.
4. File each finding as a task via `minion create-task` with clear reproduction or evidence. Do not fix anything during review.
5. Approve explicitly when code is correct. Silence is not approval.
