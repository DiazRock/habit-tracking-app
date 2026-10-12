"""Habit routes: /habits."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from habit_tracker.api.deps import get_tracker
from habit_tracker.api.schemas import HabitCreate, HabitOut
from habit_tracker.core.models import Habit
from habit_tracker.core.tracker import HabitTracker

router = APIRouter()


def _to_out(habit: Habit) -> HabitOut:
    return HabitOut(
        id=habit.habit_id,
        name=habit.name,
        description=habit.description,
        periodicity=habit.periodicity,
        created_at=habit.created_at,
    )


@router.get("", response_model=list[HabitOut])
def list_habits(tracker: HabitTracker = Depends(get_tracker)) -> list[HabitOut]:
    return [_to_out(h) for h in tracker.all_habits()]


@router.post("", response_model=HabitOut, status_code=status.HTTP_201_CREATED)
def create_habit(payload: HabitCreate, tracker: HabitTracker = Depends(get_tracker)) -> HabitOut:
    habit = tracker.create_habit(
        name=payload.name,
        description=payload.description,
        periodicity=payload.periodicity,
    )
    return _to_out(habit)


@router.get("/{habit_id}", response_model=HabitOut)
def get_habit(habit_id: int, tracker: HabitTracker = Depends(get_tracker)) -> HabitOut:
    try:
        return _to_out(tracker.get_habit(habit_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
