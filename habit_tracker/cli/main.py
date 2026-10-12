"""Typer-based CLI entry point.

Run with:
    habit --help
or, without installing:
    python -m habit_tracker.cli.main --help
"""

from __future__ import annotations

import os
from pathlib import Path

import typer

from habit_tracker.core.fixtures import load_fixtures
from habit_tracker.core.storage import Storage
from habit_tracker.core.tracker import HabitTracker

app = typer.Typer(
    name="habit",
    help="Habit tracking CLI — create, check off, and analyse habits.",
    no_args_is_help=True,
)


def _build_tracker(db_path: str) -> HabitTracker:
    storage = Storage(db_path=db_path)
    storage.init_schema()
    return HabitTracker(storage=storage)


@app.callback()
def main(
    db: str = typer.Option(
        os.environ.get("HABIT_DB", "habits.db"),
        "--db",
        help="Path to the SQLite database file.",
        envvar="HABIT_DB",
    ),
) -> None:
    """Global options for all `habit` commands."""
    # Store on a module-level object so subcommands can pick it up.
    # Typer does not pass the callback return value to subcommands,
    # so we stash it in a small singleton.
    _state.db = db


class _State:
    db: str = "habits.db"


_state = _State()


@app.command()
def create(
    name: str = typer.Option(..., "--name", "-n", help="Habit name."),
    description: str = typer.Option("", "--description", "-d", help="Habit description."),
    periodicity: str = typer.Option(
        ..., "--periodicity", "-p", help="'daily' or 'weekly'."
    ),
) -> None:
    """Create a new habit."""
    tracker = _build_tracker(_state.db)
    habit = tracker.create_habit(name=name, description=description, periodicity=periodicity)
    typer.echo(f"Created habit #{habit.habit_id}: {habit.name} ({habit.periodicity})")


@app.command()
def list_habits() -> None:
    """List all habits."""
    tracker = _build_tracker(_state.db)
    habits = tracker.all_habits()
    if not habits:
        typer.echo("No habits yet. Create one with `habit create`.")
        return
    for h in habits:
        typer.echo(f"#{h.habit_id}  {h.name}  [{h.periodicity}]  — {h.description}")


@app.command("load-fixtures")
def load_fixtures_cmd() -> None:
    """Load the 5 predefined habits + 4 weeks of tracking data."""
    tracker = _build_tracker(_state.db)
    load_fixtures(tracker)
    typer.echo("Fixtures loaded.")


@app.command()
def version() -> None:
    """Print the CLI version."""
    from habit_tracker import __version__

    typer.echo(f"habit-tracker {__version__}")


if __name__ == "__main__":
    app()