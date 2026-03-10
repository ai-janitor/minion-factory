"""Verify every module imports cleanly with no errors.

Purpose: Verify every module imports cleanly with no errors.
Rationale: Test coverage for the corresponding module.
Responsibility: Verify every module imports cleanly with no errors. NOT responsible for unrelated concerns.
Organization: One TestClass per concern, or standalone test functions."""
import pytest

pytestmark = pytest.mark.unit


def test_import_minion():
    import minion  # noqa: F401


def test_import_auth():
    import minion.auth  # noqa: F401


def test_import_cli():
    import minion.cli  # noqa: F401


def test_import_comms():
    import minion.comms  # noqa: F401


def test_import_db():
    import minion.db  # noqa: F401


def test_import_defaults():
    import minion.defaults  # noqa: F401


def test_import_filesafety():
    import minion.filesafety  # noqa: F401


def test_import_fs():
    import minion.fs  # noqa: F401


def test_import_lifecycle():
    import minion.lifecycle  # noqa: F401


def test_import_monitoring():
    import minion.monitoring  # noqa: F401


def test_import_polling():
    import minion.polling  # noqa: F401


def test_import_triggers():
    import minion.triggers  # noqa: F401


def test_import_warroom():
    import minion.warroom  # noqa: F401


def test_import_crew():
    import minion.crew  # noqa: F401


def test_import_daemon():
    import minion.daemon  # noqa: F401


def test_import_providers():
    import minion.providers  # noqa: F401


def test_import_tasks():
    import minion.tasks  # noqa: F401
