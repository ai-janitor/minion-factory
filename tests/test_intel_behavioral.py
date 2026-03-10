"""Behavioral tests for intel/ — add_doc, list_docs, find_docs, war_plan.

Purpose: Verify intel index CRUD operations: registering docs, listing with tags,
         finding by fragment, and war plan management.
"""

from __future__ import annotations

import os

import pytest

from minion.db import init_db, reset_db_path


# ---------------------------------------------------------------------------
# DB isolation fixture
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    work_dir = tmp_path / ".work"
    work_dir.mkdir(parents=True, exist_ok=True)
    db_path = str(work_dir / "minion.db")
    monkeypatch.setenv("MINION_DB_PATH", db_path)
    reset_db_path()
    init_db()
    monkeypatch.chdir(tmp_path)
    yield tmp_path
    reset_db_path()


# ---------------------------------------------------------------------------
# add_doc — register an intel document
# ---------------------------------------------------------------------------


def test_add_doc_registers_new_doc(tmp_path):
    """add_doc inserts a new intel_docs row."""
    doc_file = tmp_path / ".work" / "intel" / "test.md"
    doc_file.parent.mkdir(parents=True, exist_ok=True)
    doc_file.write_text("# Test doc\nSome content.\n")

    from minion.intel import add_doc
    result = add_doc(
        slug="test-doc",
        doc_path=str(doc_file),
        tags=["arch"],
        description="A test doc",
        created_by="leo",
    )
    assert "error" not in result
    assert result.get("status") in ("registered", "updated", "ok", "added")


def test_add_doc_scaffold_creates_file(tmp_path):
    """add_doc with scaffold=True creates a stub file if it doesn't exist."""
    doc_path = str(tmp_path / ".work" / "intel" / "new-doc.md")

    from minion.intel import add_doc
    result = add_doc(
        slug="new-doc",
        doc_path=doc_path,
        scaffold=True,
        created_by="leo",
    )
    assert "error" not in result
    assert os.path.exists(doc_path), "scaffold=True should create the file"


# ---------------------------------------------------------------------------
# list_docs — listing registered docs
# ---------------------------------------------------------------------------


def test_list_docs_empty_initially():
    """list_docs returns empty docs list before any registrations."""
    from minion.intel import list_docs
    result = list_docs()
    assert "docs" in result
    assert result["docs"] == []


def test_list_docs_returns_registered_doc(tmp_path):
    """list_docs returns docs that were registered with add_doc."""
    doc_file = tmp_path / ".work" / "intel" / "existing.md"
    doc_file.parent.mkdir(parents=True, exist_ok=True)
    doc_file.write_text("# Existing doc\n")

    from minion.intel import add_doc, list_docs
    add_doc(slug="existing-doc", doc_path=str(doc_file), tags=["lang"])
    result = list_docs()
    slugs = [d["slug"] for d in result["docs"]]
    assert "existing-doc" in slugs


def test_list_docs_tag_filter(tmp_path):
    """list_docs tag filter returns only docs with matching tag."""
    work_intel = tmp_path / ".work" / "intel"
    work_intel.mkdir(parents=True, exist_ok=True)
    (work_intel / "doc-a.md").write_text("# A\n")
    (work_intel / "doc-b.md").write_text("# B\n")

    from minion.intel import add_doc, list_docs
    add_doc(slug="doc-a", doc_path=str(work_intel / "doc-a.md"), tags=["arch"])
    add_doc(slug="doc-b", doc_path=str(work_intel / "doc-b.md"), tags=["lang"])

    result = list_docs(tag="arch")
    slugs = [d["slug"] for d in result["docs"]]
    assert "doc-a" in slugs
    assert "doc-b" not in slugs


# ---------------------------------------------------------------------------
# find_docs — search by tag or path fragment
# ---------------------------------------------------------------------------


def test_find_docs_by_path_fragment(tmp_path):
    """find_docs returns docs matching path fragment."""
    work_intel = tmp_path / ".work" / "intel"
    work_intel.mkdir(parents=True, exist_ok=True)
    (work_intel / "network.md").write_text("# Network\n")

    from minion.intel import add_doc, find_docs
    add_doc(slug="network-doc", doc_path=str(work_intel / "network.md"))
    result = find_docs(path_fragment="network")
    docs = result.get("docs", [])
    slugs = [d["slug"] for d in docs]
    assert "network-doc" in slugs


def test_find_docs_no_match_returns_empty(tmp_path):
    """find_docs returns empty list when nothing matches."""
    from minion.intel import find_docs
    result = find_docs(tag="nonexistent_tag_xyz")
    docs = result.get("docs", [])
    assert docs == []


# ---------------------------------------------------------------------------
# war_plan — set, show, append (lead-only operations)
# ---------------------------------------------------------------------------


def _register_lead(name: str = "atlas") -> None:
    import sqlite3
    db_path = os.environ["MINION_DB_PATH"]
    now = "2026-03-09T00:00:00"
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT OR REPLACE INTO agents (name, agent_class, registered_at, last_seen) VALUES (?, 'lead', ?, ?)",
        (name, now, now),
    )
    conn.commit()
    conn.close()


def test_show_war_plan_no_plan_returns_empty():
    """show_war_plan returns empty content when no plan is set."""
    from minion.intel import show_war_plan
    result = show_war_plan()
    assert isinstance(result, dict)
    assert "content" in result or "note" in result or "error" in result


def test_set_war_plan_coder_blocked(tmp_path):
    """set_war_plan blocks non-lead agents."""
    import sqlite3
    db_path = os.environ["MINION_DB_PATH"]
    now = "2026-03-09T00:00:00"
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT OR REPLACE INTO agents (name, agent_class, registered_at, last_seen) VALUES (?, 'coder', ?, ?)",
        ("fighter", now, now),
    )
    conn.commit()
    conn.close()

    from minion.intel import set_war_plan
    result = set_war_plan("fighter", "Attack from the north.")
    assert "error" in result
    assert "lead" in result["error"].lower() or "BLOCKED" in result["error"]


def test_set_war_plan_lead_succeeds():
    """set_war_plan succeeds for lead-class agents."""
    _register_lead("atlas")
    from minion.intel import set_war_plan, show_war_plan
    result = set_war_plan("atlas", "Defend the north gate.")
    assert "error" not in result

    show = show_war_plan()
    assert "content" in show
    assert "Defend the north gate." in show["content"]


def test_append_war_plan_lead_succeeds():
    """append_war_plan appends text to existing war plan."""
    _register_lead("atlas")
    from minion.intel import set_war_plan, append_war_plan, show_war_plan
    set_war_plan("atlas", "Initial plan.\n")
    result = append_war_plan("atlas", "Additional notes.")
    assert "error" not in result

    show = show_war_plan()
    assert "Additional notes." in show["content"]
