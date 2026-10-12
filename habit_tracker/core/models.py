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
    """A habit the user wants to track."""

    name: str
    description: str
    periodicity: Periodicity
    created_at: datetime = field(default_factory=datetime.now)
    habit_id: int | None = None
    completions: list[Completion] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Habit name must not be empty.")
        if self.periodicity not in ("daily", "weekly"):
            raise ValueError(
                f"periodicity must be 'daily' or 'weekly', got {self.periodicity!r}"
            )