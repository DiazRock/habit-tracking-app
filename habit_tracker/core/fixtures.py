"""Fixture loader: 5 predefined habits with 4 weeks of tracking data.

The fixture is fully deterministic so tests can assert exact streak
counts. Anchor date is 2024-01-01 (a Monday), giving exactly 4 ISO weeks
of coverage through 2024-01-28.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from habit_tracker.core.models import Completion, Habit, Periodicity
from habit_tracker.core.tracker import HabitTracker

_ANCHOR = date(2024, 1, 1)  # Monday
_DAYS = 28  # 4 full weeks
_COMPLETION_HOUR = 9


def _at(day_offset: int) -> datetime:
    """Return the fixture timestamp for the Nth day after the anchor."""
    return datetime.combine(
        _ANCHOR + timedelta(days=day_offset),
        time(hour=_COMPLETION_HOUR),
    )


# ---------------------------------------------------------------------------
# Per-habit completion patterns
# ---------------------------------------------------------------------------


def _drink_water_days() -> list[int]:
    """Perfect 28-day streak."""
    return list(range(_DAYS))


def _meditate_days() -> list[int]:
    """10 days, then a 3-day break, then 15 more."""
    return list(range(10)) + list(range(13, _DAYS))


def _exercise_days() -> list[int]:
    """4 days on, 3 days off, repeated."""
    return [d for d in range(_DAYS) if d % 7 < 4]


def _weekly_review_days() -> list[int]:
    """Completed every week (Mondays)."""
    return [0, 7, 14, 21]


def _call_family_days() -> list[int]:
    """Completed only weeks 1 and 3."""
    return [0, 14]


_FIXTURE_DEFINITIONS: list[tuple[str, str, Periodicity, list[int]]] = [
    ("Drink water", "Drink 2L of water", "daily", _drink_water_days()),
    ("Meditate", "10 minutes of meditation", "daily", _meditate_days()),
    ("Exercise", "30 minutes of exercise", "daily", _exercise_days()),
    ("Weekly review", "Review goals for the week", "weekly", _weekly_review_days()),
    ("Call family", "Call parents", "weekly", _call_family_days()),
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_fixtures(tracker: HabitTracker) -> list[Habit]:
    """Insert the 5 predefined habits and their completions.

    Idempotent per fresh database: habits are created via the tracker
    (which allocates fresh ids), and completions are saved through the
    tracker's storage. If called on a database that already contains
    habits, additional rows are appended — callers that need a clean
    slate should use a fresh database file.

    Returns the list of created habits in insertion order.
    """
    created: list[Habit] = []

    for name, description, periodicity, day_offsets in _FIXTURE_DEFINITIONS:
        habit = tracker.create_habit(name, description, periodicity)
        for offset in day_offsets:
            when = _at(offset)
            completion = Completion(habit_id=habit.habit_id, completed_at=when)
            tracker._storage.save_completion(completion)  # noqa: SLF001
            habit.completions.append(completion)
        created.append(habit)

    return created
