"""Tests for checklist template shipping and runtime checklist read/write.

Purpose: Verify that checklist templates ship as package data and that the
         checklist helper module correctly reads/writes agent checklists.
Rationale: #238 — templates must be discoverable at runtime, checklists must
           persist to ~/.minion_work/checklists/.
Responsibility: Template existence, path resolution, write/read round-trip.
Organization: One test per acceptance criterion.
"""

from __future__ import annotations

import pytest

from minion.checklist import (
    TEMPLATE_NAMES,
    get_checklist_dir,
    get_template_path,
    read_checklist,
    write_checklist,
)


# ---------------------------------------------------------------------------
# Template tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestTemplates:
    """Verify that all 3 checklist templates exist and are readable."""

    def test_template_names_are_defined(self) -> None:
        assert TEMPLATE_NAMES == ("napoleon", "lead", "worker")

    @pytest.mark.parametrize("name", TEMPLATE_NAMES)
    def test_get_template_path_returns_valid_path(self, name: str) -> None:
        path = get_template_path(name)
        assert path.exists(), f"Template {name} not found at {path}"
        assert path.suffix == ".md"

    @pytest.mark.parametrize("name", TEMPLATE_NAMES)
    def test_template_is_readable_and_nonempty(self, name: str) -> None:
        path = get_template_path(name)
        content = path.read_text(encoding="utf-8")
        assert len(content) > 50, f"Template {name} is suspiciously short"

    def test_unknown_template_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Unknown template"):
            get_template_path("nonexistent")


# ---------------------------------------------------------------------------
# Runtime checklist tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestChecklistReadWrite:
    """Verify write_checklist and read_checklist round-trip correctly."""

    def test_write_creates_file(self, monkeypatch: pytest.MonkeyPatch, tmp_path: object) -> None:
        """write_checklist() creates a .md file in the checklist dir."""
        import minion.checklist as mod

        tmp = tmp_path  # type: ignore[assignment]
        monkeypatch.setattr(mod, "_CHECKLIST_DIR", tmp)

        path = write_checklist("test-agent", "# Test Checklist\n- [ ] item 1\n")
        assert path.exists()
        assert path.name == "test-agent.md"
        assert "item 1" in path.read_text(encoding="utf-8")

    def test_read_returns_content(self, monkeypatch: pytest.MonkeyPatch, tmp_path: object) -> None:
        """read_checklist() returns content written by write_checklist()."""
        import minion.checklist as mod

        tmp = tmp_path  # type: ignore[assignment]
        monkeypatch.setattr(mod, "_CHECKLIST_DIR", tmp)

        write_checklist("roundtrip-agent", "# Roundtrip\n- [x] done\n")
        content = read_checklist("roundtrip-agent")
        assert content is not None
        assert "Roundtrip" in content
        assert "[x] done" in content

    def test_read_returns_none_for_missing(self, monkeypatch: pytest.MonkeyPatch, tmp_path: object) -> None:
        """read_checklist() returns None when no checklist exists."""
        import minion.checklist as mod

        tmp = tmp_path  # type: ignore[assignment]
        monkeypatch.setattr(mod, "_CHECKLIST_DIR", tmp)

        result = read_checklist("ghost-agent")
        assert result is None

    def test_get_checklist_dir_creates_directory(self, monkeypatch: pytest.MonkeyPatch, tmp_path: object) -> None:
        """get_checklist_dir() creates the directory if it doesn't exist."""
        import minion.checklist as mod

        tmp = tmp_path  # type: ignore[assignment]
        target = tmp / "checklists"
        monkeypatch.setattr(mod, "_CHECKLIST_DIR", target)

        result = get_checklist_dir()
        assert result.exists()
        assert result.is_dir()
