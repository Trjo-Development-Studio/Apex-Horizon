"""The Dashboard.

Design Bible V14.7 defines the default view: summary cards, key statistics,
recent activity and notifications — and explicitly no graphs, which appear only
when the player opens them (V14.14). V2.15 describes the session it supports:
the player scans, checks in, and makes a small number of deliberate decisions.

Because graphs are ruled out here, the work of making state readable at a glance
falls to what V14.7 does endorse: cards, statistics and status indicators. So
figures that are really proportions — reputation, staffing against capacity —
are drawn as meters, and states like the economy or the market's mood are drawn
as chips rather than as sentences in the same grey as every other value. None of
that is a graph; all of it saves the player from reading digits to learn
something a shape could have told them.
"""

from __future__ import annotations

import pygame

from .. import theme
from ..charts import meter
from ..widgets import Card, chip, draw_text, panel, truncate
from .base import Page


class DashboardPage(Page):
    """An overview of the company and the world around it (V14.7)."""

    key = "dashboard"
    title = "Dashboard"
    subtitle = "Your company at a glance"

    def cards(self):
        player, company, market = self.context.player, self.context.company, self.context.market
        cards = []
        if player is not None:
            cards.append(Card("Net worth", player.net_worth().format(decimals=0),
                              "Personal cash, holdings and company",
                              accent=theme.ACCENT))
            cards.append(Card("Personal cash", player.cash.format(decimals=0),
                              "Yours to invest or spend"))
        if company is not None:
            profit = company.finances.profit_this_week
            # A flat week has no direction, so it gets no arrow and no colour:
            # green for "unchanged" would be a small lie (V27.2).
            moved = None if profit.is_zero else not profit.is_negative
            cards.append(Card(
                "Company cash", company.finances.cash.format(decimals=0),
                f"{profit.format(decimals=0, signed=True)} this week",
                accent=None if moved is None else theme.value_colour(moved),
                trend=moved,
            ))
            roster = company.employees
            capacity = roster.capacity or 1
            cards.append(Card(
                "Staffing", f"{len(roster)} of {roster.capacity}",
                f"Company Level {company.level}",
                fraction=len(roster) / capacity,
            ))
        elif market is not None:
            cards.append(Card("Market index", f"{market.market_index():,.0f}",
                              "Opening level 1,000"))
            cards.append(Card("Listed companies", str(len(market.active_listings())),
                              "Trading today"))
        return cards

    def draw_content(self, surface, rect, fonts, mouse) -> None:
        column = (rect.width - theme.GAP) // 2

        activity = pygame.Rect(rect.left, rect.top, column, 250)
        panel(surface, activity)
        draw_text(surface, fonts.subheading, "Recent activity",
                  (activity.left + 20, activity.top + 18))
        entries = []
        company = self.context.company
        if company is not None:
            entries = list(reversed(company.finances.ledger.recent(7)))
        y = activity.top + 56
        if not entries:
            draw_text(surface, fonts.small,
                      "Activity will appear here once your company is trading.",
                      (activity.left + 20, y), theme.TEXT_FAINT)
        for entry in entries:
            incoming = entry.kind.value.endswith("in") or entry.kind.value == "revenue"
            draw_text(surface, fonts.small,
                      truncate(fonts.small, entry.description or entry.category, column - 150),
                      (activity.left + 20, y), theme.TEXT_MUTED)
            draw_text(surface, fonts.mono_small,
                      entry.amount.format(decimals=0),
                      (activity.right - 20, y),
                      theme.POSITIVE if incoming else theme.TEXT, align="right")
            y += 25

        world = pygame.Rect(activity.right + theme.GAP, rect.top, column, 250)
        panel(surface, world)
        draw_text(surface, fonts.subheading, "The world",
                  (world.left + 20, world.top + 18))
        economy, market = self.context.economy, self.context.market

        # States read as chips; quantities stay as figures. Separating the two
        # is what stops "Stable Economy" and "1,504" looking like the same kind
        # of thing (V14.7 status indicators).
        y = world.top + 52
        if economy is not None:
            health = float(getattr(economy, "health", 0.0))
            chip(surface, fonts, str(economy.state), (world.left + 20, y),
                 colour=theme.value_colour(health >= 0) if health else theme.TEXT_MUTED)
        if market is not None:
            bull, bear = market.is_bull_market(), market.is_bear_market()
            mood = "Bull market" if bull else "Bear market" if bear else "Steady"
            chip(surface, fonts, mood, (world.left + 150, y),
                 colour=theme.value_colour(bull) if (bull or bear) else theme.TEXT_MUTED)
        y += 34

        lines = []
        if economy is not None:
            lines.append(("Inflation", economy.inflation.format()))
        if market is not None:
            lines.append(("Market index", f"{market.market_index():,.0f}"))
            lines.append(("Companies listed", f"{len(market.active_listings()):,}"))
            gainers, _ = market.top_movers(1)
            if gainers and self.context.world:
                record = self.context.world.company_by_id(gainers[0].company_id)
                if record:
                    lines.append(("Today's top gainer", record.name))
        for label, value in lines:
            draw_text(surface, fonts.small, label, (world.left + 20, y), theme.TEXT_MUTED)
            draw_text(surface, fonts.small, truncate(fonts.small, value, column - 190),
                      (world.right - 20, y), theme.TEXT, align="right")
            y += 26

        company = self.context.company
        if company is not None:
            # Reputation is a proportion, so it is drawn as one (V14.7 asks the
            # default view to lean on indicators rather than graphs).
            draw_text(surface, fonts.small, "Company reputation",
                      (world.left + 20, y + 6), theme.TEXT_MUTED)
            draw_text(surface, fonts.mono_small, f"{company.reputation:.0%}",
                      (world.right - 20, y + 6), theme.TEXT, align="right")
            meter(surface, pygame.Rect(world.left + 20, y + 28, world.width - 40, 6),
                  company.reputation, colour=theme.ACCENT)

        rivals = pygame.Rect(rect.left, activity.bottom + theme.GAP, rect.width,
                             max(0, min(250, rect.bottom - activity.bottom - theme.GAP)))
        if rivals.height >= 120:
            self._draw_competitors(surface, rivals, fonts)

    def _draw_competitors(self, surface, rect, fonts) -> None:
        """The other investment companies in the world (V26.11).

        V4.10 and V26.2 both make the point that the market does not revolve
        around the player, and it is hard to believe that from a screen where no
        one else appears. Showing the rivals by name, size and staffing is what
        makes the world read as inhabited rather than as a backdrop.
        """
        panel(surface, rect)
        draw_text(surface, fonts.subheading, "Other investment companies",
                  (rect.left + 20, rect.top + 16))

        ai = getattr(self.context, "ai", None)
        if ai is None or not ai.companies:
            draw_text(surface, fonts.small, "No other companies are trading.",
                      (rect.left + 20, rect.top + 52), theme.TEXT_FAINT)
            return

        stats = ai.statistics()
        draw_text(surface, fonts.small,
                  f"{stats['Operating']} operating · {stats['Failed']} failed · "
                  f"{stats['People employed']} people employed",
                  (rect.left + 20, rect.top + 44), theme.TEXT_MUTED)

        player_company = self.context.company
        headers = (("Value", 520), ("Staff", 620), ("Level", 710))
        for label, offset in headers:
            draw_text(surface, fonts.small, label, (rect.left + offset, rect.top + 76),
                      theme.TEXT_FAINT, align="right")

        y = rect.top + 100
        for rival in ai.ranked():
            if y + 24 > rect.bottom - 8:
                break
            draw_text(surface, fonts.small,
                      truncate(fonts.small, rival.name, 460), (rect.left + 20, y))
            draw_text(surface, fonts.mono_small, rival.value().format(decimals=0),
                      (rect.left + 520, y),
                      theme.value_colour(not rival.value().is_negative), align="right")
            draw_text(surface, fonts.mono_small, str(len(rival.employees)),
                      (rect.left + 620, y), theme.TEXT, align="right")
            draw_text(surface, fonts.mono_small, str(rival.level),
                      (rect.left + 710, y), theme.TEXT_MUTED, align="right")
            y += 24

        if player_company is not None:
            # Where the player stands among them, which is the only reason the
            # list is worth reading.
            stronger = sum(1 for rival in ai.operating
                           if rival.value() > player_company.value())
            draw_text(surface, fonts.small,
                      f"You rank {stronger + 1} of {len(ai.operating) + 1} by company value.",
                      (rect.right - 20, rect.bottom - 26), theme.TEXT_MUTED, align="right")
