"""FastAPI dependency providers."""

from __future__ import annotations

import os

from fastapi import Request

from habit_tracker.core.storage import Storage
from habit_tracker.core.tracker import HabitTracker


def build_tracker() -> HabitTracker:
    """Create the shared HabitTracker instance for the API process."""
    db_path = os.environ.get("HABIT_DB", "habits.db")
    storage = Storage(db_path=db_path)
    storage.init_schema()
    return HabitTracker(storage=storage)


def get_tracker(request: Request) -> HabitTracker:
    """FastAPI dependency that returns the app-scoped tracker."""
    return request.app.state.tracker
