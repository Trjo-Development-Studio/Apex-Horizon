"""Buying a company outright: the list, and one purchase in detail.

Split out of the subsidiaries pages (2026-08-10) to keep each file within the
size the project works to. Buying lives here (project manager ruling,
2026-08-10); :mod:`.subsidiaries` owns the companies already bought.
"""

from __future__ import annotations

import pygame

from .. import theme
from ..charts import line_chart
from ..widgets import Button, Card, Column, SearchBox, Table, draw_text, panel
from .base import Page, no_company_message
from .subsidiaries import SubsidiariesPage


class SubsidiariesBuyPage(Page):
    """Companies the player's company could acquire outright (V12.4, V12.9).

    The dedicated purchase flow (project manager ruling, 2026-08-10): buying
    happens here, at Company → Subsidiaries → Buy, rather than from the
    Market. It reads the same market listings the Market page does and calls
    the same :class:`~apex_horizon.engine.acquisitions.subsidiaries.
    SubsidiaryBook` the Market's old Acquire button called — nothing about
    the acquisition itself is duplicated, only where the player reaches it.
    """

    key = "company:subsidiaries:buy"
    TITLE = "Buy a Subsidiary"
    SUBTITLE = "Acquire another company outright, in company cash"

    def __init__(self, context, list_page: SubsidiariesPage):
        super().__init__(context)
        self.list_page = list_page
        self.search = SearchBox("Search companies")
        self.table = Table(
            columns=[
                Column("name", "Company", 240),
                Column("industry", "Industry", 150),
                Column("cap", "Market cap", 140, align="right", numeric=True,
                       format=lambda v: v.format(decimals=0)),
                Column("cost", "Cost to acquire", 150, align="right", numeric=True,
                       format=lambda v: v.format(decimals=0)),
            ],
            search_key="name",
            sort_key="cost",
        )
        self.selected_company_id: str | None = None

    @property
    def book(self):
        if not self.context.has_company:
            return None
        return self.context.company.subsidiaries

    def breadcrumb(self):
        return [("Company", "company"), ("Subsidiaries", "company:subsidiaries"),
                ("Buy", self.key)]

    def rows(self) -> list[dict]:
        book = self.book
        market, world = self.context.market, self.context.world
        if book is None or market is None or world is None:
            return []
        company = self.context.company
        rows = []
        for listing in market.active_listings():
            if listing.company_id == company.id:
                continue
            record = world.company_by_id(listing.company_id)
            cost = book.price_of(listing.company_id)
            if record is None or cost is None:
                continue
            rows.append({
                "id": record.id,
                "name": record.name,
                "industry": record.industry.value,
                "cap": listing.market_cap,
                "cost": cost,
            })
        return rows

    def handle_event(self, event) -> bool:
        if self.search is not None and self.search.handle_event(event):
            self.table.page = 0
            return True
        if self.table.handle_event(event):
            opened = self.table.take_opened()
            if opened:
                self.selected_company_id = opened["id"]
                self.navigate_to = "company:subsidiaries:buy:company"
            return True
        return super().handle_event(event)

    def draw_content(self, surface, rect, fonts, mouse) -> None:
        book = self.book
        if book is None:
            panel(surface, pygame.Rect(rect.left, rect.top, rect.width, 160))
            draw_text(surface, fonts.body, no_company_message(self.context, "to buy one"),
                      (rect.left + 24, rect.top + 60), theme.TEXT_MUTED)
            return
        if not book.unlocked:
            panel(surface, pygame.Rect(rect.left, rect.top, rect.width, 160))
            draw_text(surface, fonts.body, "Subsidiaries has not been unlocked yet.",
                      (rect.left + 24, rect.top + 60), theme.TEXT_MUTED)
            return
        self.table.draw(surface, rect, fonts, mouse, self.rows(),
                        self.search.text if self.search else "",
                        empty_message="No companies are available to acquire right now.")


class SubsidiaryPurchaseDetailPage(Page):
    """One acquirable company in detail, with the option to buy it outright."""

    key = "company:subsidiaries:buy:company"

    def __init__(self, context, buy_page: SubsidiariesBuyPage):
        super().__init__(context)
        self.buy_page = buy_page
        self.acquire_button = Button("Acquire", primary=True)
        #: Set when the player asks to buy this company outright (V12.4).
        self.acquire_request: str | None = None

    @property
    def company(self):
        world = self.context.world
        if world is None or self.buy_page.selected_company_id is None:
            return None
        return world.company_by_id(self.buy_page.selected_company_id)

    @property
    def listing(self):
        market, company = self.context.market, self.company
        if market is None or company is None:
            return None
        return market.listing_for(company.id)

    @property
    def title(self) -> str:
        company = self.company
        return company.name if company else "Company"

    def breadcrumb(self):
        company = self.company
        return [
            ("Company", "company"), ("Subsidiaries", "company:subsidiaries"),
            ("Buy", "company:subsidiaries:buy"),
            (company.name if company else "Company", self.key),
        ]

    def take_acquire_request(self) -> str | None:
        request, self.acquire_request = self.acquire_request, None
        return request

    def handle_event(self, event) -> bool:
        company = self.company
        if company is None:
            return super().handle_event(event)
        if self.acquire_button.enabled and self.acquire_button.handle_event(event) \
                and self.acquire_button.take_click():
            self.acquire_request = company.id
            return True
        return super().handle_event(event)

    def cards(self) -> list[Card]:
        listing, company = self.listing, self.company
        book = getattr(self.context.company, "subsidiaries", None)
        if listing is None or company is None or book is None:
            return []
        price = book.price_of(company.id)
        return [
            Card("Cost to acquire", price.format(decimals=0) if price else "—",
                 "Paid in full, from company cash"),
            Card("Market cap", listing.market_cap.format(decimals=0), company.industry.value),
            Card("Share price", listing.price.format(),
                 f"{listing.daily_change().format(signed=True)} today"),
        ]

    def draw_content(self, surface, rect, fonts, mouse) -> None:
        company, listing = self.company, self.listing
        if company is None or listing is None:
            draw_text(surface, fonts.body, "Select a company from the list.",
                      (rect.left, rect.top + 20), theme.TEXT_MUTED)
            return

        # Clamped like every other fixed-height panel (V27.7): the Acquire
        # button lives at the bottom of `right`, and must not be pushed
        # under the notification stack on a short window.
        purchase_height = max(0, min(260, rect.height))
        left = pygame.Rect(rect.left, rect.top, int(rect.width * 0.58), purchase_height)
        panel(surface, left)
        draw_text(surface, fonts.subheading, "The business", (left.left + 20, left.top + 18))
        world = self.context.world
        ceo = world.person_by_id(company.ceo_id) if world else None
        city = world.city_by_id(company.headquarters_id) if world else None
        details = [
            ("Industry", company.industry.value),
            ("Chief executive", ceo.name if ceo else "—"),
            ("Headquarters", city.name if city else "—"),
            ("Shares in issue", f"{listing.shares_outstanding:,}"),
            ("Identifier", company.id),
        ]
        y = left.top + 56
        for label, value in details:
            if y + 20 > left.bottom - 8:
                break
            draw_text(surface, fonts.small, label, (left.left + 20, y), theme.TEXT_MUTED)
            draw_text(surface, fonts.small, str(value), (left.right - 20, y), theme.TEXT,
                      align="right")
            y += 26

        right = pygame.Rect(left.right + theme.GAP, rect.top,
                            rect.width - left.width - theme.GAP, purchase_height)
        panel(surface, right)
        draw_text(surface, fonts.subheading, "Acquire outright", (right.left + 20, right.top + 18))
        draw_text(surface, fonts.small,
                  "Paid in full from company cash, with no financing (V12.22).",
                  (right.left + 20, right.top + 48), theme.TEXT_MUTED)

        book = getattr(self.context.company, "subsidiaries", None)
        # Deliberately "is not None", not truthiness: SubsidiaryBook defines
        # __len__, so a company with zero subsidiaries so far — exactly the
        # position anyone buying their first is in — would otherwise read as
        # falsy and silently disable the button (bug fix, 2026-08-10).
        allowed, reason = book.can_acquire(company.id) if book is not None else (False, "")
        price = book.price_of(company.id) if book is not None else None
        if price is not None:
            draw_text(surface, fonts.body, f"Cost: {price.format(decimals=0)}",
                      (right.left + 20, right.top + 88), theme.TEXT)
        if not allowed and reason:
            draw_text(surface, fonts.small, reason,
                      (right.left + 20, right.top + 120), theme.NEGATIVE)
        self.acquire_button.enabled = allowed
        self.acquire_button.draw(
            surface, pygame.Rect(right.right - 104, right.bottom - 46, 84, 34), fonts, mouse)

        remaining = rect.bottom - left.bottom - theme.GAP
        if remaining >= 110:
            self._draw_history(surface, pygame.Rect(
                rect.left, left.bottom + theme.GAP, rect.width, remaining), fonts, listing)

    def _draw_history(self, surface, rect, fonts, listing) -> None:
        panel(surface, rect)
        draw_text(surface, fonts.subheading, "Price history", (rect.left + 20, rect.top + 16))
        closes = [float(price.amount) for price in listing.history]
        draw_text(surface, fonts.small, f"{len(closes):,} days of trading",
                  (rect.right - 20, rect.top + 20), theme.TEXT_FAINT, align="right")
        line_chart(surface, pygame.Rect(rect.left + 20, rect.top + 52,
                                        rect.width - 40, rect.height - 72),
                   fonts, closes)
