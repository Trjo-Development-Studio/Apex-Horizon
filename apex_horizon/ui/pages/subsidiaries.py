"""Subsidiaries: the list, and one company in detail.

V12.9 asks for a dedicated Subsidiaries page holding a searchable list of every
owned company, where a single click opens one — never a double click. V12.8 then
wants that page to show the company's information, financial statistics, market
value, historical performance and general details.

The list is an ordinary :class:`~apex_horizon.ui.widgets.Table`, so it searches,
sorts and paginates exactly as every other list in the game does (V14.20,
V14.28) — a corporate group should not need its own conventions.
"""

from __future__ import annotations

import pygame

from ...engine.values import Money
from .. import theme
from ..widgets import Button, Card, Column, SearchBox, Table, draw_text, panel, truncate
from .base import Page, no_company_message


def _return_colour(value) -> tuple[int, int, int]:
    return theme.value_colour(not value.is_negative)


class SubsidiariesPage(Page):
    """Every company the player's company owns (V12.9)."""

    key = "company:subsidiaries"
    TITLE = "Subsidiaries"
    SUBTITLE = "The companies your company owns outright"

    def __init__(self, context):
        super().__init__(context)
        self.search = SearchBox("Search subsidiaries")
        self.table = Table(
            columns=[
                Column("name", "Company", 260),
                Column("industry", "Industry", 150),
                Column("value", "Value", 130, align="right", numeric=True,
                       format=lambda v: v.format(decimals=0)),
                Column("income", "Income paid", 130, align="right", numeric=True,
                       format=lambda v: v.format(decimals=0)),
                Column("gain", "Return", 110, align="right", numeric=True,
                       format=lambda v: v.format(signed=True),
                       colour=_return_colour),
            ],
            search_key="name",
            sort_key="value",
            sort_descending=True,
        )
        #: Set when a row is opened, so the application can navigate (V12.9).
        self.selected_company_id: str | None = None
        #: Buying happens on its own page (Company -> Subsidiaries -> Buy),
        #: not the Market (project manager ruling, 2026-08-10) — this button
        #: only navigates there.
        self.buy_button = Button("Buy a company", primary=True)
        self.requested_buy = False

    @property
    def book(self):
        """The subsidiaries this company owns, or ``None`` without one operating.

        A bankrupt company must not read as still able to buy or manage a
        group, so this checks
        :attr:`~apex_horizon.ui.context.GameContext.has_company` rather than
        just that a company object exists.
        """
        if not self.context.has_company:
            return None
        return self.context.company.subsidiaries

    def breadcrumb(self):
        return [("Company", "company"), ("Subsidiaries", self.key)]

    def take_buy_request(self) -> bool:
        request, self.requested_buy = self.requested_buy, False
        return request

    def rows(self) -> list[dict]:
        book = self.book
        if book is None:
            return []
        return [
            {
                "id": subsidiary.company_id,
                "name": subsidiary.name,
                "industry": subsidiary.industry,
                "value": subsidiary.valuation,
                "income": subsidiary.lifetime_income,
                "gain": subsidiary.return_since_purchase(),
            }
            for subsidiary in book
        ]

    def cards(self) -> list[Card]:
        book = self.book
        if book is None:
            return []
        paid = Money.zero()
        for subsidiary in book:
            paid = paid + subsidiary.purchase_price
        return [
            Card("Owned", str(len(book)), "Companies in the group"),
            Card("Group value", book.total_value().format(decimals=0),
                 "Counts toward your company's worth"),
            Card("Income paid", book.total_income().format(decimals=0),
                 "Since each was acquired"),
            Card("Spent acquiring", paid.format(decimals=0), "Total purchase prices"),
        ]

    def handle_event(self, event) -> bool:
        book = self.book
        if (book is not None and book.unlocked and self.buy_button.handle_event(event)
                and self.buy_button.take_click()):
            self.requested_buy = True
            return True
        if self.table.handle_event(event):
            opened = self.table.take_opened()
            if opened:
                self.selected_company_id = opened["id"]
                self.navigate_to = "company:subsidiary"
            return True
        return super().handle_event(event)

    def draw_content(self, surface, rect, fonts, mouse) -> None:
        book = self.book
        if book is None:
            panel(surface, pygame.Rect(rect.left, rect.top, rect.width, 160))
            draw_text(surface, fonts.body, no_company_message(self.context, "to build a group"),
                      (rect.left + 24, rect.top + 60), theme.TEXT_MUTED)
            return
        if not len(book):
            # Clamped like every other fixed-height panel (V27.7): this box
            # carries the only "Buy a company" button reachable when the
            # player owns nothing yet — the same bootstrapping spot the
            # earlier reachability bug fix (2026-08-10) covered, so it must
            # not be pushed under the notification stack on a short window.
            box = pygame.Rect(rect.left, rect.top, rect.width, max(0, min(200, rect.height)))
            panel(surface, box)
            if box.height < 24:
                return
            if book.unlocked:
                headline = "Your company owns nothing yet."
                body = ("Acquire a company outright to build a group. Acquisitions "
                        "are paid for in company cash, in full.")
            else:
                headline = "Subsidiaries has not been unlocked yet."
                body = ("Unlock Subsidiaries in the Unlock Tree, past Investment "
                        "Funds, to start acquiring companies outright.")
            draw_text(surface, fonts.body, headline, (box.centerx, box.top + 24),
                      theme.TEXT_MUTED, align="center", baseline="middle")
            # The button gets first claim on whatever room is left, the same
            # priority the Employee department bar already gives Candidates
            # (2026-08): descriptive text is what gives way under pressure,
            # not the only path to buying a first subsidiary.
            if book.unlocked and box.height >= 78:
                button_rect = pygame.Rect(box.centerx - 90, box.bottom - 52, 180, 36)
                if box.height >= 118:
                    draw_text(surface, fonts.small, body, (box.centerx, box.top + 56),
                              theme.TEXT_FAINT, align="center", baseline="middle")
                self.buy_button.draw(surface, button_rect, fonts, mouse)
            elif box.height >= 56:
                draw_text(surface, fonts.small, body, (box.centerx, box.top + 56),
                          theme.TEXT_FAINT, align="center", baseline="middle")
            return

        if book.unlocked:
            self.buy_button.draw(
                surface, pygame.Rect(rect.right - 150, rect.top - 44, 140, 34), fonts, mouse)
        self.table.draw(surface, rect, fonts, mouse, self.rows(),
                        self.search.text if self.search else "")


class SubsidiaryDetailPage(Page):
    """One subsidiary in detail (V12.8)."""

    key = "company:subsidiary"

    def __init__(self, context, list_page: SubsidiariesPage):
        super().__init__(context)
        self.list_page = list_page

    @property
    def subsidiary(self):
        book = self.list_page.book
        if book is None or self.list_page.selected_company_id is None:
            return None
        return book.by_id(self.list_page.selected_company_id)

    @property
    def title(self) -> str:
        subsidiary = self.subsidiary
        return subsidiary.name if subsidiary else "Subsidiary"

    @property
    def subtitle(self) -> str:
        subsidiary = self.subsidiary
        return f"{subsidiary.industry} · owned outright" if subsidiary else ""

    def breadcrumb(self):
        subsidiary = self.subsidiary
        return [
            ("Company", "company"),
            ("Subsidiaries", "company:subsidiaries"),
            (subsidiary.name if subsidiary else "Subsidiary", self.key),
        ]

    def cards(self) -> list[Card]:
        subsidiary = self.subsidiary
        if subsidiary is None:
            return []
        gain = subsidiary.return_since_purchase()
        return [
            Card("Value", subsidiary.valuation.format(decimals=0), "What it is worth now"),
            Card("Paid", subsidiary.purchase_price.format(decimals=0), "When acquired"),
            Card("Income paid", subsidiary.lifetime_income.format(decimals=0),
                 "To your company, in total"),
            Card("Return", gain.format(signed=True), "Value and income against price",
                 accent=_return_colour(gain)),
        ]

    def draw_content(self, surface, rect, fonts, mouse) -> None:
        subsidiary = self.subsidiary
        if subsidiary is None:
            draw_text(surface, fonts.body, "Select a subsidiary from the list.",
                      (rect.left, rect.top + 20), theme.TEXT_MUTED)
            return

        column = (rect.width - theme.GAP) // 2
        # Clamped to what the page actually has, same as Dashboard/Employees:
        # the notification stack reserves real space at the bottom (V27.7).
        panel_height = max(0, min(250, rect.height))
        details = pygame.Rect(rect.left, rect.top, column, panel_height)
        panel(surface, details)
        draw_text(surface, fonts.subheading, "The business",
                  (details.left + 20, details.top + 18))

        world = self.context.world
        record = world.company_by_id(subsidiary.company_id) if world else None
        city = world.city_by_id(record.headquarters_id) if world and record else None
        ceo = world.person_by_id(record.ceo_id) if world and record else None
        engine = self.context.engine
        owned_days = (engine.date.day - subsidiary.acquired_on_day) if engine else 0
        lines = [
            ("Industry", subsidiary.industry),
            ("Chief executive", ceo.name if ceo else "—"),
            ("Headquarters", city.name if city else "—"),
            ("Acquired on day", f"{subsidiary.acquired_on_day:,}"),
            ("Owned for", f"{owned_days:,} days"),
            ("Identifier", subsidiary.company_id),
        ]
        y = details.top + 56
        for label, value in lines:
            if y + 20 > details.bottom - 8:
                break
            draw_text(surface, fonts.small, label, (details.left + 20, y), theme.TEXT_MUTED)
            draw_text(surface, fonts.small, truncate(fonts.small, str(value), column - 180),
                      (details.right - 20, y), theme.TEXT, align="right")
            y += 26

        money = pygame.Rect(details.right + theme.GAP, rect.top,
                            rect.width - column - theme.GAP, panel_height)
        panel(surface, money)
        draw_text(surface, fonts.subheading, "How it has done",
                  (money.left + 20, money.top + 18))
        draw_text(surface, fonts.small,
                  "A subsidiary keeps operating in its own industry and pays its "
                  "share up to your company each month.",
                  (money.left + 20, money.top + 48), theme.TEXT_MUTED)

        gain = subsidiary.return_since_purchase()
        figures = [
            ("Purchase price", subsidiary.purchase_price.format(decimals=0), theme.TEXT),
            ("Value today", subsidiary.valuation.format(decimals=0), theme.TEXT),
            ("Income paid to date", subsidiary.lifetime_income.format(decimals=0),
             theme.POSITIVE),
            ("Total return", gain.format(signed=True), _return_colour(gain)),
        ]
        y = money.top + 96
        for label, value, colour in figures:
            if y + 20 > money.bottom - 8:
                break
            draw_text(surface, fonts.small, label, (money.left + 20, y), theme.TEXT_MUTED)
            draw_text(surface, fonts.mono_small, value, (money.right - 20, y), colour,
                      align="right")
            y += 28
