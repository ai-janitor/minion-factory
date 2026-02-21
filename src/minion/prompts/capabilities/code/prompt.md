# Code Capability — First Pass Rules

When writing new code:

1. DO NOT add try/except, try/catch, or any exception handling. Let errors propagate and fail loud. Silent failures are harder to debug than stack traces.
2. Exception handling is added ONLY during the test phase, after the code path is proven correct.
3. Write the happy path first. If it blows up, the stack trace tells you exactly where.
4. No defensive coding on first pass — no `if x is not None` guards, no fallback defaults for things that should exist. If a value is missing, you want to know immediately.
