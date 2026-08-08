"""Market pages.

Design Bible V4.15 lets the player view current prices, historical prices,
company information, market statistics and industry information. V14.8 makes
lists searchable, sortable and paginated, opened with a single click.
"""

from __future__ import annotations

import pygame

from ... import engine as _engine  # noqa: F401  (keeps import order stable)
from .. import theme
from ..widgets import Card, Column, SearchBox, Table, draw_text, panel
from .base import Page


def _price(value) -> str:
    return value.format() if value is not None else "—"


def _percent(value) -> str:
    return value.format(signed=True) if value is not None else "—"


def _change_colour(value):
    if value is None or value.is_zero:
        return theme.TEXT_MUTED
    return theme.value_colour(not value.is_negative)


class MarketPage(Page):
    """Every listed company (V4.3, V4.15)."""

    key = "market"
    title = "Market"
    subtitle = "Every listed company in the world"

    def __init__(self, context):
        super().__init__(context)
        self.search = SearchBox("Search companies")
        self.table = Table(
            columns=[
                Column("name", "Company", 260),
                Column("industry", "Industry", 150),
                Column("price", "Price", 110, align="right", numeric=True, format=_price),
                Column("change", "Today", 90, align="right", numeric=True,
                       format=_percent, colour=_change_colour),
                Column("cap", "Market cap", 140, align="right", numeric=True,
                       format=lambda v: v.format(decimals=0)),
                Column("ceo", "Chief executive", 180),
            ],
            search_key="name",
            # Sorted by size on arrival: the largest companies are the ones a
            # player is most likely to be looking for first.
            sort_key="cap",
            sort_descending=True,
        )
        self.selected_company_id: str | None = None

    def rows(self) -> list[dict]:
        market, world = self.context.market, self.context.world
        if market is None or world is None:
            return []
        rows = []
        for listing in market.active_listings():
            company = world.company_by_id(listing.company_id)
            if company is None:
                continue
            ceo = world.person_by_id(company.ceo_id)
            rows.append({
                "id": company.id,
                "name": company.name,
                "industry": company.industry.value,
                "price": listing.price,
                "change": listing.daily_change(),
                "cap": listing.market_cap,
                "ceo": ceo.name if ceo else "—",
            })
        return rows

    def cards(self):
        market, economy = self.context.market, self.context.economy
        if market is None:
            return []
        gainers, losers = market.top_movers(1)
        mood = "Bull market" if market.is_bull_market() else (
            "Bear market" if market.is_bear_market() else "Steady"
        )
        cards = [
            Card("Market index", f"{market.market_index():,.0f}", mood),
            Card("Listed companies", str(len(market.active_listings())),
                 "Companies trading today"),
        ]
        if gainers:
            company = self.context.world.company_by_id(gainers[0].company_id)
            cards.append(Card("Top gainer", company.name if company else "—",
                              gainers[0].daily_change().format(signed=True),
                              accent=theme.POSITIVE))
        if losers:
            company = self.context.world.company_by_id(losers[0].company_id)
            cards.append(Card("Top faller", company.name if company else "—",
                              losers[0].daily_change().format(signed=True),
                              accent=theme.NEGATIVE))
        if economy is not None and len(cards) < 4:
            cards.append(Card("Economy", str(economy.state), economy.describe()))
        return cards

    def handle_event(self, event) -> bool:
        if self.search.handle_event(event):
            self.table.page = 0
            return True
        if self.table.handle_event(event):
            row = self.table.take_opened()
            if row is not None:
                self.selected_company_id = row["id"]
                self.navigate_to = "market:company"
            return True
        return False

    def draw_content(self, surface, rect, fonts, mouse) -> None:
        self.table.draw(surface, rect, fonts, mouse, self.rows(), self.search.text)


class CompanyDetailPage(Page):
    """One listed company in detail (V4.15)."""

    key = "market:company"

    def __init__(self, context, market_page: MarketPage):
        super().__init__(context)
        self.market_page = market_page

    @property
    def title(self) -> str:
        """The company's own name, so the page is about a company rather than
        generically titled "Company" — which would also collide with the
        player's own company page."""
        company = self.company
        return company.name if company else "Company"

    @property
    def company(self):
        world = self.context.world
        if world is None or self.market_page.selected_company_id is None:
            return None
        return world.company_by_id(self.market_page.selected_company_id)

    @property
    def listing(self):
        market = self.context.market
        company = self.company
        if market is None or company is None:
            return None
        return market.listing_for(company.id)

    def breadcrumb(self):
        company = self.company
        return [("Market", "market"), (company.name if company else "Company", self.key)]

    def cards(self):
        listing, company = self.listing, self.company
        if listing is None or company is None:
            return []
        return [
            Card("Share price", listing.price.format(),
                 f"{listing.daily_change().format(signed=True)} today",
                 accent=_change_colour(listing.daily_change())),
            Card("Market cap", listing.market_cap.format(decimals=0), company.industry.value),
            Card("Since last week", listing.change_over(7).format(signed=True),
                 "Seven days of trading",
                 accent=_change_colour(listing.change_over(7))),
            Card("Since last year", listing.change_over(336).format(signed=True),
                 "One year of trading",
                 accent=_change_colour(listing.change_over(336))),
        ]

    def draw_content(self, surface, rect, fonts, mouse) -> None:
        company, listing = self.company, self.listing
        if company is None or listing is None:
            draw_text(surface, fonts.body, "Select a company from the Market.",
                      (rect.left, rect.top + 20), theme.TEXT_MUTED)
            return

        left = pygame.Rect(rect.left, rect.top, int(rect.width * 0.58), 250)
        panel(surface, left)
        draw_text(surface, fonts.subheading, company.name, (left.left + 20, left.top + 18))
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
            draw_text(surface, fonts.small, label, (left.left + 20, y), theme.TEXT_MUTED)
            draw_text(surface, fonts.small, value, (left.right - 20, y), theme.TEXT,
                      align="right")
            y += 26

        right = pygame.Rect(left.right + theme.GAP, rect.top,
                            rect.width - left.width - theme.GAP, 250)
        panel(surface, right)
        draw_text(surface, fonts.subheading, "Why the price moved",
                  (right.left + 20, right.top + 18))
        market = self.context.market
        explanation = market.explain(company.id) if market else ""
        _wrap(surface, fonts.small, explanation,
              pygame.Rect(right.left + 20, right.top + 52, right.width - 40, 60),
              theme.TEXT_MUTED)

        change = listing.last_change
        contributions = [
            ("Company performance", change.performance),
            ("Industry conditions", change.industry),
            ("Economic conditions", change.economy),
            ("Market sentiment", change.sentiment),
            ("Supply and demand", change.supply_demand),
            ("Ordinary variation", change.variation),
        ]
        y = right.top + 118
        for label, value in contributions:
            draw_text(surface, fonts.small, label, (right.left + 20, y), theme.TEXT_MUTED)
            draw_text(surface, fonts.mono_small, value.format(signed=True, decimals=3),
                      (right.right - 20, y), _change_colour(value), align="right")
            y += 21


def _wrap(surface, font, text, rect, colour):
    words, line, y = str(text).split(), "", rect.top
    for word in words:
        candidate = f"{line} {word}".strip()
        if font.size(candidate)[0] <= rect.width or not line:
            line = candidate
            continue
        draw_text(surface, font, line, (rect.left, y), colour)
        y += font.get_height() + 3
        line = word
    if line:
        draw_text(surface, font, line, (rect.left, y), colour)
