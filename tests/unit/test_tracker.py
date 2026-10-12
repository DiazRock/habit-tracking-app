"""Unit tests for the HabitTracker orchestrator.

These tests exercise HabitTracker against a real, isolated SQLite storage
backed by a tmp_path. They stay fast because Storage is only a thin SQLite
wrapper; no HTTP or CLI is involved.
"""

from __future__ import annotations

from datetime import datetime

import pytest
from habit_tracker.core.storage import Storage
from habit_tracker.core.tracker import HabitTracker

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tracker(tmp_path) -> HabitTracker:
    storage = Storage(db_path=tmp_path / "tracker.db")
    storage.init_schema()
    yield HabitTracker(storage=storage)
    storage.close()


# ---------------------------------------------------------------------------
# create_habit
# ---------------------------------------------------------------------------


def test_create_habit_returns_habit_with_assigned_id(tracker):
    habit = tracker.create_habit("Drink water", "2L per day", "daily")
    assert habit.habit_id == 1
    assert habit.name == "Drink water"
    assert habit.description == "2L per day"
    assert habit.periodicity == "daily"
    assert habit.completions == []


def test_create_habit_assigns_monotonic_ids(tracker):
    h1 = tracker.create_habit("A", "", "daily")
    h2 = tracker.create_habit("B", "", "weekly")
    h3 = tracker.create_habit("C", "", "daily")
    assert [h1.habit_id, h2.habit_id, h3.habit_id] == [1, 2, 3]


def test_create_habit_persists_immediately(tracker):
    tracker.create_habit("Persisted", "", "daily")
    # Reload from storage independently to prove persistence.
    reloaded = tracker.all_habits()
    assert len(reloaded) == 1
    assert reloaded[0].name == "Persisted"


def test_create_habit_rejects_empty_name(tracker):
    with pytest.raises(ValueError, match="Habit name must not be empty"):
        tracker.create_habit("   ", "", "daily")


def test_create_habit_rejects_invalid_periodicity(tracker):
    with pytest.raises(ValueError, match="periodicity must be 'daily' or 'weekly'"):
        tracker.create_habit("Bad", "", "monthly")


def test_create_habit_accepts_both_supported_periodicities(tracker):
    tracker.create_habit("Daily", "", "daily")
    tracker.create_habit("Weekly", "", "weekly")
    habits = tracker.all_habits()
    assert {h.periodicity for h in habits} == {"daily", "weekly"}


# ---------------------------------------------------------------------------
# all_habits / get_habit
# ---------------------------------------------------------------------------


def test_all_habits_empty_when_none_created(tracker):
    assert tracker.all_habits() == []


def test_all_habits_returns_creation_order(tracker):
    for name in ("A", "B", "C"):
        tracker.create_habit(name, "", "daily")
    assert [h.name for h in tracker.all_habits()] == ["A", "B", "C"]


def test_get_habit_returns_matching_habit(tracker):
    tracker.create_habit("A", "", "daily")
    b = tracker.create_habit("B", "", "weekly")
    assert tracker.get_habit(b.habit_id).name == "B"


def test_get_habit_raises_for_missing_id(tracker):
    with pytest.raises(KeyError, match="habit 99 not found"):
        tracker.get_habit(99)


# ---------------------------------------------------------------------------
# check_off
# ---------------------------------------------------------------------------


def test_check_off_records_completion(tracker):
    h = tracker.create_habit("Water", "", "daily")
    when = datetime(2024, 1, 15, 9, 0, 0)
    completion = tracker.check_off(h.habit_id, when=when)
    assert completion.habit_id == h.habit_id
    assert completion.completed_at == when


def test_check_off_defaults_to_now(tracker):
    h = tracker.create_habit("Water", "", "daily")
    before = datetime.now()
    completion = tracker.check_off(h.habit_id)
    after = datetime.now()
    assert before <= completion.completed_at <= after


def test_check_off_is_visible_on_next_read(tracker):
    h = tracker.create_habit("Water", "", "daily")
    tracker.check_off(h.habit_id, when=datetime(2024, 1, 1, 9, 0))
    tracker.check_off(h.habit_id, when=datetime(2024, 1, 2, 9, 0))

    reloaded = tracker.get_habit(h.habit_id)
    assert len(reloaded.completions) == 2


def test_check_off_raises_for_missing_habit(tracker):
    with pytest.raises(KeyError, match="habit 42 not found"):
        tracker.check_off(42)


def test_check_off_same_day_twice_records_both(tracker):
    h = tracker.create_habit("Water", "", "daily")
    when = datetime(2024, 1, 1, 9, 0)
    tracker.check_off(h.habit_id, when=when)
    tracker.check_off(h.habit_id, when=when)
    reloaded = tracker.get_habit(h.habit_id)
    # Storage is append-only; analytics collapses by period.
    assert len(reloaded.completions) == 2


# ---------------------------------------------------------------------------
# delete_habit
# ---------------------------------------------------------------------------


def test_delete_habit_removes_it(tracker):
    h = tracker.create_habit("Water", "", "daily")
    tracker.delete_habit(h.habit_id)
    assert tracker.all_habits() == []


def test_delete_habit_removes_completions(tracker):
    h = tracker.create_habit("Water", "", "daily")
    tracker.check_off(h.habit_id, when=datetime(2024, 1, 1, 9, 0))
    tracker.delete_habit(h.habit_id)

    # Recreate a habit to force a new id and confirm the old completions
    # didn't leak into the new row.
    h2 = tracker.create_habit("Other", "", "daily")
    assert tracker.get_habit(h2.habit_id).completions == []


def test_delete_habit_raises_for_missing_id(tracker):
    with pytest.raises(KeyError, match="habit 42 not found"):
        tracker.delete_habit(42)


# ---------------------------------------------------------------------------
# Persistence across tracker instances
# ---------------------------------------------------------------------------


def test_state_survives_new_tracker_instance(tmp_path):
    db = tmp_path / "shared.db"

    s1 = Storage(db_path=db)
    s1.init_schema()
    t1 = HabitTracker(storage=s1)
    h = t1.create_habit("Persisted", "across instances", "daily")
    t1.check_off(h.habit_id, when=datetime(2024, 1, 1, 9, 0))
    s1.close()

    s2 = Storage(db_path=db)
    s2.init_schema()
    t2 = HabitTracker(storage=s2)
    reloaded = t2.all_habits()
    assert len(reloaded) == 1
    assert reloaded[0].name == "Persisted"
    assert len(reloaded[0].completions) == 1
    s2.close()
