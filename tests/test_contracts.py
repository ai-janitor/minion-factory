"""Validate contract JSON files and the Python contract loader."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# repo root → docs/contracts/
CONTRACTS_DIR = Path(__file__).resolve().parent.parent / "docs" / "contracts"
DOCS_DIR = CONTRACTS_DIR.parent  # docs/ — what load_contract expects

CONTRACT_NAMES = [
    "boot-sequence",
    "compaction-markers",
    "config-defaults",
    "daemon-rules",
    "inbox-template",
    "state-schema",
]


@pytest.fixture
def contracts_dir() -> Path:
    assert CONTRACTS_DIR.is_dir(), f"contracts dir missing: {CONTRACTS_DIR}"
    return CONTRACTS_DIR


# ── Every contract loads as valid JSON ─────────────────────────────────


@pytest.mark.parametrize("name", CONTRACT_NAMES)
def test_contract_loads_valid_json(contracts_dir: Path, name: str):
    path = contracts_dir / f"{name}.json"
    assert path.exists(), f"{name}.json not found"
    data = json.loads(path.read_text())
    assert isinstance(data, dict)


# ── Required keys per contract ─────────────────────────────────────────


def test_boot_sequence_keys(contracts_dir: Path):
    data = json.loads((contracts_dir / "boot-sequence.json").read_text())
    assert set(data.keys()) >= {"commands", "preamble", "postamble"}


def test_daemon_rules_keys(contracts_dir: Path):
    data = json.loads((contracts_dir / "daemon-rules.json").read_text())
    assert set(data.keys()) >= {"common", "lead", "non_lead"}


def test_inbox_template_keys(contracts_dir: Path):
    data = json.loads((contracts_dir / "inbox-template.json").read_text())
    expected = {
        "inbox_header",
        "inbox_footer",
        "message_format",
        "task_header",
        "task_footer",
        "task_format",
        "post_instructions",
    }
    assert set(data.keys()) >= expected


def test_config_defaults_keys(contracts_dir: Path):
    data = json.loads((contracts_dir / "config-defaults.json").read_text())
    expected = {
        "max_history_tokens",
        "max_prompt_chars",
        "no_output_timeout_sec",
        "retry_backoff_sec",
        "retry_backoff_max_sec",
        "max_console_stream_chars",
        "token_to_char_ratio",
        "default_context_window",
    }
    assert set(data.keys()) >= expected


def test_state_schema_keys(contracts_dir: Path):
    data = json.loads((contracts_dir / "state-schema.json").read_text())
    assert set(data.keys()) >= {"casing", "required_fields", "optional_fields", "status_enum"}


def test_compaction_markers_keys(contracts_dir: Path):
    data = json.loads((contracts_dir / "compaction-markers.json").read_text())
    assert set(data.keys()) >= {"substring_markers", "sdk_event", "history_block"}


# ── Value-level invariants ─────────────────────────────────────────────


def test_boot_sequence_has_exactly_3_commands(contracts_dir: Path):
    data = json.loads((contracts_dir / "boot-sequence.json").read_text())
    assert len(data["commands"]) == 3
    for cmd in data["commands"]:
        assert isinstance(cmd, str)
        assert "check-inbox" not in cmd, "boot commands must not contain check-inbox"


def test_state_schema_status_enum(contracts_dir: Path):
    data = json.loads((contracts_dir / "state-schema.json").read_text())
    expected_statuses = {"idle", "working", "error", "stopped"}
    assert set(data["status_enum"]) == expected_statuses


def test_config_defaults_values_are_positive_ints(contracts_dir: Path):
    data = json.loads((contracts_dir / "config-defaults.json").read_text())
    for key, value in data.items():
        assert isinstance(value, int), f"{key} should be int, got {type(value).__name__}"
        assert value > 0, f"{key} should be positive, got {value}"


def test_compaction_markers_has_substring_markers(contracts_dir: Path):
    data = json.loads((contracts_dir / "compaction-markers.json").read_text())
    assert len(data["substring_markers"]) >= 1


# ── Python contract loader ─────────────────────────────────────────────


def test_load_contract_returns_dict():
    from minion.daemon.contracts import load_contract

    result = load_contract(DOCS_DIR, "boot-sequence")
    assert isinstance(result, dict)
    assert "commands" in result


def test_load_contract_returns_none_for_missing():
    from minion.daemon.contracts import load_contract

    result = load_contract(DOCS_DIR, "nonexistent-contract")
    assert result is None


@pytest.mark.parametrize("name", CONTRACT_NAMES)
def test_load_contract_all_contracts(name: str):
    from minion.daemon.contracts import load_contract

    result = load_contract(DOCS_DIR, name)
    assert result is not None, f"load_contract failed for {name}"
    assert isinstance(result, dict)
