"""Tests for checklist template shipping, runtime checklist read/write, and generate command.

Purpose: Verify that checklist templates ship as package data, that the checklist helper
         module correctly reads/writes agent checklists to project-local .work/checklists/,
         that resolve_template maps classes to correct templates, and that the TUI
         _find_checklist only searches .work/checklists/.
Rationale: #238 — templates must be discoverable at runtime, checklists must persist
           to .work/checklists/ (project-local, not global ~/.minion_work/).
Responsibility: Template existence, path resolution, class-to-template resolution,
                write/read round-trip, TUI checklist search scope.
Organization: One test per acceptance criterion.
"""

from __future__ import annotations

import os

import pytest

from minion.checklist import (
    TEMPLATE_NAMES,
    get_checklist_dir,
    get_template_path,
    read_checklist,
    resolve_template,
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
# Template resolution tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestResolveTemplate:
    """Verify resolve_template maps agent classes to the correct templates."""

    def test_coder_resolves_to_worker(self) -> None:
        path = resolve_template("coder")
        assert "worker-checklist.md" in path.name

    def test_lead_resolves_to_lead(self) -> None:
        path = resolve_template("lead")
        assert "lead-checklist.md" in path.name

    def test_recon_resolves_to_worker(self) -> None:
        path = resolve_template("recon")
        assert "worker-checklist.md" in path.name

    def test_auditor_resolves_to_worker(self) -> None:
        path = resolve_template("auditor")
        assert "worker-checklist.md" in path.name

    def test_builder_resolves_to_worker(self) -> None:
        path = resolve_template("builder")
        assert "worker-checklist.md" in path.name

    def test_unknown_class_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="No template found"):
            resolve_template("unknown_class")

    def test_phase_specific_falls_back_to_class_default(self) -> None:
        """When no phase-specific template exists, falls back to class default."""
        path = resolve_template("coder", "nonexistent_phase")
        assert "worker-checklist.md" in path.name


# ---------------------------------------------------------------------------
# Runtime checklist tests — project-local .work/checklists/
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestChecklistReadWrite:
    """Verify write_checklist and read_checklist round-trip correctly using project-local dir."""

    def test_write_creates_file(self, tmp_path: object) -> None:
        """write_checklist() creates a .md file in the project-local checklist dir."""
        tmp = tmp_path  # type: ignore[assignment]
        project_dir = tmp / "project"
        project_dir.mkdir()

        path = write_checklist("test-agent", "# Test Checklist\n- [ ] item 1\n", project_dir=project_dir)
        assert path.exists()
        assert path.name == "test-agent.md"
        assert "item 1" in path.read_text(encoding="utf-8")
        # Verify it's in .work/checklists/ under project dir
        assert ".work" in str(path)
        assert "checklists" in str(path)

    def test_read_returns_content(self, tmp_path: object) -> None:
        """read_checklist() returns content written by write_checklist()."""
        tmp = tmp_path  # type: ignore[assignment]
        project_dir = tmp / "project"
        project_dir.mkdir()

        write_checklist("roundtrip-agent", "# Roundtrip\n- [x] done\n", project_dir=project_dir)
        content = read_checklist("roundtrip-agent", project_dir=project_dir)
        assert content is not None
        assert "Roundtrip" in content
        assert "[x] done" in content

    def test_read_returns_none_for_missing(self, tmp_path: object) -> None:
        """read_checklist() returns None when no checklist exists."""
        tmp = tmp_path  # type: ignore[assignment]
        project_dir = tmp / "project"
        project_dir.mkdir()

        result = read_checklist("ghost-agent", project_dir=project_dir)
        assert result is None

    def test_get_checklist_dir_creates_directory(self, tmp_path: object) -> None:
        """get_checklist_dir() creates the directory if it doesn't exist."""
        tmp = tmp_path  # type: ignore[assignment]
        project_dir = tmp / "project"
        project_dir.mkdir()

        result = get_checklist_dir(project_dir)
        assert result.exists()
        assert result.is_dir()
        assert str(result).endswith(".work/checklists")


# ---------------------------------------------------------------------------
# TUI _find_checklist scope test
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFindChecklistScope:
    """Verify _find_checklist in render.py only searches .work/checklists/."""

    def test_find_checklist_only_searches_project_local(self, tmp_path: object) -> None:
        """_find_checklist should NOT search ~/.minion_work/checklists/."""
        from minion.dashboard.render import _find_checklist

        tmp = tmp_path  # type: ignore[assignment]
        work_dir = tmp / ".work"
        work_dir.mkdir()
        checklists_dir = work_dir / "checklists"
        checklists_dir.mkdir()

        # Write a checklist in project-local dir
        (checklists_dir / "agent-a.md").write_text("# agent-a checklist")

        # Should find it in project-local
        result = _find_checklist("agent-a", str(work_dir))
        assert result is not None
        assert "agent-a.md" in result

    def test_find_checklist_returns_none_without_work_dir(self) -> None:
        """_find_checklist returns None when work_dir is empty."""
        from minion.dashboard.render import _find_checklist

        result = _find_checklist("any-agent", "")
        assert result is None

    def test_find_checklist_prefers_lead_prefix(self, tmp_path: object) -> None:
        """_find_checklist prefers lead-<name>.md over <name>.md."""
        from minion.dashboard.render import _find_checklist

        tmp = tmp_path  # type: ignore[assignment]
        work_dir = tmp / ".work"
        checklists_dir = work_dir / "checklists"
        checklists_dir.mkdir(parents=True)

        (checklists_dir / "my-lead.md").write_text("# worker")
        (checklists_dir / "lead-my-lead.md").write_text("# lead")

        result = _find_checklist("my-lead", str(work_dir))
        assert result is not None
        assert "lead-my-lead.md" in result

    def test_find_checklist_does_not_search_global(self, tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
        """_find_checklist must NOT look in ~/.minion_work/checklists/."""
        tmp = tmp_path  # type: ignore[assignment]

        # Create a global checklist that should NOT be found
        global_dir = tmp / "global_home" / ".minion_work" / "checklists"
        global_dir.mkdir(parents=True)
        (global_dir / "global-agent.md").write_text("# global checklist")

        # Create an empty project work_dir with no checklists
        work_dir = tmp / "project" / ".work"
        work_dir.mkdir(parents=True)

        from minion.dashboard.render import _find_checklist

        # Should NOT find the global checklist
        result = _find_checklist("global-agent", str(work_dir))
        assert result is None
