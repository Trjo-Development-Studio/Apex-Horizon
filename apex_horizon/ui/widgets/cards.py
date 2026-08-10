"""The summary card, the primary way a figure is shown (V14.13)."""

from __future__ import annotations

from dataclasses import dataclass

import pygame

from .. import theme
from .text import draw_text, panel, truncate


@dataclass
class Card:
    """A summary figure. Cards are the primary way information is shown (V14.13).

    V14.7 puts summary cards at the centre of the default view and keeps graphs
    out of it, so a card has to carry more than a number: an accent bar for the
    category it belongs to, a direction when the figure has one, and optionally
    a meter when the value is really a proportion. None of those is a graph —
    they are the status indicators V14.7 asks the default interface to lean on.
    """

    label: str
    value: str
    detail: str = ""
    accent: tuple[int, int, int] | None = None
    #: True for good, False for bad, None when the figure has no direction.
    trend: bool | None = None
    #: A 0-1 proportion drawn as a meter beneath the value, when one applies.
    fraction: float | None = None

    def draw(self, surface, rect, fonts) -> None:
        panel(surface, rect, fill=theme.SURFACE)
        colour = self.accent or theme.TEXT

        # A short bar down the leading edge, tying the card to its meaning
        # without colouring the whole surface (V27.2, V27.10).
        marker = pygame.Rect(rect.left + 1, rect.top + 14, 3, rect.height - 28)
        pygame.draw.rect(surface, self.accent or theme.BORDER_STRONG, marker,
                         border_radius=2)

        draw_text(surface, fonts.tiny,
                  truncate(fonts.tiny, self.label.upper(), rect.width - 36),
                  (rect.left + 18, rect.top + 14), theme.TEXT_FAINT)

        # A card holds names as well as figures, and a long company name has to
        # give way rather than run over the edge of the card beside it.
        value_x = rect.left + 18
        room = rect.width - 36 - (18 if self.trend is not None else 0)
        value = truncate(fonts.heading, self.value, room)
        draw_text(surface, fonts.heading, value, (value_x, rect.top + 34), colour)

        if self.trend is not None:
            arrow = "\u25b2" if self.trend else "\u25bc"
            width = fonts.heading.size(value)[0]
            draw_text(surface, fonts.small, arrow, (value_x + width + 8, rect.top + 42),
                      theme.value_colour(self.trend))

        if self.fraction is not None:
            from ..charts import meter

            # The meter takes the space the detail line would have used, so the
            # detail moves above it rather than on top of the value.
            if self.detail:
                draw_text(surface, fonts.small, self.detail,
                          (rect.left + 18, rect.bottom - 34), theme.TEXT_MUTED)
            bar = pygame.Rect(rect.left + 18, rect.bottom - 16, rect.width - 36, 5)
            meter(surface, bar, self.fraction, colour=self.accent or theme.ACCENT)
            return

        if self.detail:
            draw_text(surface, fonts.small,
                      truncate(fonts.small, self.detail, rect.width - 36),
                      (rect.left + 18, rect.bottom - 24), theme.TEXT_MUTED)
