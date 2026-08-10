"""Helpers shared by the developer console tests."""

from __future__ import annotations

import pygame

from apex_horizon.debug.commands import Reply
from apex_horizon.engine.unlocks import catalogue as c
from apex_horizon.engine.values import Money


def run(game, line: str) -> Reply:
    return game.dev_commands.execute(line)


def key(code, mod=0, unicode=""):
    return pygame.event.Event(pygame.KEYDOWN, key=code, mod=mod, unicode=unicode)


def type_line(console, text: str) -> None:
    for character in text:
        console.handle_event(key(ord(character), 0, character))
    console.handle_event(key(pygame.K_RETURN, 0, "\r"))


def found_company(game) -> None:
    player = game.context.player
    player.unlocks.unlock(c.CREATE_COMPANY)
    player.cash = Money(100_000)
    company, message = player.found_company("Test Capital", day=1)
    assert company is not None, message


def _finish(game) -> None:
    """Run any scheduled time jump to completion, as frames would."""
    for _ in range(2_000):
        if not game.dev_commands.busy:
            return
        game.dev_commands.pump(0.05)
    raise AssertionError("the scheduled jump never finished")
