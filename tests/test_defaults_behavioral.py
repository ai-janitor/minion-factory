"""Behavioral tests for defaults.py — path resolution, env var overrides.

Purpose: Verify resolve_db_path, resolve_docs_dir, resolve_work_dir, and
         resolve_coordinator_db_path respect env overrides and fall through
         to sensible defaults.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.db]


# ---------------------------------------------------------------------------
# resolve_db_path — env override
# ---------------------------------------------------------------------------


def test_resolve_db_path_uses_env_override(monkeypatch, tmp_path):
    """When MINION_DB_PATH is set, resolve_db_path returns it directly."""
    explicit = str(tmp_path / "custom.db")
    monkeypatch.setenv("MINION_DB_PATH", explicit)
    from minion.defaults import resolve_db_path
    assert resolve_db_path() == explicit


def test_resolve_db_path_falls_back_to_cwd(monkeypatch, tmp_path):
    """Without env var, resolve_db_path returns a .work/minion.db path."""
    monkeypatch.delenv("MINION_DB_PATH", raising=False)
    monkeypatch.delenv("MINION_PROJECT", raising=False)
    monkeypatch.chdir(tmp_path)
    from minion.defaults import resolve_db_path
    result = resolve_db_path()
    assert result.endswith("minion.db")
    assert ".work" in result


def test_resolve_db_path_walks_up_to_find_existing_db(monkeypatch, tmp_path):
    """Walk-up: resolve_db_path finds .work/minion.db in a parent directory."""
    monkeypatch.delenv("MINION_DB_PATH", raising=False)
    monkeypatch.delenv("MINION_PROJECT", raising=False)
    # Create .work/minion.db in tmp_path
    work = tmp_path / ".work"
    work.mkdir()
    db = work / "minion.db"
    db.write_text("")
    # Change to a subdirectory
    subdir = tmp_path / "subdir"
    subdir.mkdir()
    monkeypatch.chdir(subdir)
    from minion import defaults
    import importlib
    importlib.reload(defaults)
    result = defaults.resolve_db_path()
    assert str(db) == result


# ---------------------------------------------------------------------------
# resolve_docs_dir — env override and default
# ---------------------------------------------------------------------------


def test_resolve_docs_dir_uses_env_override(monkeypatch, tmp_path):
    """When MINION_DOCS_DIR is set, resolve_docs_dir returns it."""
    monkeypatch.setenv("MINION_DOCS_DIR", str(tmp_path))
    from minion.defaults import resolve_docs_dir
    assert resolve_docs_dir() == str(tmp_path)


def test_resolve_docs_dir_default_is_under_home(monkeypatch):
    """Without env var, resolve_docs_dir returns a path under home."""
    monkeypatch.delenv("MINION_DOCS_DIR", raising=False)
    from minion.defaults import resolve_docs_dir
    result = resolve_docs_dir()
    assert str(Path.home()) in result


# ---------------------------------------------------------------------------
# resolve_work_dir — returns .work under project
# ---------------------------------------------------------------------------


def test_resolve_work_dir_default_is_cwd_work(tmp_path, monkeypatch):
    """resolve_work_dir with no args returns cwd/.work."""
    monkeypatch.chdir(tmp_path)
    from minion.defaults import resolve_work_dir
    result = resolve_work_dir()
    assert result == tmp_path / ".work"


def test_resolve_work_dir_with_project_dir(tmp_path):
    """resolve_work_dir with project_dir returns project_dir/.work."""
    from minion.defaults import resolve_work_dir
    result = resolve_work_dir(tmp_path)
    assert result == tmp_path / ".work"


# ---------------------------------------------------------------------------
# resolve_coordinator_db_path — env override
# ---------------------------------------------------------------------------


def test_resolve_coordinator_db_path_env_override(monkeypatch, tmp_path):
    """MINION_COORDINATOR_DB_PATH overrides the default coordinator path."""
    explicit = str(tmp_path / "coord.db")
    monkeypatch.setenv("MINION_COORDINATOR_DB_PATH", explicit)
    from minion.defaults import resolve_coordinator_db_path
    assert resolve_coordinator_db_path() == explicit


def test_resolve_coordinator_db_path_default_under_home(monkeypatch):
    """Without env var, coordinator DB is under ~/.minion/."""
    monkeypatch.delenv("MINION_COORDINATOR_DB_PATH", raising=False)
    from minion.defaults import resolve_coordinator_db_path
    result = resolve_coordinator_db_path()
    assert "coordinator.db" in result
    assert str(Path.home()) in result


# ---------------------------------------------------------------------------
# resolve_path — relative paths resolve against base
# ---------------------------------------------------------------------------


def test_resolve_path_absolute_unchanged(tmp_path):
    """resolve_path with absolute path returns it unchanged."""
    from minion.defaults import resolve_path
    absolute = tmp_path / "foo.py"
    result = resolve_path(str(absolute), tmp_path)
    assert result == absolute


def test_resolve_path_relative_resolves_against_base(tmp_path):
    """resolve_path with relative path resolves against base directory."""
    from minion.defaults import resolve_path
    result = resolve_path("foo/bar.py", tmp_path)
    assert result == (tmp_path / "foo" / "bar.py").resolve()
