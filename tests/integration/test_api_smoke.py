"""Smoke tests for the FastAPI adapter."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_create_and_list_habits(client):
    r = client.post(
        "/habits",
        json={"name": "Meditate", "description": "10 min", "periodicity": "daily"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "Meditate"
    assert body["id"] == 1

    r = client.get("/habits")
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_get_unknown_habit_returns_404(client):
    r = client.get("/habits/9999")
    assert r.status_code == 404


def test_invalid_periodicity_returns_422(client):
    r = client.post(
        "/habits",
        json={"name": "X", "description": "", "periodicity": "monthly"},
    )
    assert r.status_code == 422


def test_habit_persists_across_requests(client):
    """Create a habit, then read it back via a separate request.

    Exercises router → tracker → storage → SQLite end-to-end.
    """
    created = client.post(
        "/habits",
        json={"name": "Water", "description": "", "periodicity": "daily"},
    )
    assert created.status_code == 201
    habit_id = created.json()["id"]

    fetched = client.get(f"/habits/{habit_id}")
    assert fetched.status_code == 200
    assert fetched.json()["name"] == "Water"
