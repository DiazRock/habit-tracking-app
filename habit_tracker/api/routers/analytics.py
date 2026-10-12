"""Analytics routes: /analytics."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from habit_tracker.api.deps import get_tracker
from habit_tracker.api.schemas import HabitOut, StreakOut
from habit_tracker.core import analytics
from habit_tracker.core.tracker import HabitTracker

router = APIRouter()


@router.get("/habits", response_model=list[HabitOut])
def all_habits(
    periodicity: str | None = Query(None, pattern="^(daily|weekly)$"),
    tracker: HabitTracker = Depends(get_tracker),
) -> list[HabitOut]:
    habits = (
        analytics.list_habits_by_periodicity(tracker, periodicity)
        if periodicity
        else analytics.list_all_habits(tracker)
    )
    return [
        HabitOut(
            id=h.habit_id,
            name=h.name,
            description=h.description,
            periodicity=h.periodicity,
            created_at=h.created_at,
        )
        for h in habits
    ]


@router.get("/streaks/longest", response_model=StreakOut)
def longest_streak(
    tracker: HabitTracker = Depends(get_tracker),
) -> StreakOut:
    return StreakOut(longest_streak=analytics.longest_streak_all(tracker))


@router.get("/streaks/longest/{habit_id}", response_model=StreakOut)
def longest_streak_for_habit(
    habit_id: int, tracker: HabitTracker = Depends(get_tracker)
) -> StreakOut:
    return StreakOut(
        habit_id=habit_id,
        longest_streak=analytics.longest_streak_for_habit(tracker, habit_id),
    )