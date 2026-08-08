"""Investment funds: the list, and one fund in detail.

V11.13 asks for every fund to have its own management page showing current and
historical performance, assets under management, active investments and general
statistics. V11.6 wants funds to feel like separate financial products rather
than accounts, which is why each one is opened by name and reads as its own
thing rather than as a row of the company's balance sheet.

The clearest single fact these pages have to convey is whose money this is. V11.5
is unambiguous — it belongs to the fund's investors, not the player and not the
company — so assets under management are never presented as company wealth. What
the company earns is the fee, and that is shown separately.
"""

from __future__ import annotations

import pygame

from ...engine.values import Percentage
from .. import theme
from ..widgets import Button, Card, Column, SearchBox, Table, draw_text, panel, truncate
from .base import Page


def _return_colour(value) -> tuple[int, int, int]:
    return theme.value_colour(not value.is_negative)


class FundsPage(Page):
    """Every fund the company manages (V11.7)."""

    key = "company:funds"
    title = "Investment Funds"
    subtitle = "Capital the company manages for outside investors"

    def __init__(self, context):
        super().__init__(context)
        self.search = SearchBox("Search funds")
        self.table = Table(
            columns=[
                Column("name", "Fund", 240),
                Column("aum", "Under management", 170, align="right", numeric=True,
                       format=lambda v: v.format(decimals=0)),
                Column("gain", "Return", 110, align="right", numeric=True,
                       format=lambda v: v.format(signed=True), colour=_return_colour),
                Column("positions", "Positions", 100, align="right", numeric=True),
                Column("confidence", "Confidence", 120, align="right", numeric=True,
                       format=lambda v: v.format()),
            ],
            search_key="name",
            sort_key="aum",
            sort_descending=True,
        )
        self.create_button = Button("Open a fund", primary=True)
        self.create_requested = False
        self.selected_fund_id: str | None = None

    @property
    def book(self):
        company = self.context.company
        return getattr(company, "funds", None) if company else None

    def breadcrumb(self):
        return [("Company", "company"), ("Investment Funds", self.key)]

    def take_create_request(self) -> bool:
        requested, self.create_requested = self.create_requested, False
        return requested

    def rows(self) -> list[dict]:
        book = self.book
        if book is None:
            return []
        rows = []
        for fund in book:
            positions = fund.investments.open_positions() if fund.investments else []
            rows.append({
                "id": fund.id,
                "name": fund.name,
                "aum": fund.assets_under_management(),
                "gain": fund.total_return(),
                "positions": len(positions),
                "confidence": Percentage(fund.confidence),
            })
        return rows

    def cards(self) -> list[Card]:
        book = self.book
        if book is None:
            return []
        stats = book.statistics()
        return [
            Card("Funds", str(stats["Funds"]), "Managed independently"),
            Card("Under management", stats["Assets under management"].format(decimals=0),
                 "Your investors' money, not yours"),
            Card("Fees earned", stats["Fees earned"].format(decimals=0),
                 "What the company has been paid"),
            Card("Investor confidence", stats["Average confidence"].format(),
                 "Drives how much more they entrust"),
        ]

    def handle_event(self, event) -> bool:
        book = self.book
        if (book is not None and self.create_button.enabled
                and self.create_button.handle_event(event)
                and self.create_button.take_click()):
            self.create_requested = True
            return True
        if self.table.handle_event(event):
            opened = self.table.take_opened()
            if opened:
                self.selected_fund_id = opened["id"]
                self.navigate_to = "company:fund"
            return True
        return super().handle_event(event)

    def draw_content(self, surface, rect, fonts, mouse) -> None:
        book = self.book
        if book is None:
            panel(surface, pygame.Rect(rect.left, rect.top, rect.width, 160))
            draw_text(surface, fonts.body, "Found a company first.",
                      (rect.left + 24, rect.top + 60), theme.TEXT_MUTED)
            return

        allowed, reason = book.can_create()
        self.create_button.enabled = allowed
        if not book.funds:
            box = pygame.Rect(rect.left, rect.top, rect.width, 200)
            panel(surface, box)
            headline = ("You manage no funds yet" if allowed
                        else "Investment Funds are not open to you yet")
            draw_text(surface, fonts.subheading, headline,
                      (box.centerx, box.top + 52), theme.TEXT_MUTED,
                      align="center", baseline="middle")
            draw_text(surface, fonts.small,
                      reason if not allowed else
                      "A fund invests other people's money. The company earns a fee "
                      "for managing it well.",
                      (box.centerx, box.top + 82), theme.TEXT_FAINT,
                      align="center", baseline="middle")
            if allowed:
                self.create_button.draw(
                    surface, pygame.Rect(box.centerx - 70, box.top + 116, 140, 36),
                    fonts, mouse)
            return

        self.create_button.draw(
            surface, pygame.Rect(rect.right - 150, rect.top - 44, 140, 34), fonts, mouse)
        self.table.draw(surface, rect, fonts, mouse, self.rows(),
                        self.search.text if self.search else "")


class FundDetailPage(Page):
    """One fund's management page (V11.13)."""

    key = "company:fund"

    def __init__(self, context, list_page: FundsPage):
        super().__init__(context)
        self.list_page = list_page

    @property
    def fund(self):
        book = self.list_page.book
        if book is None or self.list_page.selected_fund_id is None:
            return None
        return book.by_id(self.list_page.selected_fund_id)

    @property
    def title(self) -> str:
        fund = self.fund
        return fund.name if fund else "Fund"

    @property
    def subtitle(self) -> str:
        return "Managed for external investors"

    def breadcrumb(self):
        fund = self.fund
        return [
            ("Company", "company"),
            ("Investment Funds", "company:funds"),
            (fund.name if fund else "Fund", self.key),
        ]

    def cards(self) -> list[Card]:
        fund = self.fund
        if fund is None:
            return []
        stats = fund.statistics()
        gain = stats["Total return"]
        return [
            Card("Under management", stats["Assets under management"].format(decimals=0),
                 "Belongs to the investors"),
            Card("Total return", gain.format(signed=True), "Since the fund opened",
                 accent=_return_colour(gain)),
            Card("Active investments", str(stats["Active investments"]),
                 "Positions held right now"),
            Card("Fees earned", stats["Fees earned"].format(decimals=0),
                 "Paid to your company"),
        ]

    def draw_content(self, surface, rect, fonts, mouse) -> None:
        fund = self.fund
        if fund is None:
            draw_text(surface, fonts.body, "Select a fund from the list.",
                      (rect.left, rect.top + 20), theme.TEXT_MUTED)
            return

        column = (rect.width - theme.GAP) // 2
        summary = pygame.Rect(rect.left, rect.top, column, 250)
        panel(surface, summary)
        draw_text(surface, fonts.subheading, "The fund",
                  (summary.left + 20, summary.top + 18))
        engine = self.context.engine
        age = (engine.date.day - fund.created_on_day) if engine else 0
        lines = [
            ("Invested by clients", fund.contributed.format(decimals=0)),
            ("Under management", fund.assets_under_management().format(decimals=0)),
            ("Cash not yet invested", fund.finances.cash.format(decimals=0)),
            ("Investor confidence", f"{fund.confidence:.0%}"),
            ("Open since day", f"{fund.created_on_day:,}"),
            ("Running for", f"{age:,} days"),
        ]
        y = summary.top + 56
        for label, value in lines:
            draw_text(surface, fonts.small, label, (summary.left + 20, y), theme.TEXT_MUTED)
            draw_text(surface, fonts.mono_small, value, (summary.right - 20, y),
                      theme.TEXT, align="right")
            y += 26

        chart = pygame.Rect(summary.right + theme.GAP, rect.top,
                            rect.width - column - theme.GAP, 250)
        self._draw_history(surface, chart, fonts, fund)

        holdings = pygame.Rect(rect.left, summary.bottom + theme.GAP, rect.width,
                               max(0, rect.bottom - summary.bottom - theme.GAP))
        if holdings.height >= 120:
            self._draw_holdings(surface, holdings, fonts, fund)

    def _draw_history(self, surface, rect, fonts, fund) -> None:
        """What the fund has been worth over time (V11.10)."""
        panel(surface, rect)
        draw_text(surface, fonts.subheading, "Under management over time",
                  (rect.left + 20, rect.top + 18))
        values = [float(value) for value in fund.history]
        if len(values) < 2:
            draw_text(surface, fonts.small,
                      "A line appears once the fund has a few months behind it.",
                      (rect.left + 20, rect.top + 54), theme.TEXT_FAINT)
            return

        plot = pygame.Rect(rect.left + 20, rect.top + 56, rect.width - 40, rect.height - 84)
        low, high = min(values), max(values)
        span = (high - low) or 1.0
        points = [
            (plot.left + int(plot.width * index / (len(values) - 1)),
             plot.bottom - int(plot.height * (value - low) / span))
            for index, value in enumerate(values)
        ]
        pygame.draw.lines(surface, theme.value_colour(values[-1] >= values[0]),
                          False, points, 2)
        draw_text(surface, fonts.mono_small, f"{high:,.0f}",
                  (rect.right - 20, plot.top - 2), theme.TEXT_FAINT, align="right")
        draw_text(surface, fonts.mono_small, f"{low:,.0f}",
                  (rect.right - 20, plot.bottom - 12), theme.TEXT_FAINT, align="right")

    def _draw_holdings(self, surface, rect, fonts, fund) -> None:
        """What the fund currently holds (V11.13)."""
        panel(surface, rect)
        draw_text(surface, fonts.subheading, "Active investments",
                  (rect.left + 20, rect.top + 16))
        market, world = self.context.market, self.context.world
        positions = fund.investments.open_positions() if fund.investments else []
        if not positions:
            draw_text(surface, fonts.small,
                      "The fund holds nothing right now. A new fund with no "
                      "investments yet is perfectly normal.",
                      (rect.left + 20, rect.top + 52), theme.TEXT_FAINT)
            return

        y = rect.top + 56
        for position in positions:
            if y + 24 > rect.bottom - 8:
                break
            listing = market.listing_for(position.company_id) if market else None
            record = world.company_by_id(position.company_id) if world else None
            if listing is None or record is None:
                continue
            gain = position.unrealised_return(listing.price)
            draw_text(surface, fonts.small, truncate(fonts.small, record.name, 320),
                      (rect.left + 20, y))
            draw_text(surface, fonts.mono_small,
                      position.value_at(listing.price).format(decimals=0),
                      (rect.left + 560, y), theme.TEXT, align="right")
            draw_text(surface, fonts.mono_small, gain.format(signed=True),
                      (rect.left + 690, y), _return_colour(gain), align="right")
            y += 24
