"""The statistics page.

V28 catalogues the categories of statistic the game tracks — company, employee,
investment, fund, world, and lifetime — and explains that each exists to answer
a question the player would actually ask (V28.8). This page is that catalogue
made visible in one place.

Most of these figures already existed, scattered across the pages that own them:
the company's on the Company page, employees' on theirs, and so on. What was
missing was somewhere to see the shape of a whole playthrough at once, which is
what V28.7's lifetime statistics are for — permanent records that survive
bankruptcy, refounding, and everything else that resets.
"""

from __future__ import annotations

import pygame

from .. import theme
from ..widgets import Card, draw_text, panel, truncate
from .base import Page

ROW_HEIGHT = 24


def _format(value) -> str:
    """Money, percentages and counts all read the same way in a column."""
    if hasattr(value, "format"):
        try:
            return value.format(decimals=0)
        except TypeError:
            return value.format()
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)


class StatisticsPage(Page):
    """Every category of statistic V28 names."""

    key = "statistics"
    title = "Statistics"
    subtitle = "What this playthrough has amounted to"

    @property
    def lifetime(self):
        return getattr(self.context, "statistics", None)

    def cards(self) -> list[Card]:
        lifetime = self.lifetime
        if lifetime is None:
            return []
        return [
            Card("Highest net worth", lifetime.highest_net_worth.format(decimals=0),
                 "The most you have ever been worth"),
            Card("Net lifetime profit",
                 lifetime.net_lifetime_profit().format(decimals=0, signed=True),
                 "Everything made, less everything lost",
                 accent=theme.value_colour(
                     not lifetime.net_lifetime_profit().is_negative)),
            Card("Employees ever hired", f"{lifetime.employees_hired:,}",
                 "Across every company you have run"),
            Card("Companies acquired", f"{lifetime.companies_acquired:,}",
                 "Bought outright and kept"),
        ]

    # -- the categories V28 names ------------------------------------------
    def sections(self) -> list[tuple[str, str, list[tuple[str, str]]]]:
        context = self.context
        company = context.company
        lifetime = self.lifetime
        sections: list[tuple[str, str, list[tuple[str, str]]]] = []

        if lifetime is not None:
            # V28.7: permanent records, never reset by anything.
            sections.append((
                "Lifetime", "Never reset, whatever happens to the company",
                [(label, _format(value)) for label, value in lifetime.summary().items()],
            ))

        if company is not None:
            # V28.2, first introduced in V3.13.
            finances = company.finances
            rows = [
                ("Company value", _format(company.value())),
                ("Cash", _format(finances.cash)),
                ("Weekly profit", finances.profit_this_week.format(decimals=0, signed=True)),
                ("Reputation", f"{company.reputation:.0%}"),
                ("Company level", str(company.level)),
                ("Employees", f"{len(company.employees):,}"),
            ]
            if company.subsidiaries is not None:
                rows.append(("Subsidiaries", f"{len(company.subsidiaries):,}"))
            if company.funds is not None:
                rows.append(("Assets under management",
                             _format(company.funds.assets_under_management())))
            sections.append(("Company", "How the business stands today", rows))

            # V28.4, defined in V9.12.
            system = company.investments
            if system is not None:
                stats = system.statistics()
                sections.append((
                    "Investments", "Where company profit comes from",
                    [(label, _format(value)) for label, value in stats.items()],
                ))

        # V28.6: the world outside the player's company.
        market, economy = context.market, context.economy
        if market is not None and economy is not None:
            mood = ("Bull market" if market.is_bull_market()
                    else "Bear market" if market.is_bear_market() else "Steady")
            world_rows = [
                ("Economy", str(economy.state)),
                ("Inflation", economy.inflation.format()),
                ("Market index", f"{market.market_index():,.0f}"),
                ("Sentiment", mood),
                ("Companies listed", f"{len(market.active_listings()):,}"),
            ]
            ai = getattr(context, "ai", None)
            if ai is not None:
                world_rows.append(("Rival companies", f"{len(ai.operating):,}"))
            sections.append(("The world", "Context for your own decisions", world_rows))

        return sections

    def draw_content(self, surface, rect, fonts, mouse) -> None:
        sections = self.sections()
        if not sections:
            panel(surface, pygame.Rect(rect.left, rect.top, rect.width, 160))
            draw_text(surface, fonts.body, "Statistics appear as you play.",
                      (rect.left + 24, rect.top + 60), theme.TEXT_MUTED)
            return

        columns = max(1, min(len(sections), rect.width // 300))
        width = (rect.width - theme.GAP * (columns - 1)) // columns
        rows = -(-len(sections) // columns)
        height = max(150, (rect.height - (rows - 1) * theme.GAP) // rows)

        for index, (title, note, entries) in enumerate(sections):
            column, row = index % columns, index // columns
            box = pygame.Rect(rect.left + column * (width + theme.GAP),
                              rect.top + row * (height + theme.GAP), width, height)
            self._draw_section(surface, box, fonts, title, note, entries)

    def _draw_section(self, surface, rect, fonts, title, note, entries) -> None:
        panel(surface, rect)
        draw_text(surface, fonts.subheading, title, (rect.left + 18, rect.top + 14))
        draw_text(surface, fonts.small, truncate(fonts.small, note, rect.width - 36),
                  (rect.left + 18, rect.top + 40), theme.TEXT_FAINT)

        y = rect.top + 66
        for label, value in entries:
            if y + ROW_HEIGHT > rect.bottom - 6:
                break
            draw_text(surface, fonts.small,
                      truncate(fonts.small, label, rect.width - 150),
                      (rect.left + 18, y), theme.TEXT_MUTED)
            draw_text(surface, fonts.mono_small, value, (rect.right - 18, y),
                      theme.TEXT, align="right")
            y += ROW_HEIGHT
