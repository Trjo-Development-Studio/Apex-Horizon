"""Helpers shared by the interface tests."""

from __future__ import annotations

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from apex_horizon.engine.unlocks import CREATE_COMPANY
from apex_horizon.engine.values import Money
from apex_horizon.ui.popups import PromptPopup
from apex_horizon.ui.start_menu import NEW_GAME


def click(pos):
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos)


def release(pos):
    """Buttons fire on release, so pressing one takes both halves."""
    return pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=pos)


def _choose(app, key: str) -> None:
    """Answer the open popup, the way clicking its button would."""
    app.popups.current.chosen = key
    app.popups.handle_event(pygame.event.Event(pygame.USEREVENT))


def _new_game(menu_app, slot: str = "2", name: str = "My Empire") -> None:
    """Start Menu -> New Game -> choose a slot -> name it -> create."""

    menu_app.menu.request = (NEW_GAME, slot)
    menu_app._menu_tick(0)
    if menu_app.popups.current is not None and not isinstance(
            menu_app.popups.current, PromptPopup):
        _choose(menu_app, "overwrite")  # the slot already held a game
    prompt = menu_app.popups.current
    assert isinstance(prompt, PromptPopup), "the game must be named before it exists"
    prompt.text = name
    _choose(menu_app, "create")


def _found_company_for_acquisitions(app, cash: int = 2_000_000_000):
    app.context.player.cash = Money(cash)
    app.context.player.unlocks.unlock(CREATE_COMPANY)
    company, message = app.context.player.found_company("Acquirer Capital", 1)
    assert company is not None, message
    company.attach_market(app.context.market, app.context.allocator)
    company.register(app.context.engine)
    company.receive_capital(app.context.engine.date.day, Money(cash))
    # Acquisitions require Company Level 2 (acquisitions.minimum_company_level).
    company.set_level(3)
    return company
