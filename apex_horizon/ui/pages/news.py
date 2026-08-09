"""The news archive.

V10.15 requires past articles to remain readable rather than scrolling away, so
this page is an archive rather than a ticker: the newest story is expanded at
the top and everything still held is listed beneath it.

V10.4 ties the kinds of story a player can see to the News branch of the Unlock
Tree, so the filter offers only the tiers actually unlocked — a locked tier is
not shown as an empty category, which would advertise content as missing rather
than as not yet earned.
"""

from __future__ import annotations

import pygame

from ...engine.news import NewsTier
from .. import theme
from ..widgets import Button, Card, draw_text, panel, truncate
from .base import Page

#: Colour used to mark each tier in the list, so a scan of the archive shows at
#: a glance what kind of story each line is.
TIER_COLOURS = {
    NewsTier.BASIC: theme.TEXT_MUTED,
    NewsTier.MARKET: theme.ACCENT,
    NewsTier.ECONOMIC: theme.ACCENT,
    NewsTier.BREAKING: theme.NEGATIVE,
}

ALL = "All"


class NewsPage(Page):
    """Everything the world has reported, newest first (V10.15)."""

    key = "news"
    TITLE = "News"
    SUBTITLE = "What is happening in the financial world"

    def __init__(self, context):
        super().__init__(context)
        self.filter: str = ALL
        self._filter_buttons: dict[str, Button] = {}
        #: Index into the filtered archive of the article shown in full.
        self.selected: int = 0
        self._row_hitboxes: list[tuple[pygame.Rect, int]] = []

    # -- data --------------------------------------------------------------
    @property
    def news(self):
        return getattr(self.context, "news", None)

    def filters(self) -> list[str]:
        """The tier filters worth offering, given what is unlocked (V10.4)."""
        system = self.news
        if system is None:
            return [ALL]
        return [ALL] + [str(tier) for tier in system.available_tiers]

    def articles(self) -> list:
        system = self.news
        if system is None:
            return []
        if self.filter == ALL:
            return system.recent(60)
        wanted = next(
            (tier for tier in system.available_tiers if str(tier) == self.filter), None
        )
        return system.recent(60, tier=wanted) if wanted else []

    def on_show(self) -> None:
        self.selected = 0

    def _unlocked_cards(self) -> list[Card]:
        system = self.news
        if system is None:
            return []
        archive = system.recent(60)
        breaking = sum(1 for article in archive if article.is_breaking)
        today = self.context.engine.date.day if self.context.engine else 0
        this_week = sum(1 for article in archive if today - article.day < 7)
        return [
            Card("Stories held", str(len(system.articles)), "The archive you can read back"),
            Card("This week", str(this_week), "Published in the last seven days"),
            Card("Breaking", str(breaking),
                 "Extraordinary moves" if breaking else "Nothing extraordinary",
                 accent=theme.NEGATIVE if breaking else None),
            Card("Coverage", str(system.tier),
                 "Raised through the Unlock Tree"),
        ]

    def _draw_locked(self, surface, rect, fonts) -> None:
        """V14.26: say plainly that this is earned, not missing."""
        box = pygame.Rect(rect.left, rect.top, rect.width, min(220, rect.height))
        panel(surface, box)
        draw_text(surface, fonts.subheading, "You have no financial press yet",
                  (box.centerx, box.centery - 26), theme.TEXT_MUTED,
                  align="center", baseline="middle")
        draw_text(surface, fonts.body,
                  "Basic News, on the Unlock Tree, brings you the day's stories.",
                  (box.centerx, box.centery + 2), theme.TEXT_FAINT,
                  align="center", baseline="middle")
        draw_text(surface, fonts.small,
                  "Further levels add market reports, the economy, and breaking news.",
                  (box.centerx, box.centery + 30), theme.TEXT_FAINT,
                  align="center", baseline="middle")

    # -- interaction -------------------------------------------------------
    def _button(self, label: str) -> Button:
        if label not in self._filter_buttons:
            self._filter_buttons[label] = Button(label)
        return self._filter_buttons[label]

    def handle_event(self, event) -> bool:
        for label in self.filters():
            button = self._button(label)
            if button.handle_event(event) and button.take_click():
                self.filter = label
                self.selected = 0
                return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for rect, index in self._row_hitboxes:
                if rect.collidepoint(event.pos):
                    self.selected = index
                    return True
        return False

    # -- drawing -----------------------------------------------------------
    @property
    def locked(self) -> bool:
        """True until Basic News is unlocked (V6.6.2)."""
        news = self.news
        return news is not None and not getattr(news, "enabled", True)

    def cards(self) -> list[Card]:
        if self.locked:
            return []
        return self._unlocked_cards()

    def draw_content(self, surface, rect, fonts, mouse) -> None:
        if self.locked:
            self._draw_locked(surface, rect, fonts)
            return
        if self.news is None:
            panel(surface, pygame.Rect(rect.left, rect.top, rect.width, 160))
            draw_text(surface, fonts.body, "The News System is unavailable.",
                      (rect.left + 24, rect.top + 60), theme.TEXT_MUTED)
            return

        y = self._draw_filters(surface, rect, fonts, mouse)
        articles = self.articles()
        if not articles:
            box = pygame.Rect(rect.left, y, rect.width, 160)
            panel(surface, box)
            draw_text(surface, fonts.body, "Nothing has been reported yet.",
                      (box.centerx, box.centery - 10), theme.TEXT_MUTED,
                      align="center", baseline="middle")
            draw_text(surface, fonts.small,
                      "Stories appear as the market and the economy move.",
                      (box.centerx, box.centery + 14), theme.TEXT_FAINT,
                      align="center", baseline="middle")
            return

        self.selected = min(self.selected, len(articles) - 1)
        lead = pygame.Rect(rect.left, y, rect.width, 150)
        self._draw_lead(surface, lead, fonts, articles[self.selected])
        archive = pygame.Rect(rect.left, lead.bottom + theme.GAP, rect.width,
                              max(0, rect.bottom - lead.bottom - theme.GAP))
        self._draw_archive(surface, archive, fonts, articles)

    def _draw_filters(self, surface, rect, fonts, mouse) -> int:
        x = rect.left
        for label in self.filters():
            button = self._button(label)
            button.primary = label == self.filter
            width = max(70, fonts.small.size(label)[0] + 28)
            button.draw(surface, pygame.Rect(x, rect.top, width, 30), fonts, mouse)
            x += width + 8
        return rect.top + 30 + theme.GAP

    def _draw_lead(self, surface, rect, fonts, article) -> None:
        """The selected story, in full (V10.15)."""
        panel(surface, rect)
        colour = TIER_COLOURS.get(article.tier, theme.TEXT_MUTED)
        draw_text(surface, fonts.small, str(article.tier).upper(),
                  (rect.left + 20, rect.top + 16), colour)
        draw_text(surface, fonts.subheading,
                  truncate(fonts.subheading, article.headline, rect.width - 40),
                  (rect.left + 20, rect.top + 40))
        draw_text(surface, fonts.body,
                  truncate(fonts.body, article.body, rect.width - 40),
                  (rect.left + 20, rect.top + 76), theme.TEXT_MUTED)

        byline = article.agency or "Unattributed"
        draw_text(surface, fonts.small, f"{byline} · day {article.day}",
                  (rect.left + 20, rect.bottom - 30), theme.TEXT_FAINT)
        if article.impact is not None:
            draw_text(surface, fonts.mono_small, article.impact.format(signed=True),
                      (rect.right - 20, rect.bottom - 30),
                      theme.value_colour(not article.impact.is_negative), align="right")

    def _draw_archive(self, surface, rect, fonts, articles) -> None:
        panel(surface, rect)
        draw_text(surface, fonts.subheading, "Archive", (rect.left + 20, rect.top + 16))
        draw_text(surface, fonts.small, "Select a story to read it in full.",
                  (rect.right - 20, rect.top + 20), theme.TEXT_FAINT, align="right")

        self._row_hitboxes.clear()
        y = rect.top + 52
        row_height = 26
        for index, article in enumerate(articles):
            if y + row_height > rect.bottom - 8:
                break
            row = pygame.Rect(rect.left + 8, y - 4, rect.width - 16, row_height)
            if index == self.selected:
                pygame.draw.rect(surface, theme.SURFACE_RAISED, row, border_radius=4)
            self._row_hitboxes.append((row, index))

            draw_text(surface, fonts.small, str(article.tier),
                      (rect.left + 20, y), TIER_COLOURS.get(article.tier, theme.TEXT_MUTED))
            draw_text(surface, fonts.small,
                      truncate(fonts.small, article.headline, rect.width - 280),
                      (rect.left + 110, y), theme.TEXT)
            draw_text(surface, fonts.small,
                      truncate(fonts.small, article.agency, 150),
                      (rect.right - 100, y), theme.TEXT_FAINT, align="right")
            draw_text(surface, fonts.mono_small, str(article.day),
                      (rect.right - 20, y), theme.TEXT_FAINT, align="right")
            y += row_height
