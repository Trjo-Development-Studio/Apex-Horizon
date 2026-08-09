"""Market pages.

Design Bible V4.15 lets the player view current prices, historical prices,
company information, market statistics and industry information. V14.8 makes
lists searchable, sortable and paginated, opened with a single click.
"""

from __future__ import annotations

import pygame

from ... import engine as _engine  # noqa: F401  (keeps import order stable)
from .. import theme
from ..charts import bars, line_chart
from ..widgets import Button, Card, Column, SearchBox, Table, draw_text, panel
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
    TITLE = "Market"
    SUBTITLE = "Every listed company in the world"

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
            # No sort by default: the list keeps the order the world generated
            # the companies in, so a company stays where the player last saw it
            # rather than moving every time a price ticks. Sorting is applied
            # only when the player asks for it by clicking a column (V27.3).
            sort_key=None,
            sort_descending=False,
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
        period = market.top_mover_period
        mood = "Bull market" if market.is_bull_market() else (
            "Bear market" if market.is_bear_market() else "Steady"
        )
        cards = [
            Card("Market index", f"{market.market_index():,.0f}", mood),
            Card("Listed companies", str(len(market.active_listings())),
                 "Companies trading today"),
        ]
        # On a day when everything fell there is no top gainer, and saying so is
        # the honest answer: the least bad loser is not a gainer.
        best = market.top_gainer()
        if best is not None:
            company = self.context.world.company_by_id(best.company_id)
            cards.append(Card(
                "Top gainer", company.name if company else "—",
                f"{market.change_over_period(best).format(signed=True)} "
                f"over {period} days",
                accent=theme.POSITIVE, trend=True))
        elif market.active_listings():
            cards.append(Card("Top gainer", "None",
                              f"Nothing rose over {period} days"))

        worst = market.top_loser()
        if worst is not None:
            company = self.context.world.company_by_id(worst.company_id)
            cards.append(Card(
                "Top loser", company.name if company else "—",
                f"{market.change_over_period(worst).format(signed=True)} "
                f"over {period} days",
                accent=theme.NEGATIVE, trend=False))
        elif market.active_listings():
            cards.append(Card("Top loser", "None",
                              f"Nothing fell over {period} days"))
        if economy is not None and len(cards) < 4:
            cards.append(Card("Economy", str(economy.state), economy.describe()))
        return cards

    def handle_event(self, event) -> bool:
        if self.search is not None and self.search.handle_event(event):
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
        self.table.draw(surface, rect, fonts, mouse, self.rows(), self.search.text if self.search else "")


#: Tall enough for all seven causes V4.4 lists, so none is cut off.
DETAIL_HEIGHT = 262


class CompanyDetailPage(Page):
    """One listed company in detail (V4.15)."""

    key = "market:company"

    def __init__(self, context, market_page: MarketPage):
        super().__init__(context)
        self.market_page = market_page
        self.buy_button = Button("Buy", primary=True)
        self.sell_button = Button("Sell")
        self.acquire_button = Button("Acquire")
        #: Set when the player asks to buy this company outright (V12.4).
        self.acquire_request: str | None = None
        #: Set to ("buy"|"sell", company_id) when the player asks to trade.
        self.trade_request: tuple[str, str] | None = None

    def take_trade_request(self) -> tuple[str, str] | None:
        request, self.trade_request = self.trade_request, None
        return request

    def take_acquire_request(self) -> str | None:
        request, self.acquire_request = self.acquire_request, None
        return request

    def handle_event(self, event) -> bool:
        company = self.company
        if company is None:
            return super().handle_event(event)
        if self.buy_button.enabled and self.buy_button.handle_event(event) \
                and self.buy_button.take_click():
            self.trade_request = ("buy", company.id)
            return True
        if self.sell_button.enabled and self.sell_button.handle_event(event) \
                and self.sell_button.take_click():
            self.trade_request = ("sell", company.id)
            return True
        if self.acquire_button.enabled and self.acquire_button.handle_event(event) \
                and self.acquire_button.take_click():
            self.acquire_request = company.id
            return True
        return super().handle_event(event)

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
            _period_card("Since last week", listing.change_over(7),
                         "Seven days of trading", "Listed less than a week ago"),
            _period_card("Since last year", listing.change_over(336),
                         "One year of trading", "Listed less than a year ago"),
        ]

    def draw_content(self, surface, rect, fonts, mouse) -> None:
        company, listing = self.company, self.listing
        if company is None or listing is None:
            draw_text(surface, fonts.body, "Select a company from the Market.",
                      (rect.left, rect.top + 20), theme.TEXT_MUTED)
            return

        left = pygame.Rect(rect.left, rect.top, int(rect.width * 0.58), DETAIL_HEIGHT)
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
                            rect.width - left.width - theme.GAP, DETAIL_HEIGHT)
        panel(surface, right)
        draw_text(surface, fonts.subheading, "Why the price moved",
                  (right.left + 20, right.top + 18))
        market = self.context.market
        explanation = market.explain(company.id) if market else ""
        _wrap(surface, fonts.small, explanation,
              pygame.Rect(right.left + 20, right.top + 52, right.width - 40, 60),
              theme.TEXT_MUTED)

        # V4.21 wants a move to be explainable, and seven signed percentages to
        # three decimal places is a readout rather than an explanation. Drawn as
        # bars against each other, which pushed the price and which barely
        # mattered is legible at a glance. This is a sub-page the player opened
        # deliberately, which is where V14.7 places charts.
        change = listing.last_change
        contributions = [
            ("Performance", float(change.performance.fraction)),
            ("Industry", float(change.industry.fraction)),
            ("Economy", float(change.economy.fraction)),
            ("News", float(change.news.fraction)),
            ("Sentiment", float(change.sentiment.fraction)),
            ("Supply and demand", float(change.supply_demand.fraction)),
            ("Variation", float(change.variation.fraction)),
        ]
        bars(surface, pygame.Rect(right.left + 20, right.top + 112,
                                  right.width - 40, right.height - 128),
             fonts, contributions, label_width=146,
             value_format=lambda value: f"{value:+.2%}")

        remaining = rect.bottom - left.bottom - theme.GAP
        history_height = min(190, max(0, remaining - 150 - theme.GAP))
        if history_height >= 110:
            self._draw_history(surface, pygame.Rect(
                rect.left, left.bottom + theme.GAP, rect.width, history_height),
                fonts, listing)
            trading_top = left.bottom + theme.GAP + history_height + theme.GAP
        else:
            trading_top = left.bottom + theme.GAP

        trading = pygame.Rect(rect.left, trading_top, rect.width,
                              max(0, min(150, rect.bottom - trading_top)))
        if trading.height >= 90:
            self._draw_trading(surface, trading, fonts, mouse, listing)

    def _draw_history(self, surface, rect, fonts, listing) -> None:
        """What the share has actually done (V4.15, V14.7).

        The market keeps two years of closes for every company and, until now,
        showed the player one of them. A price is a shape, and the shape is the
        thing a decision is made on.
        """
        panel(surface, rect)
        draw_text(surface, fonts.subheading, "Price history",
                  (rect.left + 20, rect.top + 16))
        closes = [float(price.amount) for price in listing.history]
        draw_text(surface, fonts.small,
                  f"{len(closes):,} days of trading",
                  (rect.right - 20, rect.top + 20), theme.TEXT_FAINT, align="right")
        line_chart(surface, pygame.Rect(rect.left + 20, rect.top + 52,
                                        rect.width - 40, rect.height - 72),
                   fonts, closes)

    def _draw_trading(self, surface, rect, fonts, mouse, listing) -> None:
        """Buying and selling with the player's own money (V1.19, V3.4).

        This is personal trading, not the company's: it spends personal cash and
        the shares are the player's own. The company invests through its
        employees on the Investments page, which is a separate operation with
        separate money (V1.4).
        """
        panel(surface, rect)
        draw_text(surface, fonts.subheading, "Your position",
                  (rect.left + 20, rect.top + 16))

        portfolio = self.context.portfolio
        player = self.context.player
        if portfolio is None or player is None:
            draw_text(surface, fonts.small, "Personal trading is unavailable.",
                      (rect.left + 20, rect.top + 52), theme.TEXT_FAINT)
            return

        holding = portfolio.holding_for(listing.company_id)
        shares = holding.shares if holding else 0
        if holding is not None:
            gain = holding.unrealised(listing.price)
            facts = [
                ("Shares held", f"{shares:,}"),
                ("Value", holding.value_at(listing.price).format(decimals=0)),
                ("Average cost", holding.average_price.format()),
                ("Unrealised", gain.format(decimals=0, signed=True)),
            ]
        else:
            facts = [
                ("Shares held", "None"),
                ("Personal cash", player.cash.format(decimals=0)),
                ("You could buy", f"{portfolio.max_affordable(listing.company_id):,} shares"),
            ]
        x = rect.left + 20
        for label, value in facts:
            draw_text(surface, fonts.small, label, (x, rect.top + 52), theme.TEXT_MUTED)
            draw_text(surface, fonts.body, value, (x, rect.top + 72), theme.TEXT)
            x += 170

        self.buy_button.enabled = portfolio.max_affordable(listing.company_id) > 0
        self.sell_button.enabled = shares > 0
        self.buy_button.draw(surface, pygame.Rect(rect.right - 200, rect.top + 56, 84, 34),
                             fonts, mouse)
        self.sell_button.draw(surface, pygame.Rect(rect.right - 104, rect.top + 56, 84, 34),
                              fonts, mouse)

        # Buying the whole company is a different decision from buying shares
        # (V12.12), so it sits here beside them rather than on another screen.
        book = getattr(self.context.company, "subsidiaries", None)
        if book is None:
            self.acquire_button.enabled = False
            return
        price = book.price_of(listing.company_id)
        allowed, _ = book.can_acquire(listing.company_id)
        self.acquire_button.enabled = allowed
        if price is not None:
            draw_text(surface, fonts.small,
                      f"Acquire outright: {price.format(decimals=0)}",
                      (rect.right - 200, rect.bottom - 30), theme.TEXT_FAINT,
                      align="right")
        self.acquire_button.draw(
            surface, pygame.Rect(rect.right - 104, rect.bottom - 40, 84, 30), fonts, mouse
        )


def _period_card(title: str, change, note: str, missing: str) -> Card:
    """A change over time, or an honest dash when it cannot be known yet."""
    if change is None:
        return Card(title, "—", missing)
    return Card(title, change.format(signed=True), note, accent=_change_colour(change))


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
