"""Domain models for the habit tracking app.

This module must not import FastAPI, Typer, or any other framework.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

Periodicity = Literal["daily", "weekly"]


@dataclass
class Completion:
    """A single recorded completion of a habit."""

    completed_at: datetime
    habit_id: int | None = None


@dataclass
class Habit:
    name: str
    description: str
    periodicity: Periodicity
    habit_id: int
    created_at: datetime = field(default_factory=datetime.now)
    completions: list[Completion] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Habit name must not be empty.")
        if self.periodicity not in ("daily", "weekly"):
            raise ValueError(f"periodicity must be 'daily' or 'weekly', got {self.periodicity!r}")

    def complete(self, when: datetime | None = None) -> Completion:
        """Record a completion and return it.

        Appends a new :class:`Completion` to ``self.completions`` using the
        supplied timestamp (or ``datetime.now()`` when omitted) and returns
        it so the caller can persist it via ``Storage.save_completion``.

        The method is deliberately impure about ``self.completions`` — the
        tracker is expected to persist the returned completion immediately,
        and the in-memory list must stay in sync with what is on disk.
        """
        completion = Completion(
            habit_id=self.habit_id,
            completed_at=when if when is not None else datetime.now(),
        )
        self.completions.append(completion)
        return completion
