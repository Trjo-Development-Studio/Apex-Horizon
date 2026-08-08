"""The Unlock Tree page.

V6.10 asks for a professional roadmap with large spacing, clean alignment,
straight horizontal connections and no crossing lines, so that the player always
understands how every branch connects back to Basic Investing. The primary
progression is drawn as a single horizontal line, which is what V6.5 requires.

Only the part of the tree whose effects exist is shown. A roadmap full of
unlocks that change nothing would misrepresent the game, so the branches arrive
with the systems they gate.
"""

from __future__ import annotations

import pygame

from ...engine.unlocks import UNLOCKS
from .. import theme
from ..widgets import Button, Card, draw_text, panel, truncate
from .base import Page

NODE_WIDTH = 210
NODE_HEIGHT = 140
CONNECTOR = 46


class UnlockTreePage(Page):
    """The player's map of their own future (V6.14)."""

    key = "unlocks"
    title = "Unlock Tree"
    subtitle = "How your company grows"

    def __init__(self, context):
        super().__init__(context)
        self._buttons: dict[str, Button] = {}
        #: Set to an unlock key when the player asks to buy it.
        self.unlock_request: str | None = None

    def take_unlock_request(self) -> str | None:
        request, self.unlock_request = self.unlock_request, None
        return request

    def _button(self, key: str) -> Button:
        if key not in self._buttons:
            self._buttons[key] = Button("Unlock", primary=True)
        return self._buttons[key]

    def cards(self) -> list[Card]:
        tree = self.context.unlocks
        player = self.context.player
        if tree is None:
            return []
        available = tree.available()
        return [
            Card("Unlocked", f"{len(tree.unlocked)} of {len(UNLOCKS)}",
                 "Progress along the tree"),
            Card("Available now", str(len(available)),
                 available[0].name if available else "Nothing to buy yet"),
            Card("Personal cash", player.cash.format(decimals=0) if player else "—",
                 "Unlocks are bought with your own money"),
        ]

    def handle_event(self, event) -> bool:
        tree = self.context.unlocks
        if tree is None:
            return False
        for unlock in UNLOCKS:
            button = self._button(unlock.key)
            if not button.enabled:
                continue
            if button.handle_event(event) and button.take_click():
                self.unlock_request = unlock.key
                return True
        return False

    def draw_content(self, surface, rect, fonts, mouse) -> None:
        tree = self.context.unlocks
        player = self.context.player
        if tree is None:
            panel(surface, pygame.Rect(rect.left, rect.top, rect.width, 140))
            draw_text(surface, fonts.body, "The Unlock Tree is unavailable.",
                      (rect.left + 24, rect.top + 56), theme.TEXT_MUTED)
            return

        draw_text(surface, fonts.small,
                  "Every unlock requires the one before it; progression runs left to right.",
                  (rect.left, rect.top), theme.TEXT_MUTED)

        top = rect.top + 30
        for index, unlock in enumerate(UNLOCKS):
            x = rect.left + index * (NODE_WIDTH + CONNECTOR)
            if x + NODE_WIDTH > rect.right:
                break
            if index:
                # A straight horizontal connection, never a crossing one (V6.10).
                y = top + NODE_HEIGHT // 2
                pygame.draw.line(surface, theme.BORDER,
                                 (x - CONNECTOR, y), (x, y), 2)
            self._draw_node(surface, pygame.Rect(x, top, NODE_WIDTH, NODE_HEIGHT),
                            fonts, mouse, unlock, tree, player)

        note = pygame.Rect(rect.left, top + NODE_HEIGHT + theme.GAP, rect.width,
                           min(96, max(0, rect.bottom - top - NODE_HEIGHT - theme.GAP)))
        if note.height >= 90:
            panel(surface, note)
            draw_text(surface, fonts.subheading, "Further branches",
                      (note.left + 20, note.top + 16))
            draw_text(surface, fonts.small,
                      "Analytics, News, Finance, Employees, Training, Recruitment and "
                      "Company branches open from here as those systems are built.",
                      (note.left + 20, note.top + 48), theme.TEXT_MUTED)

    def _draw_node(self, surface, rect, fonts, mouse, unlock, tree, player) -> None:
        owned = tree.has(unlock.key)
        ready = not owned and tree.prerequisites_met(unlock.key)
        panel(surface, rect)
        if owned:
            pygame.draw.rect(surface, theme.POSITIVE, rect, 2, border_radius=8)

        status = "Unlocked" if owned else ("Available" if ready else "Locked")
        colour = (theme.POSITIVE if owned
                  else theme.ACCENT if ready else theme.TEXT_FAINT)
        draw_text(surface, fonts.small, status.upper(), (rect.left + 16, rect.top + 14), colour)
        draw_text(surface, fonts.body,
                  truncate(fonts.body, unlock.name, rect.width - 32),
                  (rect.left + 16, rect.top + 34))

        _wrap(surface, fonts.small, unlock.description,
              pygame.Rect(rect.left + 16, rect.top + 58, rect.width - 32, 54),
              theme.TEXT_MUTED)

        button = self._button(unlock.key)
        if owned or not ready:
            button.enabled = False
            if not owned:
                cost = tree.cost_of(unlock.key)
                draw_text(surface, fonts.small,
                          cost.format(decimals=0) if cost.is_positive else "",
                          (rect.right - 16, rect.bottom - 26), theme.TEXT_FAINT,
                          align="right")
            return

        cost = tree.cost_of(unlock.key)
        affordable = player is not None and player.cash >= cost
        button.enabled = affordable
        draw_text(surface, fonts.small, cost.format(decimals=0),
                  (rect.left + 16, rect.bottom - 26),
                  theme.TEXT if affordable else theme.NEGATIVE)
        button.draw(surface, pygame.Rect(rect.right - 92, rect.bottom - 40, 76, 30),
                    fonts, mouse)


def _wrap(surface, font, text, rect, colour) -> None:
    words, line, y = str(text).split(), "", rect.top
    for word in words:
        candidate = f"{line} {word}".strip()
        if font.size(candidate)[0] <= rect.width or not line:
            line = candidate
            continue
        draw_text(surface, font, line, (rect.left, y), colour)
        line, y = word, y + 16
        if y > rect.bottom - 16:
            return
    if line:
        draw_text(surface, font, line, (rect.left, y), colour)
