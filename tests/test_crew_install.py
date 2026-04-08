"""Tests for `minion crew install` (backlog #337)."""

from __future__ import annotations

from pathlib import Path

import pytest

from minion.crew.install import install_crews


@pytest.fixture
def fake_source_and_dest(tmp_path: Path) -> tuple[Path, Path]:
    src = tmp_path / "src" / "crews"
    src.mkdir(parents=True)
    (src / "alpha.yaml").write_text("name: alpha\n")
    (src / "beta.yaml").write_text("name: beta\n")
    (src / "README.md").write_text("ignored\n")  # not a yaml — must be skipped
    dest = tmp_path / "dest"
    return src, dest


def test_install_copies_into_empty_dest(fake_source_and_dest):
    src, dest = fake_source_and_dest
    result = install_crews(source=str(src), dest=str(dest))
    assert result["status"] == "installed"
    assert sorted(result["copied"]) == ["alpha.yaml", "beta.yaml"]
    assert result["overwrote"] == []
    assert (dest / "alpha.yaml").read_text() == "name: alpha\n"
    assert not (dest / "README.md").exists()


def test_install_skips_unchanged(fake_source_and_dest):
    src, dest = fake_source_and_dest
    install_crews(source=str(src), dest=str(dest))  # first copy
    result = install_crews(source=str(src), dest=str(dest))  # second run
    assert result["copied"] == []
    assert result["overwrote"] == []
    assert sorted(result["skipped_unchanged"]) == ["alpha.yaml", "beta.yaml"]


def test_install_refuses_to_clobber_newer_dest(fake_source_and_dest):
    src, dest = fake_source_and_dest
    install_crews(source=str(src), dest=str(dest))  # seed
    # Operator edited the installed copy after install — different bytes,
    # newer mtime.
    edited = dest / "alpha.yaml"
    edited.write_text("name: alpha\n# operator edit\n")
    import os, time
    future = time.time() + 60
    os.utime(edited, (future, future))

    result = install_crews(source=str(src), dest=str(dest))
    assert "alpha.yaml" in result["skipped_newer_in_dest"]
    # Edit must survive
    assert "operator edit" in edited.read_text()


def test_install_force_overrides_newer_dest(fake_source_and_dest):
    src, dest = fake_source_and_dest
    install_crews(source=str(src), dest=str(dest))
    edited = dest / "alpha.yaml"
    edited.write_text("name: alpha\n# operator edit\n")
    import os, time
    future = time.time() + 60
    os.utime(edited, (future, future))

    result = install_crews(source=str(src), dest=str(dest), force=True)
    assert "alpha.yaml" in result["overwrote"]
    assert edited.read_text() == "name: alpha\n"  # source value


def test_install_dry_run_writes_nothing(fake_source_and_dest):
    src, dest = fake_source_and_dest
    result = install_crews(source=str(src), dest=str(dest), dry_run=True)
    assert result["status"] == "dry-run"
    assert sorted(result["copied"]) == ["alpha.yaml", "beta.yaml"]
    assert not (dest / "alpha.yaml").exists()


def test_install_missing_source_returns_error(tmp_path: Path):
    result = install_crews(source=str(tmp_path / "nope"))
    assert "error" in result
