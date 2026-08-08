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


class Page:
    """Base class for every page in the game."""

    #: Sidebar destination this page belongs to.
    key: str = ""
    #: Title shown in the page header.
    title: str = ""
    #: Short line under the title explaining what the page is for.
    subtitle: str = ""

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

        # 3. Summary cards
        cards = self.cards()
        if cards:
            count = min(len(cards), 4)
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
