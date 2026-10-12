"""HabitTracker — orchestration layer for habits and completions."""

from __future__ import annotations

from datetime import datetime

from habit_tracker.core.models import Completion, Habit, Periodicity
from habit_tracker.core.storage import Storage


class HabitTracker:
    def __init__(self, storage: Storage) -> None:
        self._storage = storage

    def create_habit(self, name: str, description: str, periodicity: Periodicity) -> Habit:
        habit = Habit(
            name=name,
            description=description,
            periodicity=periodicity,
            habit_id=self._storage.next_habit_id(),
        )
        self._storage.save_habit(habit)
        return habit

    def delete_habit(self, habit_id: int) -> None:
        self._storage.delete_habit(habit_id)

    def check_off(self, habit_id: int, when: datetime | None = None) -> Completion:
        habit = self.get_habit(habit_id)  # raises if missing
        completion = habit.complete(when=when)
        self._storage.save_completion(completion)
        return completion

    def all_habits(self) -> list[Habit]:
        return self._storage.load_all_habits()

    def get_habit(self, habit_id: int) -> Habit:
        for h in self.all_habits():
            if h.habit_id == habit_id:
                return h
        raise KeyError(f"habit {habit_id} not found")
