"""Unit tests for the fixture loader."""

from __future__ import annotations

from datetime import date

import pytest
from habit_tracker.core import analytics
from habit_tracker.core.fixtures import load_fixtures
from habit_tracker.core.storage import Storage
from habit_tracker.core.tracker import HabitTracker

pytestmark = pytest.mark.unit


@pytest.fixture()
def tracker(tmp_path) -> HabitTracker:
    storage = Storage(db_path=tmp_path / "fixtures.db")
    storage.init_schema()
    yield HabitTracker(storage=storage)
    storage.close()


def test_load_fixtures_creates_five_habits(tracker):
    load_fixtures(tracker)
    assert len(tracker.all_habits()) == 5


def test_load_fixtures_includes_daily_and_weekly(tracker):
    load_fixtures(tracker)
    periodicities = {h.periodicity for h in tracker.all_habits()}
    assert periodicities == {"daily", "weekly"}


def test_load_fixtures_names_match_brief(tracker):
    load_fixtures(tracker)
    names = {h.name for h in tracker.all_habits()}
    assert names == {
        "Drink water",
        "Meditate",
        "Exercise",
        "Weekly review",
        "Call family",
    }


def test_load_fixtures_returns_created_habits(tracker):
    created = load_fixtures(tracker)
    assert len(created) == 5
    assert all(h.habit_id is not None for h in created)


def test_drink_water_has_28_day_streak(tracker):
    load_fixtures(tracker)
    habit = next(h for h in tracker.all_habits() if h.name == "Drink water")
    assert analytics.longest_streak_for_habit(tracker, habit.habit_id) == 28


def test_meditate_has_15_day_streak(tracker):
    load_fixtures(tracker)
    habit = next(h for h in tracker.all_habits() if h.name == "Meditate")
    assert analytics.longest_streak_for_habit(tracker, habit.habit_id) == 15


def test_exercise_has_4_day_streak(tracker):
    load_fixtures(tracker)
    habit = next(h for h in tracker.all_habits() if h.name == "Exercise")
    assert analytics.longest_streak_for_habit(tracker, habit.habit_id) == 4


def test_weekly_review_has_4_week_streak(tracker):
    load_fixtures(tracker)
    habit = next(h for h in tracker.all_habits() if h.name == "Weekly review")
    assert analytics.longest_streak_for_habit(tracker, habit.habit_id) == 4


def test_call_family_has_1_week_streak(tracker):
    load_fixtures(tracker)
    habit = next(h for h in tracker.all_habits() if h.name == "Call family")
    assert analytics.longest_streak_for_habit(tracker, habit.habit_id) == 1


def test_longest_streak_all_is_28(tracker):
    load_fixtures(tracker)
    assert analytics.longest_streak_all(tracker) == 28


def test_fixture_completions_span_four_weeks(tracker):
    load_fixtures(tracker)
    water = next(h for h in tracker.all_habits() if h.name == "Drink water")
    days = sorted({c.completed_at.date() for c in water.completions})
    assert days[0] == date(2024, 1, 1)
    assert days[-1] == date(2024, 1, 28)
    assert len(days) == 28
