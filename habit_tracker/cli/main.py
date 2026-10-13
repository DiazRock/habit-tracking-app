"""Typer-based CLI entry point.

Run with:
    habit --help
or, without installing:
    python -m habit_tracker.cli.main --help
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Literal

import typer

from habit_tracker.core import analytics
from habit_tracker.core.fixtures import load_fixtures
from habit_tracker.core.models import Periodicity
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
    periodicity: Literal["daily", "weekly"] = typer.Option(
        ..., "--periodicity", "-p", help="'daily' or 'weekly'."
    ),
) -> None:
    """Create a new habit."""
    tracker = _build_tracker(_state.db)
    habit = tracker.create_habit(name=name, description=description, periodicity=periodicity)
    typer.echo(f"Created habit #{habit.habit_id}: {habit.name} ({habit.periodicity})")


@app.command("list-habits")
def list_habits(
    periodicity: Periodicity | None = typer.Option(None, "--periodicity", "-p"),
) -> None:
    tracker = _build_tracker(_state.db)
    habits = (
        analytics.list_habits_by_periodicity(tracker, periodicity)
        if periodicity
        else analytics.list_all_habits(tracker)
    )
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


@app.command()
def delete(habit_id: int = typer.Option(..., "--id", help="Habit id to delete.")) -> None:
    """Delete a habit and all its completions."""
    tracker = _build_tracker(_state.db)
    try:
        tracker.delete_habit(habit_id)
    except KeyError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from None
    typer.echo(f"Deleted habit #{habit_id}.")


@app.command("check-off")
def check_off(
    habit_id: int = typer.Option(..., "--id", help="Habit id."),
    when: str | None = typer.Option(None, "--when", help="ISO-8601 timestamp. Defaults to now."),
) -> None:
    """Record a completion for a habit."""
    tracker = _build_tracker(_state.db)

    parsed: datetime | None = None
    if when is not None:
        try:
            parsed = datetime.fromisoformat(when)
        except ValueError:
            typer.echo(f"Error: --when must be ISO-8601 (got {when!r})", err=True)
            raise typer.Exit(code=1) from None

    try:
        completion = tracker.check_off(habit_id, when=parsed)
    except KeyError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from None

    typer.echo(f"Checked off habit #{habit_id} at {completion.completed_at.isoformat()}")


analyse_app = typer.Typer(help="Analyse habits.")
app.add_typer(analyse_app, name="analyse")


@analyse_app.command("longest-streak")
def analyse_longest_streak(
    habit_id: int | None = typer.Option(None, "--habit", help="Limit to one habit."),
) -> None:
    """Show the longest streak overall or for a single habit."""
    tracker = _build_tracker(_state.db)
    if habit_id is None:
        typer.echo(f"Longest streak (all habits): {analytics.longest_streak_all(tracker)}")
        return
    try:
        streak = analytics.longest_streak_for_habit(tracker, habit_id)
    except KeyError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from None
    typer.echo(f"Longest streak for habit #{habit_id}: {streak}")


@analyse_app.command("summary")
def analyse_summary() -> None:
    """Print a one-screen overview of all tracked habits."""
    tracker = _build_tracker(_state.db)
    habits = analytics.list_all_habits(tracker)
    if not habits:
        typer.echo("No habits yet.")
        return
    typer.echo(f"Total habits: {len(habits)}")
    typer.echo(f"  daily:  {len(analytics.current_daily_habits(tracker))}")
    typer.echo(f"  weekly: {len(analytics.list_habits_by_periodicity(tracker, 'weekly'))}")
    typer.echo(f"Longest streak: {analytics.longest_streak_all(tracker)}")
    typer.echo("")
    typer.echo("Per habit:")
    for h in habits:
        streak = analytics.longest_streak_for_habit(tracker, h.habit_id)
        typer.echo(f"  #{h.habit_id}  {h.name:<20}  [{h.periodicity:<6}]  streak={streak}")


if __name__ == "__main__":
    app()
