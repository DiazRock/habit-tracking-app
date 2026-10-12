"""Smoke tests for the OOP core."""

from __future__ import annotations

import pytest
from habit_tracker.core.models import Habit

pytestmark = pytest.mark.unit


def test_create_habit_in_memory():
    h = Habit(name="Drink water", description="", periodicity="daily", habit_id=1)
    assert h.name == "Drink water"
    assert h.periodicity == "daily"
    assert h.completions == []


def test_habit_rejects_empty_name():
    with pytest.raises(ValueError, match="Habit name must not be empty"):
        Habit(name="   ", description="", periodicity="daily", habit_id=1)


def test_habit_rejects_invalid_periodicity():
    with pytest.raises(ValueError, match="periodicity must be 'daily' or 'weekly'"):
        Habit(name="x", description="", periodicity="monthly", habit_id=1)  # type: ignore[arg-type]
