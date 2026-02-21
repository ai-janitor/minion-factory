# Review Capability

1. Read the code as-is. Do not suggest rewrites or style preferences. Review for correctness — does it do what it claims to do?
2. Check that the code matches its comments and docstrings. If the WHY layer says one thing and the code does another, flag it.
3. For each issue found, state the file, line, what's wrong, and why it matters. No vague "consider refactoring" — be specific.
4. File each finding as a task via `minion create-task` with clear reproduction or evidence. Do not fix anything during review.
5. Approve explicitly when code is correct. Silence is not approval.
6. When you see the same concept scattered across multiple files — duplicated logic, repeated patterns, similar structures that aren't sharing code — document it immediately. That is a pattern waiting to be conceptualized into its own module. Write up what the shared concept is, where it appears, and file a task to centralize it.
7. Focus on edge cases the happy path doesn't cover. What happens with empty input, None, zero, max values, missing keys, concurrent access? The happy path already works — your job is to find what breaks.
8. Write every discovered edge case to the `.work/` filesystem in the logical location (e.g., `.work/traps/correctness/`, `.work/traps/silent-fail/`). The filesystem is the database — if it's not written down, it doesn't exist.
