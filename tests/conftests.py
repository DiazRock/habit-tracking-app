"""Shared pytest fixtures."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from habit_tracker.api.deps import build_tracker
from habit_tracker.api.main import create_app


@pytest.fixture()
def tracker(tmp_path, monkeypatch):
    """Fresh in-memory-ish tracker with a temp DB path."""
    monkeypatch.setenv("HABIT_DB", str(tmp_path / "test.db"))
    return build_tracker()


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """FastAPI TestClient with an isolated tracker."""
    monkeypatch.setenv("HABIT_DB", str(tmp_path / "test.db"))
    app = create_app()
    with TestClient(app) as c:
        yield c