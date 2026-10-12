"""Pydantic models for the REST API."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class HabitCreate(BaseModel):
    name: str = Field(..., min_length=1)
    description: str = ""
    periodicity: Literal["daily", "weekly"]


class HabitOut(BaseModel):
    id: int
    name: str
    description: str
    periodicity: Literal["daily", "weekly"]
    created_at: datetime


class CompletionOut(BaseModel):
    habit_id: int
    completed_at: datetime


class CheckOffIn(BaseModel):
    when: datetime | None = None


class StreakOut(BaseModel):
    habit_id: int | None = None
    longest_streak: int
