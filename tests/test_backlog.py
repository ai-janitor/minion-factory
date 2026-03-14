"""Tests for the backlog subsystem — unit, CRUD integration, promote, kill/defer, and CLI.

Purpose: Tests for the backlog subsystem — unit, CRUD integration, promote, kill/defer, and CLI.
Rationale: Test coverage for the corresponding module.
Responsibility: Tests for the backlog subsystem — unit, CRUD integration, promote, kill/defer, and CLI. NOT responsible for unrelated concerns.
Organization: One TestClass per concern, or standalone test functions."""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
from pathlib import Path

import pytest
from click.testing import CliRunner

from minion.cli import cli

pytestmark = [pytest.mark.integration, pytest.mark.db]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BACKLOG_MD_TEMPLATE = Path(__file__).parent.parent / "task-flows" / "templates" / "backlog.md"


def _parse_json(output: str) -> dict:
    """Extract the first valid JSON object from CLI output (ignores stderr warnings)."""
    decoder = json.JSONDecoder()
    stripped = output.lstrip()
    obj, _ = decoder.raw_decode(stripped)
    return obj


def _init_db(db_path: str) -> None:
    """Initialize a minimal schema with backlog + requirements tables."""
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS schema_version (
            version     INTEGER PRIMARY KEY,
            applied_at  TEXT NOT NULL,
            description TEXT
        );
        CREATE TABLE IF NOT EXISTS requirements (
            id          INTEGER PRIMARY KEY,
            file_path   TEXT UNIQUE NOT NULL,
            origin      TEXT NOT NULL,
            stage       TEXT NOT NULL DEFAULT 'seed',
            created_by  TEXT,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            parent_id   INTEGER,
            flow_type   TEXT NOT NULL DEFAULT 'requirement'
        );
        CREATE TABLE IF NOT EXISTS backlog (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path   TEXT UNIQUE NOT NULL,
            type        TEXT NOT NULL,
            title       TEXT NOT NULL,
            priority    TEXT DEFAULT 'unset',
            status      TEXT DEFAULT 'open',
            source      TEXT,
            promoted_to TEXT,
            created_by  TEXT,
            flow_hint   TEXT DEFAULT NULL,
            created_at  TEXT NOT NULL,
            updated_at  TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS agents (
            name            TEXT PRIMARY KEY,
            agent_class     TEXT NOT NULL DEFAULT 'coder',
            registered_at   TEXT,
            last_seen       TEXT,
            last_inbox_check TEXT,
            context_updated_at TEXT,
            hp              INTEGER DEFAULT 100,
            transport       TEXT DEFAULT 'terminal',
            context         TEXT DEFAULT '',
            status          TEXT DEFAULT 'idle',
            model           TEXT DEFAULT NULL,
            zone            TEXT DEFAULT NULL
        );
        INSERT OR IGNORE INTO agents (name, agent_class, registered_at) VALUES ('test-lead', 'lead', datetime('now'));
    """)
    conn.close()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def project_dir(tmp_path):
    """Temp project dir with .work/ tree and initialized DB."""
    work = tmp_path / ".work"
    work.mkdir()
    db_path = work / "minion.db"
    _init_db(str(db_path))
    return tmp_path


@pytest.fixture
def db_path(project_dir):
    return str(project_dir / ".work" / "minion.db")


@pytest.fixture
def backlog_root(project_dir):
    """The .work/backlog/ directory (created on demand)."""
    return project_dir / ".work" / "backlog"


@pytest.fixture
def runner():
    return CliRunner()


def _run(runner, project_dir, *args):
    """Invoke CLI with temp project dir for full DB isolation."""
    return runner.invoke(cli, ["-C", str(project_dir)] + list(args))


# ---------------------------------------------------------------------------
# Unit tests — pure logic, no DB/FS
# ---------------------------------------------------------------------------


class TestSlugify:
    def test_spaces_become_hyphens(self):
        from minion.backlog.path_resolution_and_slug import _slugify
        assert _slugify("hello world") == "hello-world"

    def test_lowercased(self):
        from minion.backlog.path_resolution_and_slug import _slugify
        assert _slugify("Hello World") == "hello-world"

    def test_special_chars_stripped(self):
        from minion.backlog.path_resolution_and_slug import _slugify
        assert _slugify("fix: auth@login!") == "fix-authlogin"

    def test_repeated_hyphens_collapsed(self):
        from minion.backlog.path_resolution_and_slug import _slugify
        assert _slugify("a--b---c") == "a-b-c"

    def test_leading_trailing_hyphens_stripped(self):
        from minion.backlog.path_resolution_and_slug import _slugify
        assert _slugify("--hello--") == "hello"

    def test_already_clean(self):
        from minion.backlog.path_resolution_and_slug import _slugify
        assert _slugify("my-slug-123") == "my-slug-123"

    def test_numbers_preserved(self):
        from minion.backlog.path_resolution_and_slug import _slugify
        assert _slugify("GPT-4 is fast") == "gpt-4-is-fast"

    def test_whitespace_variants_collapsed(self):
        from minion.backlog.path_resolution_and_slug import _slugify
        # tabs and multiple spaces both become single hyphen
        assert _slugify("a\t b") == "a-b"

    def test_long_title_slug_within_max_length(self):
        from minion.backlog.path_resolution_and_slug import _slugify
        # 60-char title — slug must be <= 50 chars
        title = "This is a very long title that exceeds fifty characters total"
        slug = _slugify(title)
        assert len(slug) <= 50

    def test_truncation_at_word_boundary(self):
        from minion.backlog.path_resolution_and_slug import _slugify
        # "word-" at position 50 would land mid-word; verify no trailing or mid-word hyphen cut
        title = "one two three four five six seven eight nine ten eleven twelve"
        slug = _slugify(title)
        assert len(slug) <= 50
        # A word-boundary cut means the slug must not end with a hyphen
        assert not slug.endswith("-")
        # And no mid-word fragment: the slug must be a prefix of the full slug up to a hyphen
        full_slug = "one-two-three-four-five-six-seven-eight-nine-ten-eleven-twelve"
        assert full_slug.startswith(slug)

    def test_custom_max_length(self):
        from minion.backlog.path_resolution_and_slug import _slugify
        slug = _slugify("alpha beta gamma delta epsilon zeta eta theta", max_length=20)
        assert len(slug) <= 20
        assert not slug.endswith("-")


class TestParseReadme:
    def test_parses_title(self, tmp_path):
        from minion.backlog.path_resolution_and_slug import _parse_readme
        readme = tmp_path / "README.md"
        readme.write_text("# My Bug\n\n**Type:** bug\n")
        result = _parse_readme(str(readme))
        assert result["title"] == "My Bug"

    def test_parses_type(self, tmp_path):
        from minion.backlog.path_resolution_and_slug import _parse_readme
        readme = tmp_path / "README.md"
        readme.write_text("# Title\n\n**Type:** idea\n")
        result = _parse_readme(str(readme))
        assert result["type"] == "idea"

    def test_parses_source(self, tmp_path):
        from minion.backlog.path_resolution_and_slug import _parse_readme
        readme = tmp_path / "README.md"
        readme.write_text("# Title\n\n**Source:** agent-scout\n")
        result = _parse_readme(str(readme))
        assert result["source"] == "agent-scout"

    def test_parses_date(self, tmp_path):
        from minion.backlog.path_resolution_and_slug import _parse_readme
        readme = tmp_path / "README.md"
        readme.write_text("# Title\n\n**Date:** 2026-02-22\n")
        result = _parse_readme(str(readme))
        assert result["date"] == "2026-02-22"

    def test_missing_fields_return_none(self, tmp_path):
        from minion.backlog.path_resolution_and_slug import _parse_readme
        readme = tmp_path / "README.md"
        readme.write_text("# Just a title\n")
        result = _parse_readme(str(readme))
        assert result["title"] == "Just a title"
        assert result["type"] is None
        assert result["source"] is None
        assert result["date"] is None

    def test_nonexistent_file_returns_nones(self, tmp_path):
        from minion.backlog.path_resolution_and_slug import _parse_readme
        result = _parse_readme(str(tmp_path / "nope.md"))
        assert all(v is None for v in result.values())

    def test_full_template_parses_title(self, tmp_path):
        """Template format wraps fields in list items (- **Type:** bug).
        _parse_readme uses re.match which anchors to line start, so Type/Source/Date
        are not extracted from template-generated READMEs — only title is captured.
        """
        from minion.backlog.path_resolution_and_slug import _parse_readme
        content = BACKLOG_MD_TEMPLATE.read_text().format(
            title="Auth Regression",
            type="bug",
            source="human",
            date="2026-02-22",
            description="Login breaks after OAuth.",
        )
        readme = tmp_path / "README.md"
        readme.write_text(content)
        result = _parse_readme(str(readme))
        assert result["title"] == "Auth Regression"
        assert result["type"] == "bug"
        assert result["source"] == "human"
        assert result["date"] == "2026-02-22"


# ---------------------------------------------------------------------------
# CRUD integration tests
# ---------------------------------------------------------------------------


class TestAddItem:
    def test_creates_folder_and_readme(self, db_path, backlog_root):
        from minion.backlog import add
        result = add("bug", "Login Crash", db=db_path)
        assert "error" not in result
        folder = backlog_root / "bugs" / "login-crash"
        assert folder.is_dir()
        assert (folder / "README.md").exists()

    def test_returns_expected_fields(self, db_path):
        from minion.backlog import add
        result = add("idea", "Dark Mode", db=db_path)
        assert result["type"] == "idea"
        assert result["title"] == "Dark Mode"
        assert result["status"] == "open"
        assert "id" in result
        assert result["file_path"] == "ideas/dark-mode"

    def test_all_options(self, db_path, backlog_root):
        from minion.backlog import add
        result = add(
            "request",
            "Export CSV",
            source="product-team",
            description="Users need CSV export from dashboard.",
            priority="high",
            db=db_path,
        )
        assert "error" not in result
        assert result["file_path"] == "requests/export-csv"
        # DB row should have correct priority
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM backlog WHERE file_path = 'requests/export-csv'").fetchone()
        conn.close()
        assert row["priority"] == "high"
        assert row["source"] == "product-team"

    def test_readme_content_contains_title(self, db_path, backlog_root):
        from minion.backlog import add
        add("smell", "Long Method", db=db_path)
        readme = backlog_root / "smells" / "long-method" / "README.md"
        content = readme.read_text()
        assert "Long Method" in content

    def test_invalid_type_returns_error(self, db_path):
        from minion.backlog import add
        result = add("nonsense", "Whatever", db=db_path)
        assert "error" in result
        assert "Invalid type" in result["error"]

    def test_invalid_priority_returns_error(self, db_path):
        from minion.backlog import add
        result = add("bug", "Crash", priority="urgent", db=db_path)
        assert "error" in result
        assert "Invalid priority" in result["error"]

    def test_duplicate_slug_returns_error(self, db_path):
        from minion.backlog import add
        add("bug", "Same Title", db=db_path)
        result = add("bug", "Same Title", db=db_path)
        assert "error" in result
        assert "already exists" in result["error"]


class TestListItems:
    def _seed(self, db_path):
        from minion.backlog import add
        add("bug", "Auth Bug", priority="high", db=db_path)
        add("idea", "Dark Mode", priority="low", db=db_path)
        add("request", "Export", priority="medium", db=db_path)

    def test_returns_all_open_by_default(self, db_path):
        from minion.backlog import list_items
        self._seed(db_path)
        items = list_items(db=db_path)
        assert len(items) == 3
        assert all(i["status"] == "open" for i in items)

    def test_filter_by_type(self, db_path):
        from minion.backlog import list_items
        self._seed(db_path)
        items = list_items(type="bug", db=db_path)
        assert len(items) == 1
        assert items[0]["type"] == "bug"

    def test_filter_by_priority(self, db_path):
        from minion.backlog import list_items
        self._seed(db_path)
        items = list_items(priority="high", db=db_path)
        assert len(items) == 1
        assert items[0]["priority"] == "high"

    def test_filter_by_status_none_returns_all(self, db_path):
        from minion.backlog import list_items, add
        self._seed(db_path)
        # Kill one so it's no longer open
        add("debt", "Legacy Code", db=db_path)
        items = list_items(status=None, db=db_path)
        assert len(items) >= 4

    def test_invalid_type_returns_error_entry(self, db_path):
        from minion.backlog import list_items
        result = list_items(type="bogus", db=db_path)
        assert len(result) == 1
        assert "error" in result[0]


class TestGetItem:
    def test_by_file_path(self, db_path):
        from minion.backlog import add, get_item
        result = add("bug", "Null Pointer", db=db_path)
        item = get_item(file_path=result["file_path"], db=db_path)
        assert item is not None
        assert item["title"] == "Null Pointer"

    def test_by_id(self, db_path):
        from minion.backlog import add, get_item
        result = add("idea", "AI Summary", db=db_path)
        item = get_item(item_id=result["id"], db=db_path)
        assert item is not None
        assert item["type"] == "idea"

    def test_missing_returns_none(self, db_path):
        from minion.backlog import get_item
        item = get_item(file_path="bugs/ghost", db=db_path)
        assert item is None

    def test_no_keys_returns_error(self, db_path):
        from minion.backlog import get_item
        result = get_item(db=db_path)
        assert "error" in result


class TestUpdateItem:
    def test_change_priority(self, db_path):
        from minion.backlog import add, update_item
        r = add("debt", "Old Lib", db=db_path)
        updated = update_item(r["file_path"], priority="critical", db=db_path)
        assert updated["priority"] == "critical"

    def test_invalid_priority_returns_error(self, db_path):
        from minion.backlog import add, update_item
        r = add("debt", "Old Lib 2", db=db_path)
        result = update_item(r["file_path"], priority="extreme", db=db_path)
        assert "error" in result

    def test_missing_item_returns_error(self, db_path):
        from minion.backlog import update_item
        result = update_item("bugs/ghost", priority="low", db=db_path)
        assert "error" in result

    def test_no_fields_returns_error(self, db_path):
        from minion.backlog import update_item
        result = update_item("bugs/anything", db=db_path)
        assert "error" in result

    def test_update_by_id(self, db_path):
        """update_item should accept item_id as an alternative to file_path."""
        from minion.backlog import add, update_item
        r = add("bug", "ID Lookup Bug", db=db_path)
        updated = update_item(item_id=r["id"], priority="high", db=db_path)
        assert updated["priority"] == "high"
        assert updated["file_path"] == r["file_path"]

    def test_update_deferred_item_by_id(self, db_path):
        """Deferred items must be updatable by ID — the original bug (#236)."""
        from minion.backlog import add, update_item
        import sqlite3
        r = add("bug", "Deferred Bug", db=db_path)
        # Manually set status to deferred (simulating 'backlog defer')
        conn = sqlite3.connect(db_path)
        conn.execute("UPDATE backlog SET status='deferred' WHERE id=?", (r["id"],))
        conn.commit()
        conn.close()
        updated = update_item(item_id=r["id"], priority="critical", db=db_path)
        assert "error" not in updated
        assert updated["priority"] == "critical"
        assert updated["status"] == "deferred"

    def test_update_deferred_item_by_path(self, db_path):
        """Deferred items must also be updatable by path."""
        from minion.backlog import add, update_item
        import sqlite3
        r = add("bug", "Deferred Path Bug", db=db_path)
        conn = sqlite3.connect(db_path)
        conn.execute("UPDATE backlog SET status='deferred' WHERE id=?", (r["id"],))
        conn.commit()
        conn.close()
        updated = update_item(r["file_path"], priority="low", db=db_path)
        assert "error" not in updated
        assert updated["priority"] == "low"
        assert updated["status"] == "deferred"

    def test_update_missing_id_returns_error(self, db_path):
        from minion.backlog import update_item
        result = update_item(item_id=99999, priority="low", db=db_path)
        assert "error" in result

    def test_no_identifier_returns_error(self, db_path):
        """Neither file_path nor item_id provided — should error."""
        from minion.backlog import update_item
        result = update_item(priority="low", db=db_path)
        assert "error" in result


class TestResolveDbPathCrossProjectGuard:
    """Tests for resolve_db_path() refusing to cross git repo boundaries (#237)."""

    def test_walk_up_within_same_repo_finds_db(self, tmp_path):
        """Walk-up from a subdirectory within the same git repo should find .work/minion.db."""
        from minion.defaults import resolve_db_path
        # Set up: project root with .git and .work/minion.db
        (tmp_path / ".git").mkdir()
        work = tmp_path / ".work"
        work.mkdir()
        db_file = work / "minion.db"
        db_file.write_text("")  # just needs to exist
        subdir = tmp_path / "src" / "minion" / "cli"
        subdir.mkdir(parents=True)
        # Monkey-patch cwd to the subdirectory
        original_cwd = os.getcwd()
        os.chdir(subdir)
        try:
            # Clear env vars that would short-circuit
            env_backup = {k: os.environ.pop(k) for k in ["MINION_DB_PATH", "MINION_PROJECT"] if k in os.environ}
            try:
                result = resolve_db_path()
                assert result == str(db_file)
            finally:
                os.environ.update(env_backup)
        finally:
            os.chdir(original_cwd)

    def test_walk_up_blocked_by_different_git_root(self, tmp_path):
        """Walk-up must NOT cross into a parent directory that has a different .git root."""
        from minion.defaults import resolve_db_path
        # Parent project: has .git and .work/minion.db
        parent_project = tmp_path / "parent-project"
        parent_project.mkdir()
        (parent_project / ".git").mkdir()
        parent_work = parent_project / ".work"
        parent_work.mkdir()
        (parent_work / "minion.db").write_text("")
        # Child project: nested inside parent, has its own .git but NO .work/
        child_project = parent_project / "child-project"
        child_project.mkdir()
        (child_project / ".git").mkdir()
        # cwd = child project — should NOT find parent's DB
        original_cwd = os.getcwd()
        os.chdir(child_project)
        try:
            env_backup = {k: os.environ.pop(k) for k in ["MINION_DB_PATH", "MINION_PROJECT"] if k in os.environ}
            try:
                result = resolve_db_path()
                # Should fall back to cwd/.work/minion.db, NOT parent's DB
                expected_fallback = os.path.join(str(child_project), ".work", "minion.db")
                assert result == expected_fallback
                assert str(parent_work) not in result
            finally:
                os.environ.update(env_backup)
        finally:
            os.chdir(original_cwd)

    def test_update_item_includes_project_field(self, db_path):
        """update_item output should include a 'project' field showing the resolved DB path."""
        from minion.backlog import add, update_item
        r = add("bug", "Project Field Bug", db=db_path)
        updated = update_item(r["file_path"], priority="high", db=db_path)
        assert "project" in updated
        # The project field should be the grandparent of the DB file
        assert updated["project"] == str(Path(db_path).parent.parent)


class TestReindex:
    def _make_item_folder(self, backlog_root, item_type_folder, slug, title, item_type):
        """Create a backlog item folder with a properly formatted README."""
        folder = backlog_root / item_type_folder / slug
        folder.mkdir(parents=True, exist_ok=True)
        content = f"# {title}\n\n**Type:** {item_type}\n**Source:** test\n**Date:** 2026-01-01\n"
        (folder / "README.md").write_text(content)
        return folder

    def test_discovers_items_from_filesystem(self, db_path, backlog_root):
        from minion.backlog import reindex, list_items
        self._make_item_folder(backlog_root, "bugs", "memory-leak", "Memory Leak", "bug")
        self._make_item_folder(backlog_root, "ideas", "dark-mode", "Dark Mode", "idea")
        result = reindex(db=db_path)
        assert result["registered"] == 2
        items = list_items(status=None, db=db_path)
        paths = [i["file_path"] for i in items]
        assert "bugs/memory-leak" in paths
        assert "ideas/dark-mode" in paths

    def test_idempotent_second_run_skips_all(self, db_path, backlog_root):
        from minion.backlog import reindex
        self._make_item_folder(backlog_root, "smells", "deep-nest", "Deep Nesting", "smell")
        first = reindex(db=db_path)
        assert first["registered"] == 1
        second = reindex(db=db_path)
        assert second["registered"] == 0
        assert second["skipped"] == 1

    def test_unknown_folder_skipped(self, db_path, backlog_root):
        from minion.backlog import reindex
        # Create a folder under an unknown type folder
        unknown = backlog_root / "random" / "something"
        unknown.mkdir(parents=True)
        (unknown / "README.md").write_text("# Whatever\n")
        result = reindex(db=db_path)
        assert result["registered"] == 0

    def test_missing_backlog_dir_returns_error(self, db_path):
        from minion.backlog import reindex
        result = reindex(db=db_path)
        # backlog_root doesn't exist yet — should return gracefully
        assert "error" in result or result["registered"] == 0

    def test_infers_type_from_folder(self, db_path, backlog_root):
        from minion.backlog import reindex, list_items
        self._make_item_folder(backlog_root, "requests", "api-v2", "API v2", "request")
        reindex(db=db_path)
        items = list_items(type="request", status=None, db=db_path)
        assert len(items) == 1
        assert items[0]["file_path"] == "requests/api-v2"


# ---------------------------------------------------------------------------
# Promote tests — via CLI (promote() uses get_db() globally, not the db param)
# ---------------------------------------------------------------------------


class TestPromote:
    """promote() calls get_db() directly (ignores db param for connection).
    All promote tests go through the CLI which sets MINION_DB_PATH correctly.
    """

    def test_creates_requirement_folder(self, runner, project_dir):
        res = _run(runner, project_dir, "backlog", "add", "--type", "bug", "--title", "Memory Leak Bug")
        assert res.exit_code == 0, res.output
        rel_path = _parse_json(res.output)["file_path"]

        res = _run(runner, project_dir, "backlog", "promote", "--agent", "test-lead", rel_path)
        assert res.exit_code == 0, res.output
        slug = rel_path.split("/")[-1]
        req_folder = project_dir / ".work" / "requirements" / "bugs" / slug
        assert req_folder.is_dir()

    def test_promoted_status_set(self, runner, project_dir):
        _run(runner, project_dir, "backlog", "add", "--type", "bug", "--title", "Login Race")
        rel_path = "bugs/login-race"

        res = _run(runner, project_dir, "backlog", "promote", "--agent", "test-lead", rel_path)
        assert res.exit_code == 0, res.output
        data = _parse_json(res.output)
        assert data["status"] == "promoted"
        assert data["backlog"]["promoted_to"] is not None

    def test_requirement_registered_in_db(self, runner, project_dir, db_path):
        _run(runner, project_dir, "backlog", "add", "--type", "bug", "--title", "DB Timeout")
        res = _run(runner, project_dir, "backlog", "promote", "--agent", "test-lead", "bugs/db-timeout")
        assert res.exit_code == 0, res.output
        data = _parse_json(res.output)
        req_path = data["requirement"]["file_path"]

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM requirements WHERE file_path = ?", (req_path,)).fetchone()
        conn.close()
        assert row is not None

    def test_readme_copied_to_requirement(self, runner, project_dir):
        _run(runner, project_dir, "backlog", "add", "--type", "bug", "--title", "Copy Bug")
        res = _run(runner, project_dir, "backlog", "promote", "--agent", "test-lead", "bugs/copy-bug")
        assert res.exit_code == 0, res.output
        req_readme = project_dir / ".work" / "requirements" / "bugs" / "copy-bug" / "README.md"
        assert req_readme.exists()

    def test_double_promote_exits_nonzero(self, runner, project_dir):
        _run(runner, project_dir, "backlog", "add", "--type", "bug", "--title", "Double Promote")
        _run(runner, project_dir, "backlog", "promote", "--agent", "test-lead", "bugs/double-promote")
        res = _run(runner, project_dir, "backlog", "promote", "--agent", "test-lead", "bugs/double-promote")
        assert res.exit_code == 1
        data = _parse_json(res.output)
        assert "already promoted" in data["error"]

    def test_promote_killed_item_exits_nonzero(self, runner, project_dir, db_path):
        _run(runner, project_dir, "backlog", "add", "--type", "bug", "--title", "Killed Bug")
        # Force status to killed in DB
        conn = sqlite3.connect(db_path)
        conn.execute("UPDATE backlog SET status='killed' WHERE file_path='bugs/killed-bug'")
        conn.commit()
        conn.close()
        res = _run(runner, project_dir, "backlog", "promote", "--agent", "test-lead", "bugs/killed-bug")
        assert res.exit_code == 1
        data = _parse_json(res.output)
        assert "killed" in data["error"]

    def test_idea_promotes_as_feature(self, runner, project_dir):
        _run(runner, project_dir, "backlog", "add", "--type", "idea", "--title", "New Dashboard")
        res = _run(runner, project_dir, "backlog", "promote", "--agent", "test-lead", "ideas/new-dashboard")
        assert res.exit_code == 0, res.output
        data = _parse_json(res.output)
        assert data["requirement"]["file_path"].startswith("features/")

    def test_slug_override_used_for_requirement_path(self, runner, project_dir):
        """--slug overrides the auto-derived requirement folder name."""
        _run(runner, project_dir, "backlog", "add", "--type", "bug", "--title", "Slug Override Bug")
        res = _run(
            runner, project_dir,
            "backlog", "promote", "--agent", "test-lead", "bugs/slug-override-bug",
            "--slug", "my-custom-slug",
        )
        assert res.exit_code == 0, res.output
        data = _parse_json(res.output)
        assert data["requirement"]["file_path"] == "bugs/my-custom-slug"
        req_folder = project_dir / ".work" / "requirements" / "bugs" / "my-custom-slug"
        assert req_folder.is_dir()


# ---------------------------------------------------------------------------
# Kill / Defer / Reopen tests
# ---------------------------------------------------------------------------


class TestKillDefer:
    """Tests for kill(), defer(), reopen() using tmp_path as the working dir.

    close_item functions use file_path for BOTH DB lookup AND filesystem
    operations (relative to cwd). We store the absolute path in the DB
    directly and create the folder at that path so both lookups succeed.
    """

    def _insert_open_item(self, db_path, abs_folder: str, title: str = "Test Item") -> None:
        """Insert a DB row using the absolute folder path and create the README."""
        from datetime import datetime
        now = datetime.now().isoformat()
        Path(abs_folder).mkdir(parents=True, exist_ok=True)
        readme = Path(abs_folder) / "README.md"
        readme.write_text(f"# {title}\n\n## Outcome\n\n<!-- filled on closure -->\n")
        conn = sqlite3.connect(db_path)
        conn.execute(
            "INSERT INTO backlog (file_path, type, title, priority, status, source, created_at, updated_at) "
            "VALUES (?, 'bug', ?, 'unset', 'open', 'test', ?, ?)",
            (abs_folder, title, now, now),
        )
        conn.commit()
        conn.close()

    def test_kill_sets_status_killed(self, db_path, backlog_root):
        from minion.backlog.close_item import kill
        folder = str(backlog_root / "bugs" / "test-kill")
        self._insert_open_item(db_path, folder, "Kill Me")
        result = kill(folder, reason="No longer relevant", db=db_path)
        assert result["status"] == "killed"

    def test_kill_writes_reason_to_readme(self, db_path, backlog_root):
        from minion.backlog.close_item import kill
        folder = str(backlog_root / "bugs" / "test-kill-readme")
        self._insert_open_item(db_path, folder, "Kill Readme")
        kill(folder, reason="Superseded by v2", db=db_path)
        content = (Path(folder) / "README.md").read_text()
        assert "Superseded by v2" in content
        assert "Killed" in content

    def test_defer_sets_status_deferred(self, db_path, backlog_root):
        from minion.backlog.close_item import defer
        folder = str(backlog_root / "bugs" / "test-defer")
        self._insert_open_item(db_path, folder, "Defer Me")
        result = defer(folder, until="Q3 2026", db=db_path)
        assert result["status"] == "deferred"

    def test_defer_writes_timing_to_readme(self, db_path, backlog_root):
        from minion.backlog.close_item import defer
        folder = str(backlog_root / "bugs" / "test-defer-readme")
        self._insert_open_item(db_path, folder, "Defer Readme")
        defer(folder, until="2026-06-01", db=db_path)
        content = (Path(folder) / "README.md").read_text()
        assert "2026-06-01" in content
        assert "Deferred" in content

    def test_reopen_killed_item(self, db_path, backlog_root):
        from minion.backlog.close_item import kill, reopen
        folder = str(backlog_root / "bugs" / "test-reopen-killed")
        self._insert_open_item(db_path, folder, "Reopen Killed")
        kill(folder, reason="Test kill", db=db_path)
        result = reopen(folder, db=db_path)
        assert result["status"] == "open"

    def test_reopen_deferred_item(self, db_path, backlog_root):
        from minion.backlog.close_item import defer, reopen
        folder = str(backlog_root / "bugs" / "test-reopen-deferred")
        self._insert_open_item(db_path, folder, "Reopen Deferred")
        defer(folder, until="Q4 2026", db=db_path)
        result = reopen(folder, db=db_path)
        assert result["status"] == "open"

    def test_kill_non_open_raises(self, db_path, backlog_root):
        from minion.backlog.close_item import kill, defer
        folder = str(backlog_root / "bugs" / "test-kill-non-open")
        self._insert_open_item(db_path, folder, "Already Deferred")
        defer(folder, until="later", db=db_path)
        with pytest.raises(ValueError, match="must be 'open'"):
            kill(folder, reason="Too late", db=db_path)

    def test_reopen_open_item_raises(self, db_path, backlog_root):
        from minion.backlog.close_item import reopen
        folder = str(backlog_root / "bugs" / "test-reopen-open")
        self._insert_open_item(db_path, folder, "Already Open")
        with pytest.raises(ValueError, match="killed.*deferred"):
            reopen(folder, db=db_path)


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------


class TestBacklogCLI:
    def test_add_returns_json_with_id(self, runner, project_dir):
        res = _run(runner, project_dir, "backlog", "add", "--type", "bug", "--title", "Test Bug")
        assert res.exit_code == 0, res.output
        data = _parse_json(res.output)
        assert "id" in data
        assert data["type"] == "bug"
        assert data["title"] == "Test Bug"

    def test_add_all_options(self, runner, project_dir):
        res = _run(
            runner, project_dir,
            "backlog", "add",
            "--type", "idea",
            "--title", "CLI Idea",
            "--source", "agent",
            "--description", "Some description",
            "--priority", "high",
        )
        assert res.exit_code == 0, res.output
        data = _parse_json(res.output)
        assert data["type"] == "idea"

    def test_add_invalid_type_rejected(self, runner, project_dir):
        res = _run(runner, project_dir, "backlog", "add", "--type", "invalid", "--title", "X")
        assert res.exit_code != 0  # click.Choice rejects at CLI level
        assert "invalid" in res.output

    def test_list_returns_json_array(self, runner, project_dir):
        _run(runner, project_dir, "backlog", "add", "--type", "bug", "--title", "Bug One")
        _run(runner, project_dir, "backlog", "add", "--type", "idea", "--title", "Idea One")
        res = _run(runner, project_dir, "backlog", "list")
        assert res.exit_code == 0, res.output
        data = _parse_json(res.output)
        # donnie's CLI returns raw list
        assert isinstance(data, list)
        assert len(data) >= 2

    def test_list_filter_by_type(self, runner, project_dir):
        _run(runner, project_dir, "backlog", "add", "--type", "bug", "--title", "Bug Filter")
        _run(runner, project_dir, "backlog", "add", "--type", "idea", "--title", "Idea Filter")
        res = _run(runner, project_dir, "backlog", "list", "--type", "bug")
        assert res.exit_code == 0, res.output
        data = _parse_json(res.output)
        assert isinstance(data, list)
        assert all(item["type"] == "bug" for item in data)

    def test_show_returns_item(self, runner, project_dir):
        res = _run(runner, project_dir, "backlog", "add", "--type", "smell", "--title", "Long Func")
        item_path = _parse_json(res.output)["file_path"]
        res = _run(runner, project_dir, "backlog", "show", item_path)
        assert res.exit_code == 0, res.output
        data = _parse_json(res.output)
        assert data["file_path"] == item_path

    def test_show_missing_exits_nonzero(self, runner, project_dir):
        res = _run(runner, project_dir, "backlog", "show", "bugs/ghost")
        assert res.exit_code == 1

    def test_update_priority(self, runner, project_dir):
        res = _run(runner, project_dir, "backlog", "add", "--type", "debt", "--title", "Old Code")
        item_path = _parse_json(res.output)["file_path"]
        res = _run(runner, project_dir, "backlog", "update", item_path, "--priority", "critical")
        assert res.exit_code == 0, res.output
        data = _parse_json(res.output)
        assert data["priority"] == "critical"

    def test_update_by_id(self, runner, project_dir):
        """CLI: backlog update --id <N> should find items regardless of status."""
        res = _run(runner, project_dir, "backlog", "add", "--type", "bug", "--title", "CLI ID Update")
        data = _parse_json(res.output)
        item_id = str(data["id"])
        res = _run(runner, project_dir, "backlog", "update", "--id", item_id, "--priority", "high")
        assert res.exit_code == 0, res.output
        updated = _parse_json(res.output)
        assert updated["priority"] == "high"

    def test_update_deferred_item_by_id_cli(self, runner, project_dir, db_path):
        """CLI: updating a deferred item by --id must succeed (bug #236)."""
        import sqlite3
        res = _run(runner, project_dir, "backlog", "add", "--type", "bug", "--title", "CLI Deferred Update")
        data = _parse_json(res.output)
        item_id = data["id"]
        # Force status to deferred in DB
        conn = sqlite3.connect(db_path)
        conn.execute("UPDATE backlog SET status='deferred' WHERE id=?", (item_id,))
        conn.commit()
        conn.close()
        res = _run(runner, project_dir, "backlog", "update", "--id", str(item_id), "--priority", "critical")
        assert res.exit_code == 0, res.output
        updated = _parse_json(res.output)
        assert updated["priority"] == "critical"
        assert updated["status"] == "deferred"

    def test_reindex_returns_registered_skipped(self, runner, project_dir):
        # Create items via add first so reindex sees them as already registered
        _run(runner, project_dir, "backlog", "add", "--type", "bug", "--title", "RI Bug")
        res = _run(runner, project_dir, "backlog", "reindex")
        assert res.exit_code == 0, res.output
        data = _parse_json(res.output)
        # Already registered by add — should be skipped
        assert "skipped" in data or "registered" in data

    def test_promote_end_to_end(self, runner, project_dir):
        res = _run(runner, project_dir, "backlog", "add", "--type", "bug", "--title", "CLI Promote Bug")
        assert res.exit_code == 0, res.output
        item_path = _parse_json(res.output)["file_path"]

        res = _run(runner, project_dir, "backlog", "promote", "--agent", "test-lead", item_path)
        assert res.exit_code == 0, res.output
        data = _parse_json(res.output)
        assert data["status"] == "promoted"
        assert "requirement" in data

        # Verify requirement folder created
        slug = item_path.split("/")[-1]
        req_folder = project_dir / ".work" / "requirements" / "bugs" / slug
        assert req_folder.is_dir()


# ---------------------------------------------------------------------------
# Multi-promote tests — --count N and --slugs
# ---------------------------------------------------------------------------


class TestMultiPromote:
    """Tests for multi-requirement promote with --count and --slugs flags."""

    def test_multi_promote_creates_n_requirements(self, runner, project_dir, db_path):
        """Promote with --count 3 and 3 slugs creates 3 requirement folders and DB rows."""
        _run(runner, project_dir, "backlog", "add", "--type", "idea", "--title", "Big Feature")
        res = _run(
            runner, project_dir,
            "backlog", "promote", "--agent", "test-lead", "ideas/big-feature",
            "--count", "3", "--slugs", "auth-api,auth-ui,auth-tests",
        )
        assert res.exit_code == 0, res.output
        data = _parse_json(res.output)
        assert data["status"] == "promoted"
        assert data["count"] == 3
        assert len(data["requirements"]) == 3

        # Verify all 3 requirement folders exist
        for slug in ("auth-api", "auth-ui", "auth-tests"):
            req_folder = project_dir / ".work" / "requirements" / "features" / slug
            assert req_folder.is_dir(), f"Missing folder for slug '{slug}'"

        # Verify all 3 requirements registered in DB
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        for slug in ("auth-api", "auth-ui", "auth-tests"):
            row = conn.execute(
                "SELECT * FROM requirements WHERE file_path = ?", (f"features/{slug}",)
            ).fetchone()
            assert row is not None, f"Missing DB row for features/{slug}"
        conn.close()

        # Verify promoted_to is comma-separated
        assert "features/auth-api" in data["backlog"]["promoted_to"]
        assert "features/auth-ui" in data["backlog"]["promoted_to"]
        assert "features/auth-tests" in data["backlog"]["promoted_to"]

    def test_multi_promote_slugs_count_mismatch_error(self, runner, project_dir):
        """--count 2 but 3 slugs -> error."""
        _run(runner, project_dir, "backlog", "add", "--type", "idea", "--title", "Mismatch")
        res = _run(
            runner, project_dir,
            "backlog", "promote", "--agent", "test-lead", "ideas/mismatch",
            "--count", "2", "--slugs", "a,b,c",
        )
        assert res.exit_code != 0
        data = _parse_json(res.output)
        assert "3 items" in data["error"] or "must match" in data["error"]

    def test_multi_promote_slugs_required_when_count_gt_1(self, runner, project_dir):
        """--count 2 but no --slugs -> error."""
        _run(runner, project_dir, "backlog", "add", "--type", "idea", "--title", "No Slugs")
        res = _run(
            runner, project_dir,
            "backlog", "promote", "--agent", "test-lead", "ideas/no-slugs",
            "--count", "2",
        )
        assert res.exit_code != 0
        data = _parse_json(res.output)
        assert "slugs" in data["error"].lower()

    def test_slugs_without_count_errors(self, runner, project_dir):
        """--slugs without --count > 1 is an error."""
        _run(runner, project_dir, "backlog", "add", "--type", "idea", "--title", "Bad Combo")
        res = _run(
            runner, project_dir,
            "backlog", "promote", "--agent", "test-lead", "ideas/bad-combo",
            "--slugs", "a,b",
        )
        assert res.exit_code != 0
        data = _parse_json(res.output)
        assert "count" in data["error"].lower()

    def test_re_promote_allowed_for_multi(self, runner, project_dir, db_path):
        """First promote (count=1), then re-promote (count=2) on same item succeeds."""
        _run(runner, project_dir, "backlog", "add", "--type", "idea", "--title", "Expandable")
        # First promote: single
        res = _run(
            runner, project_dir,
            "backlog", "promote", "--agent", "test-lead", "ideas/expandable",
        )
        assert res.exit_code == 0, res.output

        # Second promote: multi — should succeed (re-promote)
        res = _run(
            runner, project_dir,
            "backlog", "promote", "--agent", "test-lead", "ideas/expandable",
            "--count", "2", "--slugs", "expand-part-a,expand-part-b",
        )
        assert res.exit_code == 0, res.output
        data = _parse_json(res.output)
        assert data["status"] == "promoted"
        assert data["count"] == 2

        # Verify promoted_to now has all 3 paths (original + 2 new)
        promoted_to = data["backlog"]["promoted_to"]
        paths = [p.strip() for p in promoted_to.split(",")]
        assert len(paths) == 3
        assert "features/expandable" in paths
        assert "features/expand-part-a" in paths
        assert "features/expand-part-b" in paths

    def test_double_promote_single_still_blocked(self, runner, project_dir):
        """Single promote on already-promoted item (no --count) still blocked."""
        _run(runner, project_dir, "backlog", "add", "--type", "bug", "--title", "Double Block")
        _run(runner, project_dir, "backlog", "promote", "--agent", "test-lead", "bugs/double-block")
        res = _run(runner, project_dir, "backlog", "promote", "--agent", "test-lead", "bugs/double-block")
        assert res.exit_code == 1
        data = _parse_json(res.output)
        assert "already promoted" in data["error"]

    def test_close_guard_multi_requirement(self, runner, project_dir, db_path):
        """Close guard checks ALL linked requirements when promoted_to is comma-separated."""
        # Create and multi-promote
        _run(runner, project_dir, "backlog", "add", "--type", "idea", "--title", "Guard Test")
        res = _run(
            runner, project_dir,
            "backlog", "promote", "--agent", "test-lead", "ideas/guard-test",
            "--count", "2", "--slugs", "guard-a,guard-b",
        )
        assert res.exit_code == 0, res.output

        # Add tasks table (needed for close guard check) — must match real schema
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                task_file TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'open',
                created_by TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                requirement_id INTEGER
            )
        """)

        # Find the requirement IDs
        row_a = conn.execute("SELECT id FROM requirements WHERE file_path = 'features/guard-a'").fetchone()
        row_b = conn.execute("SELECT id FROM requirements WHERE file_path = 'features/guard-b'").fetchone()
        assert row_a and row_b

        # Create an open task on requirement A
        conn.execute(
            "INSERT INTO tasks (title, task_file, status, created_by, created_at, updated_at, requirement_id) "
            "VALUES (?, 'dummy.md', 'open', 'test', datetime('now'), datetime('now'), ?)",
            ("Task on A", row_a[0]),
        )
        conn.commit()
        conn.close()

        # Try to close — should be blocked because of open task on req A
        res = _run(
            runner, project_dir,
            "backlog", "update", "ideas/guard-test", "--status", "closed",
        )
        assert res.exit_code == 0  # CLI succeeds but returns error in JSON
        data = _parse_json(res.output)
        assert "error" in data
        assert "Cannot close" in data["error"]

        # Close the task on A
        conn = sqlite3.connect(db_path)
        conn.execute("UPDATE tasks SET status = 'closed' WHERE title = 'Task on A'")
        conn.commit()
        conn.close()

        # Now close should succeed
        res = _run(
            runner, project_dir,
            "backlog", "update", "ideas/guard-test", "--status", "closed",
        )
        assert res.exit_code == 0
        data = _parse_json(res.output)
        assert data.get("status") == "closed"


# ---------------------------------------------------------------------------
# Batch promote tests — --ids flag for promoting multiple independent items
# ---------------------------------------------------------------------------


class TestBatchPromote:
    """Tests for the --ids flag on backlog promote.

    --ids accepts comma-separated backlog IDs and promotes each independently.
    Returns a JSON object with status, count, results array, and optional errors.
    """

    def test_batch_promotes_multiple_items(self, runner, project_dir):
        """--ids with two valid IDs promotes both and returns batch result."""
        res1 = _run(runner, project_dir, "backlog", "add", "--type", "bug", "--title", "Batch Bug A")
        assert res1.exit_code == 0, res1.output
        id_a = _parse_json(res1.output)["id"]

        res2 = _run(runner, project_dir, "backlog", "add", "--type", "bug", "--title", "Batch Bug B")
        assert res2.exit_code == 0, res2.output
        id_b = _parse_json(res2.output)["id"]

        res = _run(
            runner, project_dir,
            "backlog", "promote", "--agent", "test-lead",
            "--ids", f"{id_a},{id_b}",
        )
        assert res.exit_code == 0, res.output
        data = _parse_json(res.output)
        assert data["status"] == "batch_promoted"
        assert data["count"] == 2
        assert len(data["results"]) == 2

    def test_batch_single_id_works(self, runner, project_dir):
        """--ids with a single ID still works (degenerate batch)."""
        res1 = _run(runner, project_dir, "backlog", "add", "--type", "idea", "--title", "Solo Batch")
        assert res1.exit_code == 0, res1.output
        item_id = _parse_json(res1.output)["id"]

        res = _run(
            runner, project_dir,
            "backlog", "promote", "--agent", "test-lead",
            "--ids", str(item_id),
        )
        assert res.exit_code == 0, res.output
        data = _parse_json(res.output)
        assert data["status"] == "batch_promoted"
        assert data["count"] == 1

    def test_batch_with_invalid_id_reports_error(self, runner, project_dir):
        """--ids with one valid and one nonexistent ID: valid succeeds, invalid in errors."""
        res1 = _run(runner, project_dir, "backlog", "add", "--type", "bug", "--title", "Good Batch Item")
        assert res1.exit_code == 0, res1.output
        good_id = _parse_json(res1.output)["id"]

        res = _run(
            runner, project_dir,
            "backlog", "promote", "--agent", "test-lead",
            "--ids", f"{good_id},99999",
        )
        assert res.exit_code == 0, res.output
        data = _parse_json(res.output)
        assert data["count"] == 1  # Only the good one promoted
        assert len(data["errors"]) == 1
        assert data["errors"][0]["id"] == 99999

    def test_batch_cannot_combine_with_path(self, runner, project_dir):
        """--ids cannot be used with a positional PATH argument."""
        res = _run(
            runner, project_dir,
            "backlog", "promote", "--agent", "test-lead",
            "--ids", "1,2", "bugs/some-path",
        )
        assert res.exit_code == 2

    def test_batch_cannot_combine_with_single_id(self, runner, project_dir):
        """--ids cannot be combined with --id."""
        res = _run(
            runner, project_dir,
            "backlog", "promote", "--agent", "test-lead",
            "--ids", "1,2", "--id", "1",
        )
        assert res.exit_code == 2

    def test_batch_cannot_combine_with_count(self, runner, project_dir):
        """--ids cannot be combined with --count."""
        res = _run(
            runner, project_dir,
            "backlog", "promote", "--agent", "test-lead",
            "--ids", "1,2", "--count", "2", "--slugs", "a,b",
        )
        assert res.exit_code == 2

    def test_batch_non_integer_id_exits_nonzero(self, runner, project_dir):
        """--ids with a non-integer value exits with error."""
        res = _run(
            runner, project_dir,
            "backlog", "promote", "--agent", "test-lead",
            "--ids", "abc,def",
        )
        assert res.exit_code == 2

    def test_batch_respects_flow_flag(self, runner, project_dir, db_path):
        """--ids with --flow passes the flow to each promotion."""
        res1 = _run(runner, project_dir, "backlog", "add", "--type", "idea", "--title", "Flow Batch A")
        assert res1.exit_code == 0, res1.output
        id_a = _parse_json(res1.output)["id"]

        res = _run(
            runner, project_dir,
            "backlog", "promote", "--agent", "test-lead",
            "--ids", str(id_a), "--flow", "requirement-lite",
        )
        assert res.exit_code == 0, res.output
        data = _parse_json(res.output)
        assert data["count"] == 1
        # Verify the requirement was created with requirement-lite flow
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        req_path = data["results"][0]["requirement"]["file_path"]
        row = conn.execute("SELECT flow_type FROM requirements WHERE file_path = ?", (req_path,)).fetchone()
        conn.close()
        assert row is not None
        assert row["flow_type"] == "requirement-lite"
