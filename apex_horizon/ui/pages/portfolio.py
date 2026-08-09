"""Portfolio: everything the player has money in.

One system, several views. V14.5 wants the sidebar to list major systems rather
than individual screens, and a player's holdings are one system whether the
money came from their own pocket or from the company they own — so personal
holdings, the company's operation, and the analysis of both live here together
behind a selector rather than as four separate destinations.

The two pools of money stay entirely separate underneath (V1.4, V3.4); what is
shared is only the page they are read on. **Company holdings appear only once a
company exists**, and never replace the personal view: the player is an
individual investor before they are a CEO and may remain one indefinitely
(V1.19, V1.20), so the personal portfolio is the permanent view here and the
company's is the one that arrives later.
"""

from __future__ import annotations

import pygame

from .. import theme
from ..widgets import Card, Tabs, draw_text, panel
from .analytics import AnalyticsPage
from .base import Page
from .simple import InvestmentsPage
from .statistics import StatisticsPage

PERSONAL = "Personal"
COMPANY = "Company"
ANALYTICS = "Analytics"
STATISTICS = "Statistics"


class PortfolioPage(Page):
    """The player's holdings, the company's, and the analysis of both."""

    key = "portfolio"
    title = "Portfolio"
    subtitle = "Everything you and your company have invested"

    def __init__(self, context):
        super().__init__(context)
        self.tabs = Tabs([PERSONAL])
        # Each view is an existing page, used for its content rather than as a
        # destination of its own. Nothing was rewritten to bring them together.
        self.holdings = InvestmentsPage(context)
        self.analytics = AnalyticsPage(context)
        self.statistics = StatisticsPage(context)

    # -- which views are available -----------------------------------------
    def available(self) -> list[str]:
        labels = [PERSONAL]
        if self.context.has_company:
            labels.append(COMPANY)
        labels += [ANALYTICS, STATISTICS]
        return labels

    @property
    def view(self):
        """The page supplying the current view's content."""
        return {
            PERSONAL: self.holdings,
            COMPANY: self.holdings,
            ANALYTICS: self.analytics,
            STATISTICS: self.statistics,
        }.get(self.tabs.selected, self.holdings)

    def on_show(self) -> None:
        self.tabs.set_labels(self.available())
        self.view.on_show()

    # -- the shared page furniture -----------------------------------------
    def breadcrumb(self):
        return [("Portfolio", self.key), (self.tabs.selected, self.key)]

    def cards(self) -> list[Card]:
        self.tabs.set_labels(self.available())
        selected = self.tabs.selected
        if selected == PERSONAL:
            return self._personal_cards()
        if selected == COMPANY:
            return self._company_cards()
        return self.view.cards()

    def _personal_cards(self) -> list[Card]:
        portfolio = self.context.portfolio
        player = self.context.player
        if portfolio is None or player is None:
            return []
        stats = portfolio.statistics()
        unrealised = stats["Unrealised"]
        return [
            Card("Your holdings", stats["Holdings value"].format(decimals=0),
                 f"{stats['Companies held']} companies", accent=theme.ACCENT),
            Card("Unrealised", unrealised.format(decimals=0, signed=True),
                 "On shares you still hold",
                 accent=theme.value_colour(not unrealised.is_negative),
                 trend=None if unrealised.is_zero else not unrealised.is_negative),
            Card("Realised", stats["Realised"].format(decimals=0, signed=True),
                 f"{stats['Trades']} trades",
                 accent=theme.value_colour(not stats["Realised"].is_negative)),
        ]

    def _company_cards(self) -> list[Card]:
        company = self.context.company
        system = getattr(company, "investments", None) if company else None
        if system is None:
            return []
        stats = system.statistics()
        unrealised = stats["Unrealised"]
        return [
            Card("Company holdings", stats["Holdings value"].format(decimals=0),
                 f"{stats['Open positions']} open positions", accent=theme.ACCENT),
            Card("Company cash", company.finances.cash.format(decimals=0),
                 "Held by the business"),
            Card("Unrealised", unrealised.format(decimals=0, signed=True),
                 "On positions still held",
                 accent=theme.value_colour(not unrealised.is_negative)),
            Card("Realised", stats["Realised"].format(decimals=0, signed=True),
                 f"{stats['Closed']} closed · {stats['Win rate']} profitable",
                 accent=theme.value_colour(not stats["Realised"].is_negative)),
        ]

    # -- interaction -------------------------------------------------------
    def handle_event(self, event) -> bool:
        if self.tabs.handle_event(event):
            self.view.on_show()
            return True
        handled = self.view.handle_event(event)
        # A view may ask to navigate elsewhere; that request belongs to this
        # page, since the views are not destinations of their own.
        if self.view.navigate_to:
            self.navigate_to, self.view.navigate_to = self.view.navigate_to, None
        return handled

    # -- drawing -----------------------------------------------------------
    def draw_content(self, surface, rect, fonts, mouse) -> None:
        self.tabs.set_labels(self.available())
        strip = pygame.Rect(rect.left, rect.top, rect.width, self.tabs.height())
        self.tabs.draw(surface, strip, fonts, mouse)

        content = pygame.Rect(rect.left, strip.bottom + theme.GAP // 2, rect.width,
                              max(0, rect.bottom - strip.bottom - theme.GAP // 2))
        selected = self.tabs.selected
        if selected == PERSONAL:
            self.holdings.draw_personal(surface, content, fonts)
        elif selected == COMPANY:
            self.holdings.draw_company(surface, content, fonts, mouse)
        else:
            self.view.draw_content(surface, content, fonts, mouse)

    def draw_locked(self, surface, rect, fonts, message: str) -> None:
        panel(surface, rect)
        draw_text(surface, fonts.body, message,
                  (rect.centerx, rect.centery), theme.TEXT_MUTED,
                  align="center", baseline="middle")
