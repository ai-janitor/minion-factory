"""Bulk-register project docs into the intel index — scan a directory and auto-derive slugs and tags.

Purpose: Bulk-register project docs into the intel index — scan a directory and auto-derive slugs and tags.
Rationale: Extracted into own module for single-responsibility intel management.
Responsibility: Bulk-register project docs into the intel index — scan a directory and auto-derive slugs and tags. NOT responsible for unrelated concerns.
Organization: Standalone functions and/or a single class. See source."""

from __future__ import annotations

import os
import re

from .add_doc import add_doc


# Words to strip from tags (too common to be useful)
_STOP_WORDS = {"the", "and", "for", "with", "from", "into", "this", "that", "are", "was", "will", "how"}


def _extract_tags_from_headings(filepath: str) -> list[str]:
    """Extract tags from H1 and H2 markdown headings."""
    tags: list[str] = []
    try:
        with open(filepath, encoding="utf-8") as f:
            for line in f:
                m = re.match(r"^#{1,2}\s+(.+)", line)
                if m:
                    heading = m.group(1).strip()
                    # Split heading into words, lowercase, filter noise
                    words = [
                        w.lower().strip("—-:()[]")
                        for w in re.split(r"[\s/,]+", heading)
                        if len(w) > 2
                    ]
                    tags.extend(w for w in words if w not in _STOP_WORDS)
    except Exception:
        pass
    # Deduplicate preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for t in tags:
        if t not in seen:
            seen.add(t)
            unique.append(t)
    return unique[:15]  # Cap at 15 tags


def register_docs(
    scan_dir: str = "docs",
    created_by: str = "register-docs",
) -> dict[str, object]:
    """Walk scan_dir, register every .md file in the intel index.

    Slug is derived from relative path (e.g., docs/comms.md → docs/comms).
    Tags are extracted from H1/H2 headings. Idempotent — updates existing entries.
    Also registers top-level project docs (AGENTS.md, CLAUDE.md, README.md, REQUIREMENTS.md).
    """
    if not os.path.isabs(scan_dir):
        scan_dir = os.path.join(os.getcwd(), scan_dir)

    results: list[dict[str, object]] = []

    # Scan the docs directory
    if os.path.isdir(scan_dir):
        for root, _dirs, files in os.walk(scan_dir):
            for fname in sorted(files):
                if not fname.endswith(".md"):
                    continue
                abs_path = os.path.join(root, fname)
                rel_path = os.path.relpath(abs_path, os.getcwd())
                slug = rel_path.replace(".md", "").replace(os.sep, "/")
                tags = _extract_tags_from_headings(abs_path)
                # First line after any frontmatter as description
                desc = _first_heading(abs_path)
                r = add_doc(
                    slug=slug,
                    doc_path=abs_path,
                    tags=tags,
                    description=desc,
                    created_by=created_by,
                )
                results.append({"slug": slug, "path": rel_path, "tags": tags, **r})

    # Also register top-level project docs
    project_root = os.getcwd()
    for top_doc in ("AGENTS.md", "CLAUDE.md", "README.md", "REQUIREMENTS.md", "REQUIREMENTS-IDEAS.md"):
        abs_path = os.path.join(project_root, top_doc)
        if os.path.exists(abs_path):
            slug = top_doc.replace(".md", "").lower()
            tags = _extract_tags_from_headings(abs_path)
            desc = _first_heading(abs_path)
            r = add_doc(
                slug=slug,
                doc_path=abs_path,
                tags=tags,
                description=desc,
                created_by=created_by,
            )
            results.append({"slug": slug, "path": top_doc, "tags": tags, **r})

    return {"registered": len(results), "docs": results}


def _first_heading(filepath: str) -> str:
    """Extract the first markdown heading as description."""
    try:
        with open(filepath, encoding="utf-8") as f:
            for line in f:
                m = re.match(r"^#\s+(.+)", line)
                if m:
                    return m.group(1).strip()
    except Exception:
        pass
    return ""
