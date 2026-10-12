"""Functional analytics over habits.

Every function here is pure: it never mutates its inputs and returns a new
value. This module must not import FastAPI, Typer, or any framework.
"""

from __future__ import annotations

from habit_tracker.core.models import Habit
from habit_tracker.core.tracker import HabitTracker


def list_all_habits(tracker: HabitTracker) -> list[Habit]:
    return tracker.all_habits()


def list_habits_by_periodicity(
    tracker: HabitTracker, periodicity: str
) -> list[Habit]:
    return [h for h in tracker.all_habits() if h.periodicity == periodicity]


def longest_streak_all(tracker: HabitTracker) -> int:
    # TODO: implement streak logic in the analytics iteration.
    return 0


def longest_streak_for_habit(tracker: HabitTracker, habit_id: int) -> int:
    # TODO: implement streak logic in the analytics iteration.
    return 0