# Code Capability — First Pass Rules

When writing new code:

1. DO NOT add try/except, try/catch, or any exception handling. Let errors propagate and fail loud. The agent handles exceptions — code does not.
2. Write the happy path first. If it blows up, the stack trace tells you exactly where.
3. No defensive coding — no `if x is not None` guards, no fallback defaults for things that should exist. If a value is missing, you want to know immediately.

## File Organization

4. Do not cram everything into one file. One file, one concern. If a module has more than one public function, it should be a package with separate files.
5. Root-level files are routers — they import and dispatch, not implement. Logic lives in modules.
6. Every file starts with a comment header: purpose and rationale. What this file does and why it exists as a separate file.
7. Before writing any code, create the folder structure first. The directory tree is the database schema — it defines how the code is organized, queried, and navigated. Layout is the first deliverable, code is second.
8. Folder names are 3-5 words, descriptive. `ls` on any directory should tell you what the system does without opening a single file.
