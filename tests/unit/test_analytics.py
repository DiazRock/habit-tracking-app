"""Unit tests for the functional analytics module.

These tests construct habits with known completion patterns directly in
an isolated SQLite-backed tracker, then assert on the returned values.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest
from habit_tracker.core import analytics
from habit_tracker.core.models import Completion, Habit
from habit_tracker.core.storage import Storage
from habit_tracker.core.tracker import HabitTracker

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tracker(tmp_path) -> HabitTracker:
    storage = Storage(db_path=tmp_path / "analytics.db")
    storage.init_schema()
    yield HabitTracker(storage=storage)
    storage.close()


def _seed(
    tracker: HabitTracker,
    name: str,
    periodicity: str,
    completions: list[datetime],
) -> Habit:
    """Create a habit and pre-load its completions into storage."""
    habit = tracker.create_habit(name, "", periodicity)
    for when in completions:
        tracker._storage.save_completion(  # noqa: SLF001
            Completion(habit_id=habit.habit_id, completed_at=when)
        )
    return habit


def _days(start: date, offsets: list[int]) -> list[datetime]:
    return [datetime.combine(start + timedelta(days=d), datetime.min.time()) for d in offsets]


# ---------------------------------------------------------------------------
# list_all_habits
# ---------------------------------------------------------------------------


def test_list_all_habits_empty(tracker):
    assert analytics.list_all_habits(tracker) == []


def test_list_all_habits_returns_everything(tracker):
    tracker.create_habit("A", "", "daily")
    tracker.create_habit("B", "", "weekly")
    tracker.create_habit("C", "", "daily")

    result = analytics.list_all_habits(tracker)
    assert [h.name for h in result] == ["A", "B", "C"]


def test_list_all_habits_is_a_new_list(tracker):
    tracker.create_habit("A", "", "daily")
    result = analytics.list_all_habits(tracker)
    result.append("sentinel")  # must not affect the tracker
    assert len(analytics.list_all_habits(tracker)) == 1


# ---------------------------------------------------------------------------
# list_habits_by_periodicity
# ---------------------------------------------------------------------------


def test_list_by_periodicity_filters(tracker):
    tracker.create_habit("D1", "", "daily")
    tracker.create_habit("W1", "", "weekly")
    tracker.create_habit("D2", "", "daily")

    daily = analytics.list_habits_by_periodicity(tracker, "daily")
    weekly = analytics.list_habits_by_periodicity(tracker, "weekly")

    assert [h.name for h in daily] == ["D1", "D2"]
    assert [h.name for h in weekly] == ["W1"]


def test_list_by_periodicity_empty_when_no_match(tracker):
    tracker.create_habit("D1", "", "daily")
    assert analytics.list_habits_by_periodicity(tracker, "weekly") == []


def test_current_daily_habits_is_alias(tracker):
    tracker.create_habit("D1", "", "daily")
    tracker.create_habit("W1", "", "weekly")
    assert [h.name for h in analytics.current_daily_habits(tracker)] == ["D1"]


# ---------------------------------------------------------------------------
# longest_streak_all
# ---------------------------------------------------------------------------


def test_longest_streak_all_zero_when_empty(tracker):
    assert analytics.longest_streak_all(tracker) == 0


def test_longest_streak_all_zero_when_no_completions(tracker):
    tracker.create_habit("A", "", "daily")
    assert analytics.longest_streak_all(tracker) == 0


def test_longest_streak_all_returns_max_across_habits(tracker):
    start = date(2024, 1, 1)
    _seed(tracker, "Short", "daily", _days(start, [0, 1]))
    _seed(tracker, "Long", "daily", _days(start, [0, 1, 2, 3, 4]))
    assert analytics.longest_streak_all(tracker) == 5


def test_longest_streak_all_single_habit(tracker):
    start = date(2024, 1, 1)
    _seed(tracker, "Only", "daily", _days(start, [0, 1, 2]))
    assert analytics.longest_streak_all(tracker) == 3


# ---------------------------------------------------------------------------
# longest_streak_for_habit
# ---------------------------------------------------------------------------


def test_longest_streak_for_habit_empty_completions(tracker):
    h = tracker.create_habit("A", "", "daily")
    assert analytics.longest_streak_for_habit(tracker, h.habit_id) == 0


def test_longest_streak_for_habit_single_completion(tracker):
    start = date(2024, 1, 1)
    h = _seed(tracker, "A", "daily", _days(start, [0]))
    assert analytics.longest_streak_for_habit(tracker, h.habit_id) == 1


def test_longest_streak_for_habit_perfect_run(tracker):
    start = date(2024, 1, 1)
    h = _seed(tracker, "A", "daily", _days(start, list(range(14))))
    assert analytics.longest_streak_for_habit(tracker, h.habit_id) == 14


def test_longest_streak_for_habit_with_break(tracker):
    start = date(2024, 1, 1)
    # Days 0..4, gap at 5..6, days 7..10. Longest = 5.
    h = _seed(tracker, "A", "daily", _days(start, [0, 1, 2, 3, 4, 7, 8, 9, 10]))
    assert analytics.longest_streak_for_habit(tracker, h.habit_id) == 5


def test_longest_streak_for_habit_multiple_breaks(tracker):
    start = date(2024, 1, 1)
    # 2, gap, 3, gap, 4 → longest = 4.
    h = _seed(tracker, "A", "daily", _days(start, [0, 1, 3, 4, 5, 7, 8, 9, 10]))
    assert analytics.longest_streak_for_habit(tracker, h.habit_id) == 4


def test_longest_streak_for_habit_duplicate_completions_same_day(tracker):
    _ = date(2024, 1, 1)
    d0 = datetime(2024, 1, 1, 9, 0)
    d0_later = datetime(2024, 1, 1, 18, 0)
    d1 = datetime(2024, 1, 2, 9, 0)
    h = _seed(tracker, "A", "daily", [d0, d0_later, d1])
    # Two completions on the same day still count as one period.
    assert analytics.longest_streak_for_habit(tracker, h.habit_id) == 2


def test_longest_streak_for_habit_missing_id_raises(tracker):
    with pytest.raises(KeyError, match="habit 99 not found"):
        analytics.longest_streak_for_habit(tracker, 99)


# ---------------------------------------------------------------------------
# Weekly habits (ISO week bucketing)
# ---------------------------------------------------------------------------


def test_longest_streak_weekly_consecutive_weeks(tracker):
    # Mondays of four consecutive ISO weeks.
    completions = [
        datetime(2024, 1, 1, 9, 0),  # week 1
        datetime(2024, 1, 8, 9, 0),  # week 2
        datetime(2024, 1, 15, 9, 0),  # week 3
        datetime(2024, 1, 22, 9, 0),  # week 4
    ]
    h = _seed(tracker, "Weekly", "weekly", completions)
    assert analytics.longest_streak_for_habit(tracker, h.habit_id) == 4


def test_longest_streak_weekly_same_week_counts_once(tracker):
    completions = [
        datetime(2024, 1, 1, 9, 0),  # Monday, week 1
        datetime(2024, 1, 3, 9, 0),  # Wednesday, same week
        datetime(2024, 1, 5, 9, 0),  # Friday, same week
    ]
    h = _seed(tracker, "Weekly", "weekly", completions)
    assert analytics.longest_streak_for_habit(tracker, h.habit_id) == 1


def test_longest_streak_weekly_with_gap(tracker):
    completions = [
        datetime(2024, 1, 1, 9, 0),  # week 1
        datetime(2024, 1, 8, 9, 0),  # week 2
        # week 3 missing
        datetime(2024, 1, 22, 9, 0),  # week 4
    ]
    h = _seed(tracker, "Weekly", "weekly", completions)
    assert analytics.longest_streak_for_habit(tracker, h.habit_id) == 2


# ---------------------------------------------------------------------------
# struggled_most_last_month
# ---------------------------------------------------------------------------


def test_struggled_most_last_month_empty(tracker):
    assert analytics.struggled_most_last_month(tracker) == []


def test_struggled_most_last_month_orders_by_fewest_recent(tracker):
    now = datetime.now()
    _seed(tracker, "Many", "daily", [now - timedelta(days=i) for i in range(10)])
    _seed(tracker, "Few", "daily", [now - timedelta(days=1)])
    _seed(tracker, "None", "daily", [])

    result = analytics.struggled_most_last_month(tracker)
    assert [h.name for h in result] == ["None", "Few", "Many"]


def test_struggled_most_last_month_ignores_old_completions(tracker):
    now = datetime.now()
    _seed(tracker, "Old", "daily", [now - timedelta(days=90)])
    _seed(tracker, "Recent", "daily", [now - timedelta(days=1)])

    result = analytics.struggled_most_last_month(tracker)
    # "Old" has zero recent completions, so it comes first.
    assert [h.name for h in result] == ["Old", "Recent"]


# ---------------------------------------------------------------------------
# Purity checks
# ---------------------------------------------------------------------------


def test_analytics_does_not_mutate_tracker(tracker):
    start = date(2024, 1, 1)
    _seed(tracker, "A", "daily", _days(start, [0, 1, 2]))

    before = [(h.name, len(h.completions)) for h in tracker.all_habits()]

    analytics.list_all_habits(tracker)
    analytics.list_habits_by_periodicity(tracker, "daily")
    analytics.longest_streak_all(tracker)
    analytics.struggled_most_last_month(tracker)

    after = [(h.name, len(h.completions)) for h in tracker.all_habits()]
    assert before == after
