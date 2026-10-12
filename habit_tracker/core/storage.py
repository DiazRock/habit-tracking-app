"""Persistence stub for the SQLite backend.

The real implementation will arrive in a later iteration.
"""

from __future__ import annotations

from pathlib import Path


class Storage:
    """Placeholder storage layer.

    For now this only remembers the database path so the API and CLI can
    share the same instance. The schema initialisation and CRUD will be
    added in a subsequent iteration.
    """

    def __init__(self, db_path: str = "habits.db") -> None:
        self.db_path = Path(db_path)

    def init_schema(self) -> None:
        """Create tables if they do not exist yet (stub)."""
        # TODO: implement in the persistence iteration.
        ...