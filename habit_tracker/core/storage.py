"""SQLite persistence adapter for the habit tracking app.

This module is the *only* place in the codebase that speaks SQL. Every other
module works with :class:`~habit_tracker.core.models.Habit` and
:class:`~habit_tracker.core.models.Completion` objects.

Design notes
------------
* No framework imports. The storage layer must not know about FastAPI,
  Typer, Pydantic, or anything outside the standard library.
* Connections are opened per operation and closed immediately. SQLite
  connections are not thread-safe by default, and short-lived connections
  are simpler to reason about. The performance cost is negligible at this
  project's scale.
* ``PRAGMA foreign_keys = ON`` must be issued on **every** connection —
  SQLite defaults the pragma to OFF, which would silently disable the
  ``ON DELETE CASCADE`` on the ``completions`` table.
* Datetimes are stored as ISO 8601 strings and parsed back with
  ``datetime.fromisoformat``. The application uses naive local time
  consistently; no timezone handling is attempted.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from habit_tracker.core.models import Completion, Habit

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS habits (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT    NOT NULL,
    description  TEXT    NOT NULL DEFAULT '',
    periodicity  TEXT    NOT NULL CHECK (periodicity IN ('daily','weekly')),
    created_at   TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS completions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    habit_id     INTEGER NOT NULL,
    completed_at TEXT    NOT NULL,
    FOREIGN KEY (habit_id) REFERENCES habits(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_completions_habit
    ON completions(habit_id, completed_at);
"""


class Storage:
    """SQLite-backed repository for habits and completions.

    The class exposes a collection-like interface over the durable store.
    Every method that mutates state returns either the assigned id or
    ``None``; every method that reads state returns domain objects, never
    raw rows.
    """

    def __init__(self, db_path: str | Path = "habits.db") -> None:
        """Record the location of the SQLite database.

        No connection is opened here. Call :meth:`init_schema` before using
        any other method to ensure the tables exist.

        Parameters
        ----------
        db_path:
            Path to the SQLite file. Accepts ``str`` or :class:`pathlib.Path`.
        """
        self.db_path = Path(db_path)

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        """Yield a configured connection and commit on clean exit.

        Enables the foreign-keys pragma, wraps the block in a transaction,
        commits on success, and rolls back automatically on exception.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def close(self) -> None:
        """Release resources.

        Connections are opened per operation, so this method is currently a
        no-op. It exists so that callers (test suites, FastAPI shutdown
        hooks, CLI exit handlers) have a stable lifecycle hook to invoke if
        the implementation later holds a persistent connection.
        """
        # No persistent connection to close today.

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def init_schema(self) -> None:
        """Create tables and indices if they do not yet exist.

        Idempotent: safe to call on every process start.
        """
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    # ------------------------------------------------------------------
    # Habit CRUD
    # ------------------------------------------------------------------

    def next_habit_id(self) -> int:
        """Return the next available habit id.

        Uses ``MAX(id) + 1`` rather than ``AUTOINCREMENT``'s internal
        counter so the value is available *before* the insert. The caller
        (``HabitTracker.create_habit``) needs the id to build a ``Habit``
        whose ``habit_id`` field is non-optional.

        .. note::
           In a multi-writer environment this can race. The application is
           single-process, so the race does not occur in practice.
        """
        with self._connect() as conn:
            row = conn.execute("SELECT COALESCE(MAX(id), 0) AS max_id FROM habits").fetchone()
        return int(row["max_id"]) + 1

    def save_habit(self, habit: Habit) -> int:
        """Insert or update a habit row, returning its id.

        Uses ``INSERT ... ON CONFLICT(id) DO UPDATE`` so the method is
        idempotent: running it twice with the same input has the same
        effect as running it once.
        """
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO habits (id, name, description, periodicity, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name        = excluded.name,
                    description = excluded.description,
                    periodicity = excluded.periodicity,
                    created_at  = excluded.created_at
                """,
                (
                    habit.habit_id,
                    habit.name,
                    habit.description,
                    habit.periodicity,
                    habit.created_at.isoformat(),
                ),
            )
        return habit.habit_id

    def delete_habit(self, habit_id: int) -> None:
        """Delete a habit and (via cascade) its completions.

        Raises
        ------
        KeyError
            If no habit with the given id exists.
        """
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM habits WHERE id = ?", (habit_id,))
            if cursor.rowcount == 0:
                raise KeyError(f"habit {habit_id} not found")

    # ------------------------------------------------------------------
    # Completion CRUD
    # ------------------------------------------------------------------

    def save_completion(self, completion: Completion) -> int:
        """Insert a completion row, returning its new id.

        Completions are append-only. A check-off at the same timestamp as
        an earlier one creates a second row; the analytics layer treats any
        day with at least one completion as "completed".
        """
        if completion.habit_id is None:
            raise ValueError("completion.habit_id must be set before saving")

        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO completions (habit_id, completed_at)
                VALUES (?, ?)
                """,
                (completion.habit_id, completion.completed_at.isoformat()),
            )
            new_id = cursor.lastrowid
            if new_id is None:
                raise RuntimeError("failed to insert completion")
            return new_id

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def load_all_habits(self) -> list[Habit]:
        """Return every habit with its completions attached.

        Issues exactly two queries — one for habits, one for completions —
        and groups them in memory. Never issue one query per habit: that is
        the classic N+1 anti-pattern.
        """
        with self._connect() as conn:
            habit_rows = conn.execute(
                """
                SELECT id, name, description, periodicity, created_at
                FROM habits
                ORDER BY id
                """
            ).fetchall()
            completion_rows = conn.execute(
                """
                SELECT habit_id, completed_at
                FROM completions
                ORDER BY habit_id, completed_at
                """
            ).fetchall()

        # Group completions by habit_id.
        completions_by_habit: dict[int, list[Completion]] = {}
        for row in completion_rows:
            habit_id = int(row["habit_id"])
            completions_by_habit.setdefault(habit_id, []).append(
                Completion(
                    habit_id=habit_id,
                    completed_at=datetime.fromisoformat(row["completed_at"]),
                )
            )

        habits: list[Habit] = []
        for row in habit_rows:
            habit_id = int(row["id"])
            habits.append(
                Habit(
                    name=row["name"],
                    description=row["description"],
                    periodicity=row["periodicity"],
                    habit_id=habit_id,
                    created_at=datetime.fromisoformat(row["created_at"]),
                    completions=completions_by_habit.get(habit_id, []),
                )
            )
        return habits


__all__ = ["Storage"]
