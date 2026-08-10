"""Settings, and honest placeholders for systems still to be built.

V14.26 requires a page with no content to present a clear, intentional empty
state. Saying plainly that a system is still to come is more honest than an
empty table implying there is simply nothing to show.
"""

from __future__ import annotations

import pygame

from .. import theme
from ..widgets import Button, Card, draw_text, panel, truncate
from .base import Page


class InvestmentsPage(Page):
    """Everything the player has invested in — their own, and the company's.

    The player is an individual investor before they are a CEO (V1.19), and may
    remain one indefinitely (V1.20), so this page leads with the portfolio they
    hold personally. The company's operation appears beneath it once one exists.
    Keeping them visibly apart is what V1.4 and V3.4 require: two separate pools
    of money that never merge.
    """

    key = "investments"
    TITLE = "Investments"
    SUBTITLE = "What you hold personally, and what your company holds"

    @property
    def investments(self):
        """The company's own investment operation, or ``None`` without one
        currently operating (a bankrupt company must not still read as
        actively investing)."""
        if not self.context.has_company:
            return None
        return self.context.company.investments

    def cards(self):
        portfolio = self.context.portfolio
        cards = []
        if portfolio is not None:
            stats = portfolio.statistics()
            cards = [
                Card("Your holdings", stats["Holdings value"].format(decimals=0),
                     f"{stats['Companies held']} companies"),
                Card("Your unrealised", stats["Unrealised"].format(decimals=0, signed=True),
                     "On shares you still hold",
                     accent=theme.value_colour(not stats["Unrealised"].is_negative)),
                Card("Your realised", stats["Realised"].format(decimals=0, signed=True),
                     f"{stats['Trades']} trades · {stats['Win rate']} profitable"
                     if stats["Win rate"] != "—"
                     else f"{stats['Trades']} trades · nothing sold yet",
                     accent=theme.value_colour(not stats["Realised"].is_negative)),
            ]
        system = self.investments
        if system is None:
            return cards
        company_stats = system.statistics()
        return [
            *cards[:2],
            Card("Company holdings", company_stats["Holdings value"].format(decimals=0),
                 f"{company_stats['Open positions']} open positions"),
            Card("Company realised",
                 company_stats["Realised"].format(decimals=0, signed=True),
                 f"{company_stats['Closed']} closed · {company_stats['Win rate']} profitable",
                 accent=theme.value_colour(not company_stats["Realised"].is_negative)),
        ]

    def draw_content(self, surface, rect, fonts, mouse) -> None:
        personal_height = min(240, max(140, rect.height // 2))
        personal = pygame.Rect(rect.left, rect.top, rect.width, personal_height)
        self.draw_personal(surface, personal, fonts)

        remaining = pygame.Rect(rect.left, personal.bottom + theme.GAP, rect.width,
                                max(0, rect.bottom - personal.bottom - theme.GAP))
        if remaining.height >= 120:
            self.draw_company(surface, remaining, fonts, mouse)

    def draw_company(self, surface, remaining, fonts, mouse) -> None:
        """The company's own investment operation, on its own (V8).

        Drawn separately from the personal holdings above it so the Portfolio
        page can show either alone, without the two ever sharing a figure.
        """
        system = self.investments
        if system is None:
            panel(surface, remaining)
            draw_text(surface, fonts.subheading, "Your company",
                      (remaining.left + 20, remaining.top + 16))
            draw_text(surface, fonts.body,
                      "Found a company and hire someone to invest at a larger scale.",
                      (remaining.left + 20, remaining.top + 56), theme.TEXT_MUTED)
            draw_text(surface, fonts.small,
                      "Company money is separate from your own, and is invested by "
                      "the people you employ.",
                      (remaining.left + 20, remaining.top + 84), theme.TEXT_FAINT)
            return

        rect = remaining
        column = (rect.width - theme.GAP) // 2
        held = pygame.Rect(rect.left, rect.top, column, rect.height)
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

        pipeline = pygame.Rect(held.right + theme.GAP, rect.top, column, rect.height)
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

    def draw_personal(self, surface, rect, fonts) -> None:
        """The player's own holdings, bought with their own money (V1.19)."""
        panel(surface, rect)
        draw_text(surface, fonts.subheading, "Your portfolio", (rect.left + 20, rect.top + 16))
        draw_text(surface, fonts.small,
                  "Bought with your personal cash. Trade from a company's page in the Market.",
                  (rect.left + 20, rect.top + 42), theme.TEXT_MUTED)

        portfolio = self.context.portfolio
        market = self.context.market
        world = self.context.world
        if portfolio is None or market is None or world is None:
            draw_text(surface, fonts.small, "Personal investing is unavailable.",
                      (rect.left + 20, rect.top + 78), theme.TEXT_FAINT)
            return

        holdings = sorted(portfolio.holdings.values(),
                          key=lambda h: h.cost_basis.amount, reverse=True)
        if not holdings:
            draw_text(surface, fonts.body, "You do not own any shares yet.",
                      (rect.left + 20, rect.top + 84), theme.TEXT_MUTED)
            draw_text(surface, fonts.small,
                      "Open a company from the Market and buy your first shares.",
                      (rect.left + 20, rect.top + 110), theme.TEXT_FAINT)
            return

        draw_text(surface, fonts.small, "Company", (rect.left + 20, rect.top + 74),
                  theme.TEXT_FAINT)
        for label, x in (("Shares", 430), ("Value", 580), ("Unrealised", 730)):
            draw_text(surface, fonts.small, label, (rect.left + x, rect.top + 74),
                      theme.TEXT_FAINT, align="right")

        y = rect.top + 98
        for holding in holdings:
            if y + 24 > rect.bottom - 8:
                break
            listing = market.listing_for(holding.company_id)
            record = world.company_by_id(holding.company_id)
            if listing is None or record is None:
                continue
            gain = holding.unrealised(listing.price)
            draw_text(surface, fonts.small,
                      truncate(fonts.small, record.name, 300), (rect.left + 20, y))
            draw_text(surface, fonts.mono_small, f"{holding.shares:,}",
                      (rect.left + 430, y), theme.TEXT, align="right")
            draw_text(surface, fonts.mono_small,
                      holding.value_at(listing.price).format(decimals=0),
                      (rect.left + 580, y), theme.TEXT, align="right")
            draw_text(surface, fonts.mono_small, gain.format(decimals=0, signed=True),
                      (rect.left + 730, y), theme.value_colour(not gain.is_negative),
                      align="right")
            y += 24


def _autosave_line(saves) -> str:
    """How often the game saves itself, and where — both in one sentence."""
    where = f"Slot {saves.slot}" if saves.slot else "no slot yet"
    minutes = saves.autosave_interval_minutes
    if minutes <= 0:
        return f"This game is saved in {where}. Autosaving is turned off."
    every = f"{int(minutes)}" if minutes == int(minutes) else f"{minutes:g}"
    return f"This game is saved in {where}, every {every} minutes of play."


class SettingsPage(Page):
    """Simulation speed, and leaving the game (V14.5, V16.3)."""

    key = "settings"
    TITLE = "Settings"
    SUBTITLE = "Preferences and session"

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
        # Clamped to what the page actually has, same as Dashboard/Employees:
        # the notification stack reserves real space at the bottom (V27.7),
        # and a fixed-height panel would otherwise overlap it on a short
        # window. The left offset is also clamped so the panel never starts
        # past the page's own right edge on a narrow window.
        saves_left = min(rect.left + 540, rect.right - 320)
        saves_rect = pygame.Rect(saves_left, rect.top,
                                 max(320, rect.right - saves_left),
                                 max(0, min(300, rect.height)))
        self._draw_saves(surface, saves_rect, fonts, mouse)

    def _draw_simulation(self, surface, rect, fonts, mouse) -> None:
        box = pygame.Rect(rect.left, rect.top, min(rect.width, 520),
                          max(0, min(210, rect.height)))
        panel(surface, box)
        if box.height < 40:
            return
        draw_text(surface, fonts.subheading, "Simulation", (box.left + 20, box.top + 18))
        y = box.top + 50
        if y + 30 <= box.bottom:
            draw_text(surface, fonts.small,
                      "Speed can also be changed with the 1, 2 and 3 keys.",
                      (box.left + 20, y), theme.TEXT_MUTED)
            y += 30
        # The speed buttons are the one control on this panel that must never
        # be skipped for lack of room — everything below them (the pause
        # note, Save & Exit) gives way instead, positioned after them rather
        # than pinned to the box's bottom, so a short box can never make Save
        # & Exit land on top of them (same priority rule the Employee
        # department bar already uses, 2026-08).
        engine = self.context.engine
        current = engine.clock.speed if engine else 1
        for index, (speed, button) in enumerate(self.speed_buttons.items()):
            button.primary = speed == current
            button.draw(surface, pygame.Rect(box.left + 20 + index * 78, y, 68, 34),
                        fonts, mouse)
        y += 34 + 16
        if y + 14 <= box.bottom - 44:
            draw_text(surface, fonts.small,
                      "The simulation pauses only while a decision is open.",
                      (box.left + 20, y), theme.TEXT_FAINT)
        exit_top = max(y, box.bottom - 52)
        if exit_top + 36 <= box.bottom:
            self.exit_button.draw(surface, pygame.Rect(box.left + 20, exit_top, 140, 36),
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
                  _autosave_line(saves),
                  (rect.left + 20, rect.top + 52), theme.TEXT_MUTED)

        self._slot_buttons.clear()
        y = rect.top + 84
        for info in saves.slots():
            if y + 24 > rect.bottom - 8:
                break
            # The save's own name leads the row, falling back to "Slot N" only
            # when there is nothing saved here to name (project manager
            # correction, 2026-08-10). Both columns are measured off the panel
            # rather than fixed, so a long save name cannot push the details
            # onto the buttons at the end of the row.
            name_width = max(60, min(150, (rect.width - 220) // 2))
            detail_left = rect.left + 20 + name_width + 12
            detail_width = max(0, (rect.right - 168) - detail_left)
            draw_text(surface, fonts.small,
                      truncate(fonts.small, info.title, name_width),
                      (rect.left + 20, y), theme.TEXT)
            colour = theme.NEGATIVE if info.damaged else (
                theme.TEXT_MUTED if info.exists else theme.TEXT_FAINT
            )
            if detail_width >= 40:
                draw_text(surface, fonts.small,
                          truncate(fonts.small, info.describe(), detail_width),
                          (detail_left, y), colour)

            if saves.slot == info.slot:
                # The slot this game lives in, so the player can see at a glance
                # where an autosave is going. It sits beside the buttons rather
                # than beside the name, which has the row's width to itself.
                draw_text(surface, fonts.tiny, "THIS GAME", (rect.right - 158, y + 2),
                          theme.ACCENT, align="right")
            save_button = self._slot_button(info.slot, "save", "Save")
            save_button.draw(surface, pygame.Rect(rect.right - 150, y - 6, 58, 24),
                             fonts, mouse)
            self._slot_buttons.append((info.slot, "save", save_button))
            load_button = self._slot_button(info.slot, "load", "Load")
            load_button.enabled = info.exists
            load_button.draw(surface, pygame.Rect(rect.right - 84, y - 6, 58, 24), fonts, mouse)
            self._slot_buttons.append((info.slot, "load", load_button))
            y += 34
