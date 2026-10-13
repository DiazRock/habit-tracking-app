"""Functional analytics over habits.

Every function in this module is *pure*: it takes its inputs and returns a
new value without mutating anything. No global state, no side effects, no
framework imports. This is the functional-programming half of the brief's
"OOP for habits, FP for analytics" mandate.

Design notes
------------
* Streaks are computed with :func:`functools.reduce` over a sorted,
  deduplicated sequence of periods (dates for daily habits, ISO weeks for
  weekly habits).
* A "period" is an atomic unit of time: one day for daily habits, one
  ISO week for weekly habits. A habit is considered completed within a
  period if at least one completion falls in that period.
* The algorithms treat inputs as immutable: no ``list.append`` on caller
  data, no in-place sorts.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import date, datetime, timedelta
from functools import reduce
from typing import TypeAlias

from habit_tracker.core.models import Habit
from habit_tracker.core.tracker import HabitTracker

# ---------------------------------------------------------------------------
# Period abstraction
# ---------------------------------------------------------------------------

PeriodKey: TypeAlias = date | tuple[int, int]


def _day_key(when: datetime) -> date:
    """Reduce a completion timestamp to its calendar day."""
    return when.date()


def _week_key(when: datetime) -> tuple[int, int]:
    """Reduce a completion timestamp to its ISO (year, week)."""
    iso = when.isocalendar()
    return (iso.year, iso.week)


def _key_fn(periodicity: str) -> Callable[[datetime], PeriodKey]:
    """Return the period-bucketing function for a given periodicity."""
    if periodicity == "daily":
        return _day_key
    if periodicity == "weekly":
        return _week_key
    raise ValueError(f"unsupported periodicity: {periodicity!r}")


def _consecutive(current: PeriodKey, previous: PeriodKey) -> bool:
    """Return True if ``current`` immediately follows ``previous``."""
    if isinstance(current, date) and isinstance(previous, date):
        return current - previous == timedelta(days=1)
    if isinstance(current, tuple) and isinstance(previous, tuple):
        # ISO weeks: compare as Monday-anchored dates.
        cy, cw = current
        py, pw = previous
        c_monday = date.fromisocalendar(cy, cw, 1)
        p_monday = date.fromisocalendar(py, pw, 1)
        return c_monday - p_monday == timedelta(weeks=1)
    return False


# ---------------------------------------------------------------------------
# Streak computation
# ---------------------------------------------------------------------------


def _longest_streak_from_keys(keys: Iterable[PeriodKey]) -> int:
    """Compute the longest consecutive run in an iterable of period keys.

    Pure function. Deduplicates and sorts the input, then reduces over it
    tracking the current run length and the best seen so far.
    """
    distinct_sorted = sorted(set(keys))

    if not distinct_sorted:
        return 0

    def step(
        state: tuple[int, int, PeriodKey | None],
        current: PeriodKey,
    ) -> tuple[int, int, PeriodKey | None]:
        current_run, best_run, previous = state
        if previous is None or _consecutive(current, previous):
            current_run += 1
        else:
            current_run = 1
        return (current_run, max(best_run, current_run), current)

    initial: tuple[int, int, PeriodKey | None] = (0, 0, None)
    _, best, _ = reduce(step, distinct_sorted, initial)
    return best


def _habit_longest_streak(habit: Habit) -> int:
    """Longest streak for a single habit, in its own periodicity."""
    key = _key_fn(habit.periodicity)
    keys = (key(c.completed_at) for c in habit.completions)
    return _longest_streak_from_keys(keys)


# ---------------------------------------------------------------------------
# Public API — required by the brief
# ---------------------------------------------------------------------------


def list_all_habits(tracker: HabitTracker) -> list[Habit]:
    """Return every currently tracked habit."""
    return list(tracker.all_habits())


def list_habits_by_periodicity(tracker: HabitTracker, periodicity: str) -> list[Habit]:
    """Return all habits whose periodicity matches ``periodicity``."""
    return list(filter(lambda h: h.periodicity == periodicity, tracker.all_habits()))


def longest_streak_all(tracker: HabitTracker) -> int:
    """Return the longest streak across all defined habits."""
    return max(
        (map(_habit_longest_streak, tracker.all_habits())),
        default=0,
    )


def longest_streak_for_habit(tracker: HabitTracker, habit_id: int) -> int:
    """Return the longest streak for a single habit.

    Raises
    ------
    KeyError
        If no habit with the given id exists.
    """
    habit = tracker.get_habit(habit_id)  # raises KeyError if missing
    return _habit_longest_streak(habit)


# ---------------------------------------------------------------------------
# Public API — extras suggested by the brief
# ---------------------------------------------------------------------------


def current_daily_habits(tracker: HabitTracker) -> list[Habit]:
    """Return all habits with ``periodicity == 'daily'``."""
    return list_habits_by_periodicity(tracker, "daily")


def struggled_most_last_month(tracker: HabitTracker) -> list[Habit]:
    """Return habits sorted by fewest completions in the last 30 days.

    Habits with no completions in the window come first. Ties are broken
    by habit name for a stable ordering.
    """
    today = datetime.now().date()
    cutoff = today - timedelta(days=30)

    def count_recent(habit: Habit) -> int:
        return sum(1 for c in habit.completions if c.completed_at.date() >= cutoff)

    return sorted(
        tracker.all_habits(),
        key=lambda h: (count_recent(h), h.name),
    )
