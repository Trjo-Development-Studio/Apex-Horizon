"""The Start Menu.

V16.4 has Save & Exit returning the player to the Main Menu, which means there
has to be one to return to. This is that screen, and the first thing the player
sees when the game opens.

It is deliberately not another dashboard. There is nothing to manage here and
nothing to read: a title, the version, and the few things a player can do
before a world exists. V1.15 still applies — clean, modern, professional, no
flashy effects — but a menu earns a little more room to breathe than a page
dense with figures, and the project manager asked for it to look like the front
of a finished game rather than an empty application window, which is what
:mod:`.background` is for.

Starting a game means choosing where it will live. A save belongs to one slot
for its whole life (the project manager's decision, 2026-08-09), so the slot is
picked before the world exists rather than assumed — the same list serves New
Game and Load Game, showing which slots are empty and which are already taken
(V16.9 defines what a slot shows without loading it).
"""

from __future__ import annotations

import pygame

from .. import __version__
from . import theme
from .background import Backdrop
from .widgets import Button, draw_text, panel, truncate

NEW_GAME = "new"
LOAD_GAME = "load"
SETTINGS = "settings"
EXIT = "exit"

PANEL_WIDTH = 460
SLOT_HEIGHT = 52


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
        self.back = Button("Back")
        #: ``None`` for the main buttons, or which list of slots is showing.
        self.mode: str | None = None
        self.message: str = ""
        #: False when the message is a problem, so a save confirmation is not
        #: shown in the same red as an unreadable file.
        self.message_ok: bool = True
        #: Set to an action, or ``(action, slot)``, for the application to act on.
        self.request: object | None = None
        self.background = Backdrop()
        self._slot_rects: list[tuple[pygame.Rect, str, bool]] = []

    # -- interaction -------------------------------------------------------
    def take_request(self):
        request, self.request = self.request, None
        return request

    def say(self, message: str, *, ok: bool = True) -> None:
        """Show one line under the menu until something replaces it."""
        self.message, self.message_ok = message, ok

    def close_slots(self) -> None:
        """Return to the main buttons."""
        self.mode = None

    def handle_event(self, event) -> bool:
        if self.mode is not None:
            return self._handle_slot_event(event)
        for key, button in self.buttons.items():
            if not button.enabled:
                continue
            if button.handle_event(event) and button.take_click():
                self.mode = key if key in (NEW_GAME, LOAD_GAME) else None
                if self.mode is None:
                    self.request = key
                else:
                    self.message = ""
                return True
        return False

    def _handle_slot_event(self, event) -> bool:
        clicking = event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
        for rect, slot, usable in self._slot_rects:
            if usable and clicking and rect.collidepoint(event.pos):
                self.request = (self.mode, slot)
                return True
        if self.back.handle_event(event) and self.back.take_click():
            self.close_slots()
            return True
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.close_slots()
            return True
        return False

    # -- drawing -----------------------------------------------------------
    def draw(self, surface, fonts, mouse) -> None:
        self.background.draw(surface)
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
                          PANEL_WIDTH, min(400, height - title_y - 140))
        if self.mode is None:
            self._draw_actions(surface, fonts, mouse, box)
        else:
            self._draw_slots(surface, fonts, mouse, box)

        if self.message:
            draw_text(surface, fonts.small, self.message,
                      (width // 2, box.bottom + 24),
                      theme.TEXT_MUTED if self.message_ok else theme.NEGATIVE,
                      align="center")

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

    def _draw_slots(self, surface, fonts, mouse, box) -> None:
        """The five slots (V16.8), each saying whether it is empty or taken."""
        panel(surface, box)
        choosing_new = self.mode == NEW_GAME
        draw_text(surface, fonts.subheading,
                  "Choose a save slot" if choosing_new else "Load a saved game",
                  (box.left + 20, box.top + 16))
        draw_text(surface, fonts.tiny,
                  "YOUR GAME WILL BE SAVED HERE" if choosing_new
                  else "PICK UP WHERE YOU LEFT OFF",
                  (box.left + 20, box.top + 40), theme.TEXT_FAINT)
        self._slot_rects.clear()

        y = box.top + 62
        for info in self._listed_slots():
            if y + SLOT_HEIGHT > box.bottom - 58:
                break
            rect = pygame.Rect(box.left + 16, y, box.width - 32, SLOT_HEIGHT - 6)
            # An empty slot is a place to start a game, not a game to load.
            usable = choosing_new or info.exists
            self._draw_slot(surface, fonts, mouse, rect, info, usable, choosing_new)
            self._slot_rects.append((rect, info.slot, usable))
            y += SLOT_HEIGHT

        self.back.draw(surface, pygame.Rect(box.left + 16, box.bottom - 50,
                                            box.width - 32, 40), fonts, mouse)

    def _draw_slot(self, surface, fonts, mouse, rect, info, usable, choosing_new) -> None:
        hovered = usable and rect.collidepoint(mouse)
        fill = theme.SURFACE_RAISED if hovered else theme.SURFACE
        pygame.draw.rect(surface, fill, rect, border_radius=6)
        if hovered:
            pygame.draw.rect(surface, theme.ACCENT, rect, width=1, border_radius=6)

        text_colour = theme.TEXT if usable else theme.TEXT_FAINT
        # The save's own name, falling back to "Slot N" only when there is
        # nothing saved here to name (project manager correction,
        # 2026-08-10): a list of five identical "Slot N" rows tells the
        # player nothing about which game is which.
        draw_text(surface, fonts.small,
                  truncate(fonts.small, info.title, rect.width - 110),
                  (rect.left + 14, rect.top + 7), text_colour)
        detail = info.describe() if info.exists else "No game saved here"
        draw_text(surface, fonts.tiny, truncate(fonts.tiny, detail, rect.width - 110),
                  (rect.left + 14, rect.top + 27), theme.TEXT_MUTED)

        if choosing_new:
            # V16.9 in one word: is there something here already?
            taken = info.exists
            draw_text(surface, fonts.tiny, "IN USE" if taken else "EMPTY",
                      (rect.right - 14, rect.centery),
                      theme.WARNING if taken else theme.TEXT_FAINT,
                      align="right", baseline="middle")

    # -- what there is to show ---------------------------------------------
    def _listed_slots(self) -> list:
        """Every slot when starting a game; only the saved ones when loading."""
        if self.saves is None:
            return []
        try:
            slots = list(self.saves.slots())
        except OSError:  # pragma: no cover - a broken save directory
            return []
        if self.mode == NEW_GAME:
            return slots
        return [info for info in slots if info.exists]

    def _saved_slots(self) -> list:
        if self.saves is None:
            return []
        try:
            return [info for info in self.saves.slots() if info.exists]
        except OSError:  # pragma: no cover - a broken save directory
            return []
