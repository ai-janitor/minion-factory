"""Shared error classifier for CLI provider output.

Purpose: Classify HTTP/API errors from provider verbose output into categories.
Rationale: SU-14 code deduplication — extracted from BaseProvider so that
           error classification is reusable outside the provider class hierarchy.
           F-051: classify_provider_error() consolidates the shared 3-phase pattern
           (JSON parse -> regex fallback -> generic summary) used by Gemini, Codex,
           and any future provider _classify_error() overrides.
Responsibility: classify_error() — maps status codes and patterns to categories.
                extract_error_summary() — reduces long output lines to short summaries.
                classify_provider_error() — 3-phase error classification for provider output.
Organization: Three public functions. No class dependencies.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)


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
    except json.JSONDecodeError:
        # Non-JSON lines are the normal case in provider output (log lines, stack
        # traces, plain text) — DEBUG only, not an error.
        logger.debug("extract_error_summary: line is not JSON, trying regex fallback")
    except (TypeError, AttributeError) as e:
        # These indicate a bug in the extractor logic, not normal input.
        logger.error("JSON error extraction failed: %s", e)

    # Try HTTP status code pattern
    m = re.search(r'\b([45]\d{2})\b', line[:200])
    if m:
        return f"HTTP {m.group(1)} (response truncated, {len(line)} chars)"

    return f"Large output ({len(line)} chars)"


# ---------------------------------------------------------------------------
# F-051: Shared 3-phase provider error classification
# ---------------------------------------------------------------------------


@dataclass
class ProviderErrorConfig:
    """Declarative configuration for provider-specific error classification.

    Purpose: Encapsulate the provider-specific parts of error classification so
    that the 3-phase pattern (JSON -> regex -> fallback) is written once.

    Attributes:
        prefix: Short label prepended to summaries (e.g. "CODEX_ERROR", "GEMINI").
        json_extractor: Optional callable that takes a parsed JSON dict and returns
            a short summary string, or None if the dict doesn't match.
        regex_patterns: List of (compiled_pattern, format_fn) pairs. Each
            format_fn receives the re.Match and returns a summary string.
    """

    prefix: str = "ERROR"
    json_extractor: Optional[Callable[[dict], Optional[str]]] = None
    regex_patterns: List[Tuple[re.Pattern, Callable[[re.Match], str]]] = field(
        default_factory=list
    )


def classify_provider_error(
    line: str,
    config: ProviderErrorConfig,
    max_normal: int = 500,
) -> Optional[str]:
    """3-phase provider error classification — shared structural pattern.

    Pseudo-logic:
      1. If line <= max_normal chars, return None (not worth classifying)
      2. Phase 1 — JSON: try to parse line as JSON, pass dict to config.json_extractor
      3. Phase 2 — Regex: try each regex_pattern in order, return first match
      4. Phase 3 — Fallback: delegate to extract_error_summary() for generic handling

    This replaces the duplicated _classify_error() overrides in GeminiProvider
    and CodexProvider (and any future providers) with a single call + config.

    Args:
        line: Raw output line (already stripped of trailing newline).
        config: Provider-specific extraction rules.
        max_normal: Lines shorter than this are not classified.

    Returns: Short summary string, or None if line is short enough.
    """
    if len(line) <= max_normal:
        return None

    # Phase 1: JSON extraction
    if config.json_extractor is not None:
        try:
            data = json.loads(line)
            if isinstance(data, dict):
                result = config.json_extractor(data)
                if result is not None:
                    return result
        except json.JSONDecodeError:
            # Non-JSON lines are the normal case in provider output — DEBUG only.
            logger.debug("classify_provider_error: line is not JSON, skipping JSON phase")
        except (TypeError, AttributeError) as e:
            # These indicate a bug in the extractor logic, not normal input.
            logger.error("Provider error JSON extraction failed: %s", e)

    # Phase 2: Regex pattern matching
    for pattern, format_fn in config.regex_patterns:
        m = pattern.search(line)
        if m:
            return format_fn(m)

    # Phase 3: Generic fallback
    return extract_error_summary(line, max_normal)
