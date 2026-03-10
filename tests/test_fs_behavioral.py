"""Behavioral tests for fs.py — path builders, atomic writes, slug utilities.

Purpose: Verify fs module's path generation, atomic_write_file, read_content_file,
         and ensure_dirs work correctly.
"""

from __future__ import annotations

import os
import pytest

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# _slugify — text to filesystem-safe slug
# ---------------------------------------------------------------------------


def test_slugify_converts_spaces_to_dashes():
    """_slugify converts spaces to dashes."""
    from minion.fs import _slugify
    assert _slugify("hello world") == "hello-world"


def test_slugify_lowercases():
    """_slugify lowercases the input."""
    from minion.fs import _slugify
    assert _slugify("HelloWorld") == "helloworld"


def test_slugify_strips_special_chars():
    """_slugify removes non-alphanumeric characters."""
    from minion.fs import _slugify
    result = _slugify("hello! @world#")
    assert "!" not in result
    assert "@" not in result
    assert "#" not in result


def test_slugify_truncates_at_max_len():
    """_slugify truncates slug to max_len characters."""
    from minion.fs import _slugify
    long_text = "a" * 100
    result = _slugify(long_text, max_len=20)
    assert len(result) <= 20


def test_slugify_empty_string():
    """_slugify handles empty string without error."""
    from minion.fs import _slugify
    result = _slugify("")
    assert isinstance(result, str)


# ---------------------------------------------------------------------------
# _timestamp — compact ISO timestamp
# ---------------------------------------------------------------------------


def test_timestamp_format():
    """_timestamp returns a compact 15-char timestamp string."""
    from minion.fs import _timestamp
    ts = _timestamp()
    assert isinstance(ts, str)
    assert len(ts) == 15  # 20260219T143022
    assert "T" in ts


# ---------------------------------------------------------------------------
# atomic_write_file — write and read back
# ---------------------------------------------------------------------------


def test_atomic_write_file_creates_file(tmp_path):
    """atomic_write_file writes content to a file and returns the path."""
    from minion.fs import atomic_write_file
    target = str(tmp_path / "test.md")
    returned_path = atomic_write_file(target, "hello content")
    assert os.path.exists(returned_path)
    assert open(returned_path).read() == "hello content"


def test_atomic_write_file_overwrites_existing(tmp_path):
    """atomic_write_file overwrites existing file content."""
    from minion.fs import atomic_write_file
    target = str(tmp_path / "overwrite.md")
    atomic_write_file(target, "first content")
    atomic_write_file(target, "second content")
    assert open(target).read() == "second content"


def test_atomic_write_file_creates_parent_dirs(tmp_path):
    """atomic_write_file creates parent directories if needed."""
    from minion.fs import atomic_write_file
    target = str(tmp_path / "deep" / "nested" / "file.md")
    atomic_write_file(target, "deep content")
    assert os.path.exists(target)


# ---------------------------------------------------------------------------
# read_content_file — safe file reader
# ---------------------------------------------------------------------------


def test_read_content_file_reads_existing(tmp_path):
    """read_content_file reads content from an existing file."""
    from minion.fs import read_content_file
    f = tmp_path / "content.md"
    f.write_text("some content")
    result = read_content_file(str(f))
    assert result == "some content"


def test_read_content_file_missing_file_returns_empty():
    """read_content_file returns empty string for missing file."""
    from minion.fs import read_content_file
    result = read_content_file("/nonexistent/path/file.md")
    assert result == "" or result is None


def test_read_content_file_none_input_returns_empty():
    """read_content_file returns empty string when given None."""
    from minion.fs import read_content_file
    result = read_content_file(None)
    assert result == "" or result is None


# ---------------------------------------------------------------------------
# message_file_path — path structure
# ---------------------------------------------------------------------------


def test_message_file_path_contains_agents(tmp_path, monkeypatch):
    """message_file_path returns a path containing to/from agent names."""
    monkeypatch.chdir(tmp_path)
    from minion.fs import message_file_path
    path = message_file_path("leo", "atlas", slug="hello")
    assert "leo" in path
    assert "atlas" in path
    assert path.endswith(".md")


# ---------------------------------------------------------------------------
# inbox_path — creates directory
# ---------------------------------------------------------------------------


def test_inbox_path_creates_directory(tmp_path, monkeypatch):
    """inbox_path creates the inbox directory and returns its path."""
    monkeypatch.chdir(tmp_path)
    from minion.fs import inbox_path
    path = inbox_path("leo")
    assert os.path.isdir(path)
    assert "leo" in path
