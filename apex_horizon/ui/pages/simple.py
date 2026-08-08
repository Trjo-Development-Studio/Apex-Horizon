"""Settings, and honest placeholders for systems still to be built.

V14.26 requires a page with no content to present a clear, intentional empty
state. Saying plainly that a system is still to come is more honest than an
empty table implying there is simply nothing to show.
"""

from __future__ import annotations

import pygame

from .. import theme
from ..widgets import Button, Card, draw_text, panel, truncate
from .base import EmptyStatePage, Page


class InvestmentsPage(Page):
    """What the company holds, and what its people are working on (V9.12)."""

    key = "investments"
    title = "Investments"
    subtitle = "What your company holds, and what it is considering"

    @property
    def investments(self):
        company = self.context.company
        return getattr(company, "investments", None) if company else None

    def cards(self):
        system = self.investments
        if system is None:
            return []
        stats = system.statistics()
        return [
            Card("Holdings", stats["Holdings value"].format(decimals=0),
                 f"{stats['Open positions']} open positions"),
            Card("Unrealised", stats["Unrealised"].format(decimals=0, signed=True),
                 "On positions still held",
                 accent=theme.value_colour(not stats["Unrealised"].is_negative)),
            Card("Realised", stats["Realised"].format(decimals=0, signed=True),
                 f"{stats['Closed']} closed · {stats['Win rate']} profitable",
                 accent=theme.value_colour(not stats["Realised"].is_negative)),
            Card("In the pipeline", str(stats["Awaiting review"] + stats["Awaiting execution"]),
                 "Awaiting review or execution"),
        ]

    def draw_content(self, surface, rect, fonts, mouse) -> None:
        system = self.investments
        if system is None:
            panel(surface, pygame.Rect(rect.left, rect.top, rect.width, 160))
            draw_text(surface, fonts.body,
                      "Found a company and hire someone to begin investing.",
                      (rect.left + 24, rect.top + 60), theme.TEXT_MUTED)
            return

        column = (rect.width - theme.GAP) // 2
        held = pygame.Rect(rect.left, rect.top, column, 300)
        panel(surface, held)
        draw_text(surface, fonts.subheading, "Open positions", (held.left + 20, held.top + 16))
        y = held.top + 54
        positions = system.open_positions()
        if not positions:
            draw_text(surface, fonts.small, "Nothing held right now.",
                      (held.left + 20, y), theme.TEXT_FAINT)
        for position in positions[:8]:
            listing = self.context.market.listing_for(position.company_id)
            company_record = self.context.world.company_by_id(position.company_id)
            if listing is None or company_record is None:
                continue
            gain = position.unrealised_return(listing.price)
            draw_text(surface, fonts.small,
                      truncate(fonts.small, company_record.name, column - 200),
                      (held.left + 20, y), theme.TEXT)
            draw_text(surface, fonts.mono_small, position.value_at(listing.price).format(decimals=0),
                      (held.right - 100, y), theme.TEXT, align="right")
            draw_text(surface, fonts.mono_small, gain.format(signed=True),
                      (held.right - 20, y), theme.value_colour(not gain.is_negative),
                      align="right")
            y += 24

        pipeline = pygame.Rect(held.right + theme.GAP, rect.top, column, 300)
        panel(surface, pipeline)
        draw_text(surface, fonts.subheading, "The pipeline",
                  (pipeline.left + 20, pipeline.top + 16))
        draw_text(surface, fonts.small,
                  "Research finds it, management approves it, an investor acts.",
                  (pipeline.left + 20, pipeline.top + 42), theme.TEXT_MUTED)
        y = pipeline.top + 76
        recent = (system.awaiting_execution() + system.pending_review())[:8]
        if not recent:
            draw_text(surface, fonts.small, "Nothing under consideration.",
                      (pipeline.left + 20, y), theme.TEXT_FAINT)
        for opportunity in recent:
            company_record = self.context.world.company_by_id(opportunity.company_id)
            if company_record is None:
                continue
            draw_text(surface, fonts.small,
                      truncate(fonts.small, company_record.name, column - 220),
                      (pipeline.left + 20, y), theme.TEXT)
            draw_text(surface, fonts.small, str(opportunity.stage),
                      (pipeline.right - 20, y), theme.TEXT_MUTED, align="right")
            y += 24


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
        self._buttons_by_slot: dict[tuple[str, str], Button] = {}
        self._slot_buttons: list[tuple[str, str, Button]] = []
        #: Set to (slot, action) when the player asks to save or load a slot.
        self.slot_request: tuple[str, str] | None = None

    def _slot_button(self, slot: str, action: str, label: str) -> Button:
        key = (slot, action)
        if key not in self._buttons_by_slot:
            self._buttons_by_slot[key] = Button(label)
        return self._buttons_by_slot[key]

    def take_slot_request(self) -> tuple[str, str] | None:
        request, self.slot_request = self.slot_request, None
        return request

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
        for slot, action, button in self._slot_buttons:
            if button.handle_event(event) and button.take_click():
                self.slot_request = (slot, action)
                return True
        return False

    def take_speed_request(self) -> int | None:
        request, self.requested_speed = self.requested_speed, None
        return request

    def take_exit_request(self) -> bool:
        request, self.exit_requested = self.exit_requested, False
        return request

    def draw_content(self, surface, rect, fonts, mouse) -> None:
        self._draw_simulation(surface, rect, fonts, mouse)
        saves_rect = pygame.Rect(rect.left + 540, rect.top,
                                 max(320, rect.width - 540), 300)
        self._draw_saves(surface, saves_rect, fonts, mouse)

    def _draw_simulation(self, surface, rect, fonts, mouse) -> None:
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

    def _draw_saves(self, surface, rect, fonts, mouse) -> None:
        """Manual save slots (V16.8) with the details V16.9 requires."""
        panel(surface, rect)
        draw_text(surface, fonts.subheading, "Saved games", (rect.left + 20, rect.top + 18))
        saves = self.context.saves
        if saves is None:
            draw_text(surface, fonts.small, "The Save System is unavailable.",
                      (rect.left + 20, rect.top + 56), theme.TEXT_FAINT)
            return

        draw_text(surface, fonts.small,
                  f"Autosaves every {saves.autosave_interval_months} in-game month(s).",
                  (rect.left + 20, rect.top + 52), theme.TEXT_MUTED)

        self._slot_buttons.clear()
        y = rect.top + 84
        for info in saves.slots():
            draw_text(surface, fonts.small, info.label, (rect.left + 20, y), theme.TEXT)
            colour = theme.NEGATIVE if info.damaged else (
                theme.TEXT_MUTED if info.exists else theme.TEXT_FAINT
            )
            draw_text(surface, fonts.small, truncate(fonts.small, info.describe(), 240),
                      (rect.left + 110, y), colour)

            if not info.is_autosave:
                save_button = self._slot_button(info.slot, "save", "Save")
                save_button.draw(surface, pygame.Rect(rect.right - 150, y - 6, 58, 24),
                                 fonts, mouse)
                self._slot_buttons.append((info.slot, "save", save_button))
            load_button = self._slot_button(info.slot, "load", "Load")
            load_button.enabled = info.exists
            load_button.draw(surface, pygame.Rect(rect.right - 84, y - 6, 58, 24), fonts, mouse)
            self._slot_buttons.append((info.slot, "load", load_button))
            y += 34
