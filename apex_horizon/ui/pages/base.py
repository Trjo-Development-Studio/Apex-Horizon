"""The shared page layout.

Design Bible V14.20 requires every management page to follow the same order —
header, breadcrumb, summary cards, search, main content, additional details —
because consistent layouts reduce the player's learning curve. V14.28 asks that
this be enforced by a single shared component rather than by developer
discipline, which is what this module is: a page supplies its parts, and the
base class decides where they go.

The result is the property V14.25 describes — opening the fiftieth page feels
exactly like opening the first.
"""

from __future__ import annotations

import pygame

from .. import theme
from ..context import GameContext
from ..widgets import Card, SearchBox, draw_text

#: Cards shown across the top of a page. Five rather than four, so leading
#: every page with the player's cash does not push a page's own fourth card off
#: the row.
MAX_CARDS = 5


def no_company_message(context: GameContext, action: str) -> str:
    """What a page says when it needs an operating company and there isn't one.

    Every page gating on :attr:`GameContext.has_company` says why in the same
    voice, and says something different for a company that never existed than
    for one that failed — a bankruptcy is a setback worth acknowledging, not a
    detail to fold into the same sentence used on day one (V14.26: an empty
    state has to read as honest, not as a locked door).

    ``action`` completes "Found a company {action}." / "Found a new company
    {action}.", e.g. ``"before hiring anyone"`` or ``"to begin tracking
    finances"``.
    """
    failed = context.bankrupt_company
    if failed is not None:
        return f"{failed.name} went bankrupt. Found a new company {action}."
    return f"Found a company {action}."


class Page:
    """Base class for every page in the game."""

    #: Sidebar destination this page belongs to.
    key: str = ""
    #: Title shown in the page header. Most pages set the constant below; a
    #: page whose title depends on what it is showing — one company, one
    #: employee — overrides the property instead. Both are legitimate, which is
    #: why the constant and the property are separate things.
    TITLE: str = ""
    #: Short line under the title explaining what the page is for.
    SUBTITLE: str = ""

    @property
    def title(self) -> str:
        return self.TITLE

    @property
    def subtitle(self) -> str:
        return self.SUBTITLE

    def __init__(self, context: GameContext):
        self.context = context
        self.search: SearchBox | None = None
        #: Set by a page to ask the application to navigate elsewhere.
        self.navigate_to: str | None = None

    # -- content supplied by subclasses ------------------------------------
    def breadcrumb(self) -> list[tuple[str, str]]:
        """Path segments as (label, destination). The last is the current page."""
        return [(self.title, self.key)]

    def cards(self) -> list[Card]:
        """Summary cards shown beneath the breadcrumb (V14.13)."""
        return []

    def draw_content(self, surface, rect, fonts, mouse) -> None:
        """The page's main content, drawn inside ``rect``."""

    def handle_event(self, event) -> bool:
        if self.search is not None:
            return self.search.handle_event(event)
        return False

    def on_show(self) -> None:
        """Called each time the page becomes visible."""

    # -- layout ------------------------------------------------------------
    def draw(self, surface, rect, fonts, mouse, breadcrumb) -> None:
        """Lay the page out in the order V14.20 requires."""
        y = rect.top

        # 1. Header
        draw_text(surface, fonts.title, self.title, (rect.left, y))
        if self.subtitle:
            draw_text(surface, fonts.small, self.subtitle, (rect.left, y + 38),
                      theme.TEXT_MUTED)
        y += 66 if self.subtitle else 48

        # 2. Breadcrumb
        breadcrumb.set(self.breadcrumb())
        breadcrumb.draw(surface, fonts, mouse, (rect.left, y + 8))
        y += 30

        # 3. Summary cards, always led by the player's cash
        cards = self._cards_with_cash()
        if cards:
            count = min(len(cards), MAX_CARDS)
            width = (rect.width - theme.GAP * (count - 1)) // count
            for index, card in enumerate(cards[:count]):
                card_rect = pygame.Rect(
                    rect.left + index * (width + theme.GAP), y, width, theme.CARD_HEIGHT
                )
                card.draw(surface, card_rect, fonts)
            y += theme.CARD_HEIGHT + theme.GAP

        # 4. Search
        if self.search is not None:
            search_rect = pygame.Rect(rect.left, y, 280, 34)
            self.search.draw(surface, search_rect, fonts, mouse)
            y += 34 + theme.GAP

        # 5. Main content (and any additional details the page adds within it)
        content = pygame.Rect(rect.left, y, rect.width, max(0, rect.bottom - y))
        self.draw_content(surface, content, fonts, mouse)


    def _cards_with_cash(self) -> list[Card]:
        """This page's cards, always led by the player's personal cash.

        Assembled here rather than by each page so that no screen can omit it
        and it always sits in the same position — first in the row — whatever
        the player is looking at (V14.13).

        Personal cash specifically: never net worth, which counts holdings and a
        company that cannot be spent, and never the company's own cash (V1.4).
        A page that shows either of those shows them as well, not instead.
        """
        player = getattr(self.context, "player", None)
        if player is None:
            return self.cards()
        cash = Card("Cash", player.cash.format(decimals=0), "Yours to spend right now",
                    accent=theme.ACCENT)
        return [cash, *self.cards()]


class EmptyStatePage(Page):
    """A page for a system that does not exist yet.

    V14.26 requires a page with no content to present a clear, intentional empty
    state rather than a blank or broken-looking screen. Saying plainly that a
    system is still to come is more honest than an empty table implying there is
    simply nothing to show.
    """

    message: str = ""
    detail: str = ""

    def draw_content(self, surface, rect, fonts, mouse) -> None:
        from ..widgets import panel

        box = pygame.Rect(rect.left, rect.top, rect.width, min(220, rect.height))
        panel(surface, box)
        draw_text(surface, fonts.subheading, self.message,
                  (box.centerx, box.centery - 16), theme.TEXT_MUTED,
                  align="center", baseline="middle")
        if self.detail:
            draw_text(surface, fonts.small, self.detail,
                      (box.centerx, box.centery + 12), theme.TEXT_FAINT,
                      align="center", baseline="middle")
