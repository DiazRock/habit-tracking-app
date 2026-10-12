"""FastAPI application factory and console entry point.

Run with:
    habit-api
or:
    uvicorn habit_tracker.api.main:app --reload
"""

from __future__ import annotations

import os

import uvicorn
from fastapi import FastAPI

from habit_tracker.api.deps import build_tracker
from habit_tracker.api.routers import analytics, habits, system


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    app = FastAPI(
        title="Habit Tracker API",
        version="0.1.0",
        description="REST API for the DLBDSOOFPP01 habit tracking project.",
    )

    # Single shared tracker per process. A future iteration will move this
    # behind a proper dependency-injection layer.
    app.state.tracker = build_tracker()

    app.include_router(system.router)
    app.include_router(habits.router, prefix="/habits", tags=["habits"])
    app.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
    return app


app = create_app()


def run() -> None:
    """Console entry point for `habit-api`."""
    host = os.environ.get("API_HOST", "127.0.0.1")
    port = int(os.environ.get("API_PORT", "8000"))
    uvicorn.run("habit_tracker.api.main:app", host=host, port=port, reload=False)