"""Launch test for the application shell.

Design Bible V15.19 and V19.10 make "the game launches successfully" a mandatory
check for every completed implementation. This exercises the real window and
frame loop headlessly so the requirement is verified automatically on every run.
"""

from __future__ import annotations

import os

import pytest

# Select headless SDL drivers before pygame initialises any subsystem.
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from apex_horizon.engine import errors
from apex_horizon.ui.window import GameWindow


@pytest.fixture
def window():
    errors.clear_error_notifiers()
    win = GameWindow(size=(320, 240))
    yield win
    win.shutdown()
    errors.clear_error_notifiers()


def test_window_starts_and_renders_frames(window):
    assert window.running is True
    # Several frames must render without raising.
    for _ in range(3):
        window.tick()


def test_quit_event_stops_the_loop(window):
    pygame.event.post(pygame.event.Event(pygame.QUIT))
    window.tick()
    assert window.running is False


def test_escape_key_stops_the_loop(window):
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
    window.tick()
    assert window.running is False


def test_engine_errors_reach_the_window(window):
    # The shell subscribes to engine error notifications (V15.13).
    errors.notify_player("Saving failed after 3 attempts.")
    assert any("Saving failed" in message for message in window.messages)
    window.tick()


def test_window_drives_the_simulation(window):
    # The shell advances in-game time each frame (V13.29).
    start = window.engine.date.day
    for _ in range(3):
        window.tick()
    assert window.engine.date.day >= start


def test_speed_keys_change_simulation_speed(window):
    # V13.5 speeds, reachable by keyboard per V27.9.
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_3))
    window.tick()
    assert window.engine.clock.speed == 3
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_1))
    window.tick()
    assert window.engine.clock.speed == 1
