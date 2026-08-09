"""The Start Menu.

V16.4 has Save & Exit returning the player to the Main Menu, which means there
has to be one to return to. This is that screen, and the first thing the player
sees when the game opens.

It is deliberately not another dashboard. There is nothing to manage here and
nothing to read: a title, the version, and the few things a player can do
before a world exists. V1.15 still applies — clean, modern, professional, no
flashy effects — but a menu earns a little more room to breathe than a page
dense with figures.

The save slots are listed rather than hidden behind a submenu, because the one
thing a returning player wants is to see their game and continue it (V16.9
defines what a slot shows without loading the world).
"""

from __future__ import annotations

import pygame

from .. import __version__
from . import theme
from .widgets import Button, draw_text, panel, truncate

NEW_GAME = "new"
LOAD_GAME = "load"
SETTINGS = "settings"
EXIT = "exit"

PANEL_WIDTH = 460
SLOT_HEIGHT = 46


class StartMenu:
    """What the player sees before a world exists, and after leaving one."""

    def __init__(self, saves=None):
        self.saves = saves
        self.buttons = {
            NEW_GAME: Button("New Game", primary=True),
            LOAD_GAME: Button("Load Game"),
            SETTINGS: Button("Settings"),
            EXIT: Button("Exit Game"),
        }
        self.showing_loads = False
        self.message: str = ""
        #: Set to an action, or ("load", slot), for the application to act on.
        self.request: object | None = None
        self._slot_buttons: dict[str, Button] = {}
        self._slot_rects: list[tuple[pygame.Rect, str]] = []

    # -- interaction -------------------------------------------------------
    def take_request(self):
        request, self.request = self.request, None
        return request

    def handle_event(self, event) -> bool:
        if self.showing_loads:
            for rect, slot in self._slot_rects:
                if (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
                        and rect.collidepoint(event.pos)):
                    self.request = (LOAD_GAME, slot)
                    return True
            back = self.buttons[LOAD_GAME]
            if back.handle_event(event) and back.take_click():
                self.showing_loads = False
                return True
            return False

        for key, button in self.buttons.items():
            if not button.enabled:
                continue
            if button.handle_event(event) and button.take_click():
                if key == LOAD_GAME:
                    self.showing_loads = True
                else:
                    self.request = key
                return True
        return False

    # -- drawing -----------------------------------------------------------
    def draw(self, surface, fonts, mouse) -> None:
        surface.fill(theme.BACKGROUND)
        width, height = surface.get_size()

        title_y = max(70, height // 2 - 210)
        draw_text(surface, fonts.title, "APEX HORIZON", (width // 2, title_y),
                  theme.TEXT, align="center")
        draw_text(surface, fonts.small,
                  "Build an investment company. Outlast the market.",
                  (width // 2, title_y + 44), theme.TEXT_MUTED, align="center")
        draw_text(surface, fonts.tiny, f"Version {__version__}",
                  (width // 2, height - 34), theme.TEXT_FAINT, align="center")

        box = pygame.Rect(width // 2 - PANEL_WIDTH // 2, title_y + 90,
                          PANEL_WIDTH, min(360, height - title_y - 140))
        if self.showing_loads:
            self._draw_loads(surface, fonts, mouse, box)
        else:
            self._draw_actions(surface, fonts, mouse, box)

        if self.message:
            draw_text(surface, fonts.small, self.message,
                      (width // 2, box.bottom + 24), theme.NEGATIVE, align="center")

    def _draw_actions(self, surface, fonts, mouse, box) -> None:
        order = (NEW_GAME, LOAD_GAME, SETTINGS, EXIT)
        saved = self._saved_slots()
        # The button says why it cannot be pressed, rather than a note beside it
        # that has to find room between two buttons (V14.26).
        self.buttons[LOAD_GAME].label = (
            "Load Game" if saved else "Load Game — no saved games yet"
        )
        self.buttons[LOAD_GAME].enabled = bool(saved)
        for index, key in enumerate(order):
            rect = pygame.Rect(box.left + 60, box.top + index * 58, box.width - 120, 46)
            self.buttons[key].draw(surface, rect, fonts, mouse)

    def _draw_loads(self, surface, fonts, mouse, box) -> None:
        panel(surface, box)
        draw_text(surface, fonts.subheading, "Load a saved game",
                  (box.left + 20, box.top + 16))
        self._slot_rects.clear()

        slots = self._saved_slots()
        y = box.top + 56
        for info in slots:
            if y + SLOT_HEIGHT > box.bottom - 60:
                break
            rect = pygame.Rect(box.left + 16, y, box.width - 32, SLOT_HEIGHT - 6)
            hovered = rect.collidepoint(mouse)
            pygame.draw.rect(surface, theme.SURFACE_RAISED if hovered else theme.SURFACE,
                             rect, border_radius=6)
            draw_text(surface, fonts.small, info.label, (rect.left + 14, rect.top + 6),
                      theme.TEXT)
            draw_text(surface, fonts.tiny,
                      truncate(fonts.tiny, info.describe(), rect.width - 40),
                      (rect.left + 14, rect.top + 24), theme.TEXT_MUTED)
            self._slot_rects.append((rect, info.slot))
            y += SLOT_HEIGHT

        back = self.buttons[LOAD_GAME]
        back.label = "Back"
        back.enabled = True
        back.draw(surface, pygame.Rect(box.left + 16, box.bottom - 52,
                                       box.width - 32, 40), fonts, mouse)

    def _saved_slots(self) -> list:
        if self.saves is None:
            return []
        try:
            return [info for info in self.saves.slots() if info.exists]
        except OSError:  # pragma: no cover - a broken save directory
            return []
