"""Integration tests for the CLI adapter.

These tests drive the Typer application through ``CliRunner``, which
invokes commands exactly the way the shell would. They exercise the full
stack: argument parsing → command body → HabitTracker → Storage → SQLite.

Each test gets an isolated SQLite file in ``tmp_path`` so no state leaks
between invocations.
"""

from __future__ import annotations

from datetime import datetime

import pytest
from habit_tracker.cli.main import app
from typer.testing import CliRunner

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def runner() -> CliRunner:
    """CliRunner with a stable, non-interactive invocation style."""
    return CliRunner()


@pytest.fixture()
def db(tmp_path) -> str:
    """Path to a throwaway SQLite file for a single test."""
    return str(tmp_path / "cli.db")


def _invoke(runner: CliRunner, db: str, *args: str):
    """Shorthand: invoke the CLI against a specific database file."""
    return runner.invoke(app, ["--db", db, *args])


# ---------------------------------------------------------------------------
# --help and version
# ---------------------------------------------------------------------------


def test_cli_help_lists_commands(runner):
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for command in ("create", "delete", "check-off", "list-habits", "analyse"):
        assert command in result.stdout


def test_cli_version(runner):
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "habit-tracker" in result.stdout
    assert "0.1.0" in result.stdout


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------


def test_create_prints_id_and_name(runner, db):
    result = _invoke(runner, db, "create", "-n", "Water", "-d", "2L", "-p", "daily")
    assert result.exit_code == 0
    assert "Created habit #1" in result.stdout
    assert "Water" in result.stdout
    assert "daily" in result.stdout


def test_create_assigns_monotonic_ids(runner, db):
    _invoke(runner, db, "create", "-n", "A", "-p", "daily")
    _invoke(runner, db, "create", "-n", "B", "-p", "weekly")
    result = _invoke(runner, db, "create", "-n", "C", "-p", "daily")
    assert "Created habit #3" in result.stdout


def test_create_rejects_invalid_periodicity(runner, db):
    result = _invoke(runner, db, "create", "-n", "Bad", "-p", "monthly")
    # Typer fails argument validation with exit code 2.
    assert result.exit_code == 2


def test_create_requires_name(runner, db):
    result = _invoke(runner, db, "create", "-p", "daily")
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# list-habits
# ---------------------------------------------------------------------------


def test_list_empty_shows_guidance(runner, db):
    result = _invoke(runner, db, "list-habits")
    assert result.exit_code == 0
    assert "No habits yet" in result.stdout


def test_list_shows_created_habits(runner, db):
    _invoke(runner, db, "create", "-n", "Water", "-p", "daily")
    _invoke(runner, db, "create", "-n", "Review", "-p", "weekly")

    result = _invoke(runner, db, "list-habits")
    assert result.exit_code == 0
    assert "Water" in result.stdout
    assert "Review" in result.stdout
    assert "[daily]" in result.stdout
    assert "[weekly]" in result.stdout


def test_list_filters_by_periodicity(runner, db):
    _invoke(runner, db, "create", "-n", "Water", "-p", "daily")
    _invoke(runner, db, "create", "-n", "Review", "-p", "weekly")

    result = _invoke(runner, db, "list-habits", "-p", "daily")
    assert result.exit_code == 0
    assert "Water" in result.stdout
    assert "Review" not in result.stdout


def test_list_rejects_invalid_periodicity_filter(runner, db):
    result = _invoke(runner, db, "list-habits", "-p", "monthly")
    assert result.exit_code == 2


# ---------------------------------------------------------------------------
# check-off
# ---------------------------------------------------------------------------


def test_check_off_records_completion(runner, db):
    _invoke(runner, db, "create", "-n", "Water", "-p", "daily")
    result = _invoke(runner, db, "check-off", "--id", "1", "--when", "2024-01-15T09:00:00")
    assert result.exit_code == 0
    assert "Checked off habit #1" in result.stdout
    assert "2024-01-15T09:00:00" in result.stdout


def test_check_off_defaults_to_now(runner, db):
    _invoke(runner, db, "create", "-n", "Water", "-p", "daily")
    result = _invoke(runner, db, "check-off", "--id", "1")
    assert result.exit_code == 0
    # The output contains today's year.
    assert str(datetime.now().year) in result.stdout


def test_check_off_unknown_habit_exits_nonzero(runner, db):
    result = _invoke(runner, db, "check-off", "--id", "99")
    assert result.exit_code == 1
    assert "habit 99 not found" in result.stdout or "habit 99 not found" in result.stderr


def test_check_off_rejects_bad_iso_timestamp(runner, db):
    _invoke(runner, db, "create", "-n", "Water", "-p", "daily")
    result = _invoke(runner, db, "check-off", "--id", "1", "--when", "not-a-date")
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------


def test_delete_removes_habit(runner, db):
    _invoke(runner, db, "create", "-n", "Water", "-p", "daily")
    result = _invoke(runner, db, "delete", "--id", "1")
    assert result.exit_code == 0
    assert "Deleted habit #1" in result.stdout

    listed = _invoke(runner, db, "list-habits")
    assert "Water" not in listed.stdout


def test_delete_unknown_habit_exits_nonzero(runner, db):
    result = _invoke(runner, db, "delete", "--id", "42")
    assert result.exit_code == 1
    assert "habit 42 not found" in result.stdout or "habit 42 not found" in result.stderr


def test_delete_cascades_completions(runner, db):
    _invoke(runner, db, "create", "-n", "Water", "-p", "daily")
    _invoke(runner, db, "check-off", "--id", "1", "--when", "2024-01-01T09:00:00")
    _invoke(runner, db, "delete", "--id", "1")

    # Recreate under a new name and confirm no stale completions leaked.
    created = _invoke(runner, db, "create", "-n", "Other", "-p", "daily")
    assert created.exit_code == 0

    # Parse the freshly-assigned id from the CLI output.
    # Output format: "Created habit #<id>: Other (daily)"
    import re

    match = re.search(r"#(\d+)", created.stdout)
    assert match is not None
    new_id = match.group(1)

    result = _invoke(runner, db, "analyse", "longest-streak", "--habit", new_id)
    assert result.exit_code == 0
    assert "0" in result.stdout


# ---------------------------------------------------------------------------
# analyse longest-streak
# ---------------------------------------------------------------------------


def test_analyse_longest_streak_empty(runner, db):
    result = _invoke(runner, db, "analyse", "longest-streak")
    assert result.exit_code == 0
    assert "0" in result.stdout


def test_analyse_longest_streak_for_single_habit(runner, db):
    _invoke(runner, db, "create", "-n", "Water", "-p", "daily")
    for day in (1, 2, 3):
        _invoke(
            runner,
            db,
            "check-off",
            "--id",
            "1",
            "--when",
            f"2024-01-0{day}T09:00:00",
        )
    result = _invoke(runner, db, "analyse", "longest-streak", "--habit", "1")
    assert result.exit_code == 0
    assert "3" in result.stdout


def test_analyse_longest_streak_all_habits(runner, db):
    _invoke(runner, db, "create", "-n", "Short", "-p", "daily")
    _invoke(runner, db, "create", "-n", "Long", "-p", "daily")
    for day in (1, 2):
        _invoke(
            runner,
            db,
            "check-off",
            "--id",
            "1",
            "--when",
            f"2024-01-0{day}T09:00:00",
        )
    for day in (1, 2, 3, 4, 5):
        _invoke(
            runner,
            db,
            "check-off",
            "--id",
            "2",
            "--when",
            f"2024-01-0{day}T09:00:00",
        )
    result = _invoke(runner, db, "analyse", "longest-streak")
    assert result.exit_code == 0
    assert "5" in result.stdout


def test_analyse_longest_streak_missing_habit_exits_nonzero(runner, db):
    result = _invoke(runner, db, "analyse", "longest-streak", "--habit", "99")
    assert result.exit_code == 1


# ---------------------------------------------------------------------------
# analyse summary
# ---------------------------------------------------------------------------


def test_analyse_summary_empty(runner, db):
    result = _invoke(runner, db, "analyse", "summary")
    assert result.exit_code == 0
    assert "No habits" in result.stdout


def test_analyse_summary_lists_totals(runner, db):
    _invoke(runner, db, "create", "-n", "Water", "-p", "daily")
    _invoke(runner, db, "create", "-n", "Meditate", "-p", "daily")
    _invoke(runner, db, "create", "-n", "Review", "-p", "weekly")

    result = _invoke(runner, db, "analyse", "summary")
    assert result.exit_code == 0
    assert "Total habits: 3" in result.stdout
    assert "daily:  2" in result.stdout or "daily: 2" in result.stdout
    assert "weekly: 1" in result.stdout
    assert "Water" in result.stdout
    assert "Meditate" in result.stdout
    assert "Review" in result.stdout


# ---------------------------------------------------------------------------
# load-fixtures
# ---------------------------------------------------------------------------


def test_load_fixtures_creates_five_habits(runner, db):
    result = _invoke(runner, db, "load-fixtures")
    assert result.exit_code == 0
    assert "Fixtures loaded" in result.stdout

    listed = _invoke(runner, db, "list-habits")
    assert listed.stdout.count("#") == 5


def test_load_fixtures_then_analyse_longest_streak(runner, db):
    _invoke(runner, db, "load-fixtures")
    result = _invoke(runner, db, "analyse", "longest-streak")
    assert result.exit_code == 0
    assert "28" in result.stdout


# ---------------------------------------------------------------------------
# Persistence across invocations
# ---------------------------------------------------------------------------


def test_state_survives_between_invocations(runner, db):
    """Each ``_invoke`` call is a fresh process; data must persist."""
    _invoke(runner, db, "create", "-n", "Water", "-p", "daily")
    _invoke(runner, db, "check-off", "--id", "1", "--when", "2024-01-01T09:00:00")

    result = _invoke(runner, db, "list-habits")
    assert "Water" in result.stdout

    result = _invoke(runner, db, "analyse", "longest-streak", "--habit", "1")
    assert "1" in result.stdout


def test_databases_are_isolated(runner, tmp_path):
    """Two different --db paths must not share data."""
    db_a = str(tmp_path / "a.db")
    db_b = str(tmp_path / "b.db")

    _invoke(runner, db_a, "create", "-n", "In A", "-p", "daily")

    result = _invoke(runner, db_b, "list-habits")
    assert result.exit_code == 0
    assert "In A" not in result.stdout
