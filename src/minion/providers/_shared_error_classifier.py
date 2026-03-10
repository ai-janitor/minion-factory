"""Shared error classifier for CLI provider output.

Purpose: Classify HTTP/API errors from provider verbose output into categories.
Rationale: SU-14 code deduplication — extracted from BaseProvider so that
           error classification is reusable outside the provider class hierarchy.
Responsibility: classify_error() — maps status codes and patterns to categories.
                extract_error_summary() — reduces long output lines to short summaries.
Organization: Two public functions. No class dependencies.
"""

from __future__ import annotations

import json
import re
from typing import Optional


def classify_error(status_code: int) -> str:
    """Classify an HTTP status code into an error category.

    Pseudo-logic:
      - 429 -> "rate_limit"
      - 401, 403 -> "auth"
      - 500, 502, 503, 504 -> "transient"
      - everything else -> "permanent"

    Returns: One of "transient", "permanent", "auth", "rate_limit".
    """
    if status_code == 429:
        return "rate_limit"
    if status_code in (401, 403):
        return "auth"
    if status_code in (500, 502, 503, 504):
        return "transient"
    return "permanent"


def extract_error_summary(line: str, max_normal: int = 500) -> Optional[str]:
    """If line exceeds max_normal chars, try to extract a short error summary.

    Pseudo-logic:
      1. If line <= max_normal chars, return None (not an error worth summarizing)
      2. Try JSON parse: extract error.code, error.message, or top-level code/message
      3. Try regex for HTTP status codes (4xx, 5xx) in first 200 chars
      4. Fallback: "Large output (N chars)"

    Returns: Short summary string, or None if line is short enough.
    """
    if len(line) <= max_normal:
        return None

    # Try JSON error extraction
    try:
        data = json.loads(line)
        if isinstance(data, dict):
            code = data.get("error", {}).get("code") or data.get("code") or data.get("status")
            msg = data.get("error", {}).get("message") or data.get("message") or ""
            if code or msg:
                return f"{code or 'ERROR'}: {str(msg)[:120]}"
    except (json.JSONDecodeError, TypeError, AttributeError):
        pass

    # Try HTTP status code pattern
    m = re.search(r'\b([45]\d{2})\b', line[:200])
    if m:
        return f"HTTP {m.group(1)} (response truncated, {len(line)} chars)"

    return f"Large output ({len(line)} chars)"
