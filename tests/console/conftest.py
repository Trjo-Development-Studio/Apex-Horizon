"""Fixtures for the developer console tests (V15.18)."""

from __future__ import annotations

import os

import pytest

from apex_horizon.engine.values import Calendar, set_calendar


@pytest.fixture
def game():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    from apex_horizon.ui.app import GameApp

    set_calendar(Calendar(7, 4, 12))
    app = GameApp(size=(1100, 700), seed=2026)
    yield app
    app.shutdown()
    set_calendar(None)
