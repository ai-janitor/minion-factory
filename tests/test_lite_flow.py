"""Tests for the requirement-lite flow — 4-stage shortcut lifecycle.

Covers:
- requirement-lite.yaml has exactly 4 stages
- Transitions work: seed → decomposing → tasked → completed
- Default flow still uses the full requirement.yaml (9 stages)
- register() stores flow_type correctly
- update_stage() picks up flow_type from the DB
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pytest
from click.testing import CliRunner

from minion.cli import cli


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _setup_project(tmp_path: Path) -> Path:
    """Initialize a project dir with .work/ tree via CLI."""
    work = tmp_path / ".work"
    work.mkdir()
    runner = CliRunner()
    result = runner.invoke(cli, ["-C", str(tmp_path), "agent", "--help"])
    assert result.exit_code == 0, result.output
    return tmp_path


def _run(runner: CliRunner, project_dir: Path, *args: str):
    return runner.invoke(cli, ["-C", str(project_dir)] + list(args))


def _req_row(db_path: str, file_path: str) -> dict:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM requirements WHERE file_path = ?", (file_path,)
    ).fetchone()
    conn.close()
    assert row is not None, f"Requirement '{file_path}' not found in DB"
    return dict(row)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def project_dir(tmp_path):
    return _setup_project(tmp_path)


@pytest.fixture
def db_path(project_dir):
    return str(project_dir / ".work" / "minion.db")


@pytest.fixture
def runner():
    return CliRunner()


# ---------------------------------------------------------------------------
# Test: requirement-lite.yaml shape
# ---------------------------------------------------------------------------


class TestLiteFlowShape:
    def test_lite_flow_has_four_stages(self):
        """requirement-lite.yaml must define exactly 4 stages."""
        from minion.tasks.loader import load_flow

        flow = load_flow("requirement-lite")
        assert len(flow.stages) == 4, (
            f"Expected 4 stages, got {len(flow.stages)}: {list(flow.stages)}"
        )

    def test_lite_flow_stage_names(self):
        """requirement-lite.yaml must have seed, decomposing, tasked, completed."""
        from minion.tasks.loader import load_flow

        flow = load_flow("requirement-lite")
        assert set(flow.stages.keys()) == {"seed", "decomposing", "tasked", "completed"}

    def test_lite_flow_name_field(self):
        """Flow name field must be 'requirement-lite'."""
        from minion.tasks.loader import load_flow

        flow = load_flow("requirement-lite")
        assert flow.name == "requirement-lite"

    def test_lite_flow_completed_is_terminal(self):
        """completed stage must be terminal."""
        from minion.tasks.loader import load_flow

        flow = load_flow("requirement-lite")
        assert flow.stages["completed"].terminal is True


# ---------------------------------------------------------------------------
# Test: lite flow transitions via resolve_next
# ---------------------------------------------------------------------------


class TestLiteFlowTransitions:
    def test_seed_to_decomposing(self):
        """Happy path from seed must be decomposing (not itemizing)."""
        from minion.tasks.engine import resolve_next
        from minion.tasks.loader import load_flow

        flow = load_flow("requirement-lite")
        result = resolve_next(flow, "seed")
        assert result.success, f"Expected success, got: {result.error}"
        assert result.to_status == "decomposing"

    def test_decomposing_to_tasked(self):
        """Happy path from decomposing must be tasked."""
        from minion.tasks.engine import resolve_next
        from minion.tasks.loader import load_flow

        flow = load_flow("requirement-lite")
        result = resolve_next(flow, "decomposing")
        assert result.success
        assert result.to_status == "tasked"

    def test_tasked_to_completed(self):
        """Happy path from tasked must be completed."""
        from minion.tasks.engine import resolve_next
        from minion.tasks.loader import load_flow

        flow = load_flow("requirement-lite")
        result = resolve_next(flow, "tasked")
        assert result.success
        assert result.to_status == "completed"

    def test_completed_is_terminal_no_next(self):
        """resolve_next on completed must fail (terminal — no next stage)."""
        from minion.tasks.engine import resolve_next
        from minion.tasks.loader import load_flow

        flow = load_flow("requirement-lite")
        result = resolve_next(flow, "completed")
        assert not result.success

    def test_decomposing_fail_returns_to_seed(self):
        """Fail path from decomposing must return to seed."""
        from minion.tasks.engine import resolve_next
        from minion.tasks.loader import load_flow

        flow = load_flow("requirement-lite")
        result = resolve_next(flow, "decomposing", passed=False)
        assert result.success
        assert result.to_status == "seed"

    def test_no_itemizing_stage(self):
        """Lite flow must not include itemizing — that's full-flow only."""
        from minion.tasks.loader import load_flow

        flow = load_flow("requirement-lite")
        assert "itemizing" not in flow.stages
        assert "itemized" not in flow.stages
        assert "investigating" not in flow.stages
        assert "findings_ready" not in flow.stages
        assert "in_progress" not in flow.stages


# ---------------------------------------------------------------------------
# Test: default flow still uses full requirement.yaml
# ---------------------------------------------------------------------------


class TestDefaultFlowUnchanged:
    def test_full_flow_has_nine_stages(self):
        """requirement.yaml must still have all 9 stages."""
        from minion.tasks.loader import load_flow

        flow = load_flow("requirement")
        expected = {
            "seed", "itemizing", "itemized", "investigating", "findings_ready",
            "decomposing", "tasked", "in_progress", "completed",
        }
        assert set(flow.stages.keys()) == expected

    def test_full_flow_seed_goes_to_itemizing(self):
        """Full flow seed happy path must still be itemizing (not decomposing)."""
        from minion.tasks.engine import resolve_next
        from minion.tasks.loader import load_flow

        flow = load_flow("requirement")
        result = resolve_next(flow, "seed")
        assert result.success
        assert result.to_status == "itemizing"

    def test_register_without_flow_type_defaults_to_requirement(self, db_path, project_dir):
        """register() with no flow_type arg must store 'requirement' in DB."""
        os.environ["MINION_DB_PATH"] = db_path
        from minion.db import reset_db_path
        reset_db_path()

        req_path = project_dir / ".work" / "requirements" / "features" / "default-flow-test"
        req_path.mkdir(parents=True)
        (req_path / "README.md").write_text("# Default flow test\n")

        from minion.requirements.crud import register
        result = register("features/default-flow-test", created_by="test")
        assert "error" not in result, result
        assert result.get("flow_type") == "requirement"

        row = _req_row(db_path, "features/default-flow-test")
        assert row["flow_type"] == "requirement"


# ---------------------------------------------------------------------------
# Test: register() stores flow_type correctly
# ---------------------------------------------------------------------------


class TestRegisterFlowType:
    def test_register_with_lite_flow_stores_flow_type(self, db_path, project_dir):
        """register() with flow_type='requirement-lite' must persist it to DB."""
        os.environ["MINION_DB_PATH"] = db_path
        from minion.db import reset_db_path
        reset_db_path()

        req_path = project_dir / ".work" / "requirements" / "features" / "lite-reg-test"
        req_path.mkdir(parents=True)
        (req_path / "README.md").write_text("# Lite registration test\n")

        from minion.requirements.crud import register
        result = register("features/lite-reg-test", created_by="test", flow_type="requirement-lite")
        assert "error" not in result, result
        assert result.get("flow_type") == "requirement-lite"

        row = _req_row(db_path, "features/lite-reg-test")
        assert row["flow_type"] == "requirement-lite"

    def test_register_with_full_flow_stores_flow_type(self, db_path, project_dir):
        """register() with flow_type='requirement' must persist it to DB."""
        os.environ["MINION_DB_PATH"] = db_path
        from minion.db import reset_db_path
        reset_db_path()

        req_path = project_dir / ".work" / "requirements" / "features" / "full-reg-test"
        req_path.mkdir(parents=True)
        (req_path / "README.md").write_text("# Full registration test\n")

        from minion.requirements.crud import register
        result = register("features/full-reg-test", created_by="test", flow_type="requirement")
        assert "error" not in result, result

        row = _req_row(db_path, "features/full-reg-test")
        assert row["flow_type"] == "requirement"


# ---------------------------------------------------------------------------
# Test: update_stage() uses stored flow_type
# ---------------------------------------------------------------------------


class TestUpdateStageUsesFlowType:
    def _make_req(self, project_dir: Path, rel_path: str, flow_type: str, db_path: str) -> None:
        """Create requirement folder + README, register with given flow_type."""
        os.environ["MINION_DB_PATH"] = db_path
        from minion.db import reset_db_path
        reset_db_path()

        abs_path = project_dir / ".work" / "requirements" / rel_path
        abs_path.mkdir(parents=True)
        (abs_path / "README.md").write_text(f"# {rel_path}\n")

        from minion.requirements.crud import register
        result = register(rel_path, created_by="test", flow_type=flow_type)
        assert "error" not in result, result

    def test_lite_req_update_stage_to_decomposing(self, db_path, project_dir):
        """update_stage() on lite req accepts decomposing (valid lite transition)."""
        rel = "features/lite-update-test"
        self._make_req(project_dir, rel, "requirement-lite", db_path)

        from minion.requirements.crud import update_stage
        result = update_stage(rel, "decomposing")
        assert "error" not in result, result
        assert result["to_stage"] == "decomposing"

    def test_lite_req_update_stage_rejects_itemizing(self, db_path, project_dir):
        """update_stage() on lite req rejects itemizing (not in lite flow)."""
        rel = "features/lite-reject-itemizing"
        self._make_req(project_dir, rel, "requirement-lite", db_path)

        from minion.requirements.crud import update_stage
        result = update_stage(rel, "itemizing")
        assert "error" in result, f"Expected error, got: {result}"
        assert "itemizing" in result["error"] or "Unknown stage" in result["error"]

    def test_full_req_update_stage_accepts_itemizing(self, db_path, project_dir):
        """update_stage() on full req accepts itemizing (valid full-flow transition)."""
        rel = "features/full-accept-itemizing"
        self._make_req(project_dir, rel, "requirement", db_path)

        from minion.requirements.crud import update_stage
        result = update_stage(rel, "itemizing")
        # Gate check may block, but should not return "Unknown stage" error
        if "error" in result:
            assert "Unknown stage" not in result["error"], (
                f"Should not reject itemizing for full-flow requirement: {result}"
            )
