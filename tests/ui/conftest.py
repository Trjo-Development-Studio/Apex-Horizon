"""Fixtures for the interface tests (Design Bible Volumes 14 and 27)."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")


from apex_horizon.engine.values import Calendar, set_calendar
from apex_horizon.ui.app import GameApp


@pytest.fixture
def app():
    set_calendar(Calendar(7, 4, 12))
    application = GameApp(size=(1280, 800), seed=2026)
    yield application
    application.shutdown()
    set_calendar(None)



@pytest.fixture
def menu_app(tmp_path):
    from apex_horizon.engine.save import SaveStore

    set_calendar(Calendar(7, 4, 12))
    application = GameApp(size=(1100, 760), seed=2026, start_in_menu=True)
    application.saves.store = SaveStore(tmp_path, manual_slots=5)
    application.menu.saves = application.saves
    yield application
    application.shutdown()
    set_calendar(None)
