"""Tests for intel add_doc, find_docs, read_doc, link_doc — CRUD operations.

Purpose: Verify intel doc lifecycle: add creates files and DB rows, find searches
         by tag and path fragment, read returns content, link connects docs to tasks.
Rationale: These four operations are the core intel pipeline. If any break, agents
           lose the ability to share knowledge across sessions.
Responsibility: Test add_doc, find_docs, read_doc, link_doc. NOT responsible for
                list_docs, war_plan, or reindex (covered in test_intel_behavioral).
Organization: One section per function, using shared isolated_db fixture.
"""

from __future__ import annotations

import os

import pytest

from minion.db import init_db, reset_db_path

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# DB + filesystem isolation fixture
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Each test gets its own .work/ tree and isolated SQLite DB."""
    work_dir = tmp_path / ".work"
    work_dir.mkdir(parents=True, exist_ok=True)
    intel_dir = work_dir / "intel"
    intel_dir.mkdir(parents=True, exist_ok=True)

    db_path = str(work_dir / "minion.db")
    monkeypatch.setenv("MINION_DB_PATH", db_path)
    reset_db_path()
    init_db()

    monkeypatch.chdir(tmp_path)
    yield tmp_path

    reset_db_path()


# ---------------------------------------------------------------------------
# add_doc — creates DB row and optionally scaffolds file
# ---------------------------------------------------------------------------


def test_add_doc_scaffold_creates_file_and_db_row(tmp_path):
    """add_doc with scaffold=True creates the file if it doesn't exist."""
    from minion.intel.add_doc import add_doc

    doc_path = str(tmp_path / ".work" / "intel" / "test-doc.md")
    result = add_doc(
        slug="test-doc",
        doc_path=doc_path,
        tags=["python", "testing"],
        description="A test document",
        created_by="test-agent",
        scaffold=True,
    )

    assert result["status"] == "added"
    assert result["slug"] == "test-doc"
    assert os.path.exists(doc_path)


def test_add_doc_without_scaffold_requires_existing_file(tmp_path):
    """add_doc without scaffold=True returns error if file doesn't exist."""
    from minion.intel.add_doc import add_doc

    doc_path = str(tmp_path / ".work" / "intel" / "nonexistent.md")
    result = add_doc(slug="missing", doc_path=doc_path, scaffold=False)

    assert "error" in result


def test_add_doc_update_existing(tmp_path):
    """add_doc on existing slug updates the row."""
    from minion.intel.add_doc import add_doc

    doc_path = str(tmp_path / ".work" / "intel" / "update-doc.md")
    add_doc(slug="update-doc", doc_path=doc_path, tags=["v1"], scaffold=True)
    result = add_doc(slug="update-doc", doc_path=doc_path, tags=["v2"], scaffold=True)

    assert result["status"] == "updated"


# ---------------------------------------------------------------------------
# find_docs — search by tag and/or path fragment
# ---------------------------------------------------------------------------


def test_find_docs_by_tag(tmp_path):
    """find_docs returns docs matching the given tag."""
    from minion.intel.add_doc import add_doc
    from minion.intel.find_docs import find_docs

    doc_path = str(tmp_path / ".work" / "intel" / "tagged.md")
    add_doc(slug="tagged-doc", doc_path=doc_path, tags=["gpu"], scaffold=True)

    result = find_docs(tag="gpu")
    assert len(result["docs"]) == 1
    assert result["docs"][0]["slug"] == "tagged-doc"


def test_find_docs_by_path_fragment(tmp_path):
    """find_docs returns docs matching the given path fragment."""
    from minion.intel.add_doc import add_doc
    from minion.intel.find_docs import find_docs

    doc_path = str(tmp_path / ".work" / "intel" / "arch" / "dep-graph.md")
    os.makedirs(os.path.dirname(doc_path), exist_ok=True)
    add_doc(slug="dep-graph", doc_path=doc_path, scaffold=True)

    result = find_docs(path_fragment="arch")
    assert len(result["docs"]) >= 1
    slugs = [d["slug"] for d in result["docs"]]
    assert "dep-graph" in slugs


def test_find_docs_no_results(tmp_path):
    """find_docs returns empty list when no docs match."""
    from minion.intel.find_docs import find_docs

    result = find_docs(tag="nonexistent-tag-xyz")
    assert result["docs"] == []


# ---------------------------------------------------------------------------
# read_doc — read content of registered doc
# ---------------------------------------------------------------------------


def test_read_doc_returns_content(tmp_path):
    """read_doc returns the file content for a registered doc."""
    from minion.intel.add_doc import add_doc
    from minion.intel.read_doc import read_doc

    doc_path = str(tmp_path / ".work" / "intel" / "readable.md")
    add_doc(slug="readable", doc_path=doc_path, scaffold=True)

    # Write some content after scaffolding
    with open(doc_path, "w") as f:
        f.write("# Test Content\nThis is test data.")

    result = read_doc(slug="readable")
    assert "content" in result
    assert "Test Content" in result["content"]


def test_read_doc_summary_truncates(tmp_path):
    """read_doc with summary=True returns only the first 10 lines."""
    from minion.intel.add_doc import add_doc
    from minion.intel.read_doc import read_doc

    doc_path = str(tmp_path / ".work" / "intel" / "long-doc.md")
    add_doc(slug="long-doc", doc_path=doc_path, scaffold=True)

    lines = [f"Line {i}" for i in range(20)]
    with open(doc_path, "w") as f:
        f.write("\n".join(lines))

    result = read_doc(slug="long-doc", summary=True)
    assert "content" in result
    content_lines = result["content"].splitlines()
    assert len(content_lines) <= 10


def test_read_doc_unregistered_slug():
    """read_doc returns error for an unregistered slug."""
    from minion.intel.read_doc import read_doc

    result = read_doc(slug="nonexistent-slug-xyz")
    assert "error" in result


# ---------------------------------------------------------------------------
# link_doc — connect docs to tasks/requirements
# ---------------------------------------------------------------------------


def test_link_doc_to_task(tmp_path):
    """link_doc creates a link between a doc and a task."""
    from minion.intel.add_doc import add_doc
    from minion.intel.link_doc import link_doc

    doc_path = str(tmp_path / ".work" / "intel" / "linkable.md")
    add_doc(slug="linkable", doc_path=doc_path, scaffold=True)

    result = link_doc(slug="linkable", task_id=42)
    assert result["status"] == "linked"
    assert result["entity_type"] == "task"
    assert result["entity_id"] == 42


def test_link_doc_duplicate_returns_already_linked(tmp_path):
    """link_doc on an existing link returns already_linked, not an error."""
    from minion.intel.add_doc import add_doc
    from minion.intel.link_doc import link_doc

    doc_path = str(tmp_path / ".work" / "intel" / "dup-link.md")
    add_doc(slug="dup-link", doc_path=doc_path, scaffold=True)

    link_doc(slug="dup-link", task_id=99)
    result = link_doc(slug="dup-link", task_id=99)
    assert result["status"] == "already_linked"


def test_link_doc_requires_exactly_one_target():
    """link_doc returns error when neither task nor req is provided."""
    from minion.intel.link_doc import link_doc

    result = link_doc(slug="any-slug")
    assert "error" in result


def test_link_doc_rejects_both_targets():
    """link_doc returns error when both task and req are provided."""
    from minion.intel.link_doc import link_doc

    result = link_doc(slug="any-slug", task_id=1, req_id=2)
    assert "error" in result


def test_link_doc_unregistered_slug():
    """link_doc returns error for a slug that isn't registered."""
    from minion.intel.link_doc import link_doc

    result = link_doc(slug="ghost-slug", task_id=1)
    assert "error" in result
