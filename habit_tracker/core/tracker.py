"""HabitTracker — orchestration layer for habits and completions."""

from __future__ import annotations

from habit_tracker.core.models import Habit
from habit_tracker.core.storage import Storage


class HabitTracker:
    """High-level API used by both the CLI and the REST API.

    All methods must be framework-agnostic. The adapters (CLI, FastAPI)
    only translate between their wire format and these method calls.
    """

    def __init__(self, storage: Storage) -> None:
        self._storage = storage
        self._habits: dict[int, Habit] = {}
        self._next_id: int = 1

    def create_habit(self, name: str, description: str, periodicity: str) -> Habit:
        habit = Habit(
            name=name,
            description=description,
            periodicity=periodicity,  # type: ignore[arg-type]
            habit_id=self._next_id,
        )
        self._habits[habit.habit_id] = habit
        self._next_id += 1
        return habit

    def all_habits(self) -> list[Habit]:
        return list(self._habits.values())

    def get_habit(self, habit_id: int) -> Habit:
        try:
            return self._habits[habit_id]
        except KeyError as exc:
            raise KeyError(f"habit {habit_id} not found") from exc
