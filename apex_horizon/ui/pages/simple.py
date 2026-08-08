"""Settings, and honest placeholders for systems still to be built.

V14.26 requires a page with no content to present a clear, intentional empty
state. Saying plainly that a system is still to come is more honest than an
empty table implying there is simply nothing to show.
"""

from __future__ import annotations

import pygame

from .. import theme
from ..widgets import Button, Card, draw_text, panel
from .base import EmptyStatePage, Page


class InvestmentsPage(EmptyStatePage):
    key = "investments"
    title = "Investments"
    subtitle = "What your company holds"
    message = "The Investment System is not built yet."
    detail = "Research, approval and execution arrive in a later milestone."


class NewsPage(EmptyStatePage):
    key = "news"
    title = "News"
    subtitle = "What is happening in the financial world"
    message = "The News System is not built yet."
    detail = "Headlines will be generated from real simulation events."


class UnlockTreePage(EmptyStatePage):
    key = "unlocks"
    title = "Unlock Tree"
    subtitle = "How your company grows"
    message = "The Unlock Tree is not built yet."
    detail = "Progression from Basic Investing through to Investment Funds."


class SettingsPage(Page):
    """Simulation speed, and leaving the game (V14.5, V16.3)."""

    key = "settings"
    title = "Settings"
    subtitle = "Preferences and session"

    def __init__(self, context):
        super().__init__(context)
        self.speed_buttons = {speed: Button(f"×{speed}") for speed in (1, 2, 3)}  # noqa: RUF001 (multiplication sign is intended)
        self.exit_button = Button("Save & Exit")
        self.requested_speed: int | None = None
        self.exit_requested = False

    def cards(self):
        engine = self.context.engine
        if engine is None:
            return []
        return [
            Card("Simulation speed", f"×{engine.clock.speed}",  # noqa: RUF001 (multiplication sign is intended)
                 "One second is one in-game day"),
            Card("In-game date", engine.date.label(), f"Day {engine.date.day}"),
        ]

    def handle_event(self, event) -> bool:
        for speed, button in self.speed_buttons.items():
            if button.handle_event(event) and button.take_click():
                self.requested_speed = speed
                return True
        if self.exit_button.handle_event(event) and self.exit_button.take_click():
            self.exit_requested = True
            return True
        return False

    def take_speed_request(self) -> int | None:
        request, self.requested_speed = self.requested_speed, None
        return request

    def take_exit_request(self) -> bool:
        request, self.exit_requested = self.exit_requested, False
        return request

    def draw_content(self, surface, rect, fonts, mouse) -> None:
        box = pygame.Rect(rect.left, rect.top, min(rect.width, 520), 210)
        panel(surface, box)
        draw_text(surface, fonts.subheading, "Simulation", (box.left + 20, box.top + 18))
        draw_text(surface, fonts.small,
                  "Speed can also be changed with the 1, 2 and 3 keys.",
                  (box.left + 20, box.top + 50), theme.TEXT_MUTED)
        engine = self.context.engine
        current = engine.clock.speed if engine else 1
        for index, (speed, button) in enumerate(self.speed_buttons.items()):
            button.primary = speed == current
            button.draw(surface, pygame.Rect(box.left + 20 + index * 78, box.top + 80, 68, 34),
                        fonts, mouse)
        draw_text(surface, fonts.small,
                  "The simulation pauses only while a decision is open.",
                  (box.left + 20, box.top + 130), theme.TEXT_FAINT)
        self.exit_button.draw(surface,
                              pygame.Rect(box.left + 20, box.bottom - 52, 140, 36),
                              fonts, mouse)
