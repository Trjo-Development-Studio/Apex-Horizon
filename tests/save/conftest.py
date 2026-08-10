"""Fixtures for the Save System tests (Design Bible Volume 16)."""

from __future__ import annotations

import pytest

from apex_horizon.engine.save import (
    SaveStore,
)
from apex_horizon.engine.values import Calendar, set_calendar
from apex_horizon.ui.app import GameApp


@pytest.fixture(autouse=True)
def _calendar():
    set_calendar(Calendar(7, 4, 12))
    yield
    set_calendar(None)


@pytest.fixture
def store(tmp_path):
    return SaveStore(tmp_path, manual_slots=5)


@pytest.fixture
def game(tmp_path):
    app = GameApp(size=(1100, 700), seed=2026)
    app.saves.store = SaveStore(tmp_path, manual_slots=5)
    yield app
    app.shutdown()
