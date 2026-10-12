"""Unit tests for the SQLite storage adapter."""

from __future__ import annotations

import sqlite3
from datetime import datetime

import pytest
from habit_tracker.core.models import Completion, Habit
from habit_tracker.core.storage import Storage

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def storage(tmp_path) -> Storage:
    """Fresh SQLite database per test, isolated in a temp directory."""
    s = Storage(db_path=tmp_path / "test.db")
    s.init_schema()
    yield s
    s.close()


def _habit(habit_id: int = 1, **overrides) -> Habit:
    """Build a valid Habit with sensible defaults, overriding as needed."""
    fields = dict[str, object] = {
        "name": "Drink water",
        "description": "2L per day",
        "periodicity": "daily",
        "habit_id": habit_id,
    }
    fields.update(overrides)
    return Habit(**fields)


def _completion(habit_id: int = 1, when: datetime | None = None) -> Completion:
    return Completion(
        habit_id=habit_id,
        completed_at=when or datetime(2024, 1, 1, 9, 0, 0),
    )


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


def test_init_schema_is_idempotent(tmp_path):
    s = Storage(db_path=tmp_path / "test.db")
    s.init_schema()
    s.init_schema()  # must not raise


def test_schema_creates_habits_and_completions_tables(storage):
    with storage._connect() as conn:  # noqa: SLF001
        names = {
            row["name"]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
    assert {"habits", "completions"} <= names


# ---------------------------------------------------------------------------
# Identity allocation
# ---------------------------------------------------------------------------


def test_next_habit_id_starts_at_one(storage):
    assert storage.next_habit_id() == 1


def test_next_habit_id_increments_after_save(storage):
    storage.save_habit(_habit(habit_id=1))
    assert storage.next_habit_id() == 2


def test_next_habit_id_uses_max_not_autoincrement(storage):
    # Simulate a gap: insert ids 1 and 5, expect next = 6.
    storage.save_habit(_habit(habit_id=1))
    storage.save_habit(_habit(habit_id=5, name="Other"))
    assert storage.next_habit_id() == 6


# ---------------------------------------------------------------------------
# save_habit / load_all_habits
# ---------------------------------------------------------------------------


def test_save_and_load_habit_round_trip(storage):
    original = _habit(
        habit_id=1,
        name="Meditate",
        description="10 minutes",
        periodicity="weekly",
    )
    storage.save_habit(original)

    loaded = storage.load_all_habits()
    assert len(loaded) == 1
    h = loaded[0]
    assert h.habit_id == original.habit_id
    assert h.name == "Meditate"
    assert h.description == "10 minutes"
    assert h.periodicity == "weekly"
    assert h.created_at.isoformat() == original.created_at.isoformat()


def test_save_habit_is_upsert(storage):
    storage.save_habit(_habit(habit_id=1, name="Original"))
    storage.save_habit(_habit(habit_id=1, name="Renamed"))

    loaded = storage.load_all_habits()
    assert len(loaded) == 1
    assert loaded[0].name == "Renamed"


def test_load_all_habits_returns_empty_list_initially(storage):
    assert storage.load_all_habits() == []


def test_load_all_habits_sorted_by_id(storage):
    for i in (3, 1, 2):
        storage.save_habit(_habit(habit_id=i, name=f"Habit {i}"))

    loaded = storage.load_all_habits()
    assert [h.habit_id for h in loaded] == [1, 2, 3]


def test_habits_are_isolated_by_storage_instance(tmp_path):
    db_a = tmp_path / "a.db"
    db_b = tmp_path / "b.db"

    a = Storage(db_path=db_a)
    a.init_schema()
    a.save_habit(_habit(habit_id=1, name="In A"))

    b = Storage(db_path=db_b)
    b.init_schema()
    assert b.load_all_habits() == []


# ---------------------------------------------------------------------------
# save_completion
# ---------------------------------------------------------------------------


def test_save_completion_attaches_to_habit(storage):
    storage.save_habit(_habit(habit_id=1))
    when = datetime(2024, 1, 15, 9, 30, 0)
    storage.save_completion(_completion(habit_id=1, when=when))

    loaded = storage.load_all_habits()
    assert len(loaded[0].completions) == 1
    assert loaded[0].completions[0].completed_at == when


def test_save_completion_returns_int_id(storage):
    storage.save_habit(_habit(habit_id=1))
    new_id = storage.save_completion(_completion(habit_id=1))
    assert isinstance(new_id, int)
    assert new_id >= 1


def test_save_completion_requires_habit_id(storage):
    storage.save_habit(_habit(habit_id=1))
    orphan = Completion(habit_id=None, completed_at=datetime(2024, 1, 1, 9, 0, 0))
    with pytest.raises(ValueError, match="habit_id must be set"):
        storage.save_completion(orphan)


def test_multiple_completions_preserved_in_chronological_order(storage):
    storage.save_habit(_habit(habit_id=1))
    for day in (1, 3, 2):  # intentionally out of order
        storage.save_completion(_completion(habit_id=1, when=datetime(2024, 1, day, 9, 0, 0)))

    loaded = storage.load_all_habits()
    days = [c.completed_at.day for c in loaded[0].completions]
    assert days == [1, 2, 3]


def test_completions_grouped_by_habit(storage):
    storage.save_habit(_habit(habit_id=1, name="A"))
    storage.save_habit(_habit(habit_id=2, name="B"))
    storage.save_completion(_completion(habit_id=1, when=datetime(2024, 1, 1, 9, 0)))
    storage.save_completion(_completion(habit_id=1, when=datetime(2024, 1, 2, 9, 0)))
    storage.save_completion(_completion(habit_id=2, when=datetime(2024, 1, 1, 9, 0)))

    loaded = {h.habit_id: h for h in storage.load_all_habits()}
    assert len(loaded[1].completions) == 2
    assert len(loaded[2].completions) == 1


def test_completions_are_not_duplicated_on_reload(storage):
    storage.save_habit(_habit(habit_id=1))
    storage.save_completion(_completion(habit_id=1))

    first = storage.load_all_habits()[0].completions
    second = storage.load_all_habits()[0].completions
    assert len(first) == 1
    assert len(second) == 1


# ---------------------------------------------------------------------------
# delete_habit and cascade
# ---------------------------------------------------------------------------


def test_delete_habit_removes_it(storage):
    storage.save_habit(_habit(habit_id=1))
    storage.delete_habit(1)
    assert storage.load_all_habits() == []


def test_delete_missing_habit_raises_keyerror(storage):
    with pytest.raises(KeyError, match="habit 42 not found"):
        storage.delete_habit(42)


def test_delete_habit_cascades_to_completions(storage):
    storage.save_habit(_habit(habit_id=1))
    storage.save_completion(_completion(habit_id=1, when=datetime(2024, 1, 1, 9, 0)))
    storage.save_completion(_completion(habit_id=1, when=datetime(2024, 1, 2, 9, 0)))

    storage.delete_habit(1)

    # If the FK pragma were off, completion rows would be orphaned.
    # This is a white-box check on the completions table.
    with storage._connect() as conn:  # noqa: SLF001
        orphan_count = conn.execute(
            "SELECT COUNT(*) AS n FROM completions WHERE habit_id = 1"
        ).fetchone()["n"]
    assert orphan_count == 0


def test_delete_habit_leaves_other_habits_untouched(storage):
    storage.save_habit(_habit(habit_id=1, name="Keep"))
    storage.save_habit(_habit(habit_id=2, name="Remove"))
    storage.save_completion(_completion(habit_id=1))
    storage.save_completion(_completion(habit_id=2))

    storage.delete_habit(2)

    loaded = storage.load_all_habits()
    assert len(loaded) == 1
    assert loaded[0].habit_id == 1
    assert len(loaded[0].completions) == 1


# ---------------------------------------------------------------------------
# Constraint enforcement
# ---------------------------------------------------------------------------


def test_periodicity_check_constraint_rejects_invalid_value(storage):
    with (
        storage._connect() as conn,  # noqa: SLF001
        pytest.raises(sqlite3.IntegrityError),
    ):
        conn.execute(
            "INSERT INTO habits "
            "(id, name, description, periodicity, created_at) "
            "VALUES (99, 'Bad', '', 'monthly', '2024-01-01T00:00:00')"
        )


def test_foreign_key_constraint_rejects_orphan_completion(storage):
    with (
        storage._connect() as conn,  # noqa: SLF001
        pytest.raises(sqlite3.IntegrityError),
    ):
        conn.execute(
            "INSERT INTO completions (habit_id, completed_at) "
            "VALUES (999, '2024-01-01T09:00:00')"
        )


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


def test_close_is_idempotent(storage):
    storage.close()
    storage.close()  # must not raise
