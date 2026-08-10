"""Drawing primitives: text, panels, chips and tooltips.

Split out of the single widgets module (2026-08-10) so that no file runs past
the size limit the project works to. Everything here is a plain function over
a surface and holds no state of its own, which is what lets every stateful
widget in the sibling modules depend on this one without depending on each
other.
"""

from __future__ import annotations

import pygame

from .. import theme


def draw_text(surface, font, text, pos, colour=theme.TEXT, *, align="left", baseline="top"):
    """Draw a line of text and return the rectangle it occupied."""
    rendered = font.render(str(text), True, colour)
    rect = rendered.get_rect()
    x, y = pos
    if align == "right":
        rect.right = x
    elif align == "center":
        rect.centerx = x
    else:
        rect.left = x
    if baseline == "middle":
        rect.centery = y
    else:
        rect.top = y
    surface.blit(rendered, rect)
    return rect


def truncate(font, text: str, width: int) -> str:
    """Shorten text with an ellipsis so it never overflows its column."""
    text = str(text)
    if font.size(text)[0] <= width:
        return text
    ellipsis = "…"
    while text and font.size(text + ellipsis)[0] > width:
        text = text[:-1]
    return text + ellipsis


def format_fraction(value: float, *, decimals: int = 0) -> str:
    """Format a raw 0.0-1.0 fraction as a percentage, e.g. ``0.42`` -> ``"42%"``.

    For fields not represented as a real :class:`~apex_horizon.engine.values.
    Percentage` value (reputation, confidence, happiness, performance) — one
    spelling instead of ``:.0%`` in some places and ``* 100:.0f}%`` in others
    for the same output (formatting-consistency pass, 2026-08-10).
    """
    return f"{value * 100:.{decimals}f}%"


def panel(surface, rect, *, fill=theme.SURFACE, border=theme.BORDER, radius=theme.CORNER):
    pygame.draw.rect(surface, fill, rect, border_radius=radius)
    if border is not None:
        pygame.draw.rect(surface, border, rect, 1, border_radius=radius)


def chip(surface, fonts, text: str, position: tuple[int, int], *,
         colour: tuple[int, int, int] | None = None,
         align: str = "left") -> pygame.Rect:
    """A small labelled pill for a state: an economy, a mood, a stage.

    States were being printed as bare words in the same style as every other
    value, which left nothing to distinguish "what this is" from "what it is
    doing". A chip is a status indicator, which V14.7 explicitly wants the
    default interface to use.
    """
    tint = colour or theme.TEXT_MUTED
    width = fonts.tiny.size(text.upper())[0] + 18
    left = position[0] - width if align == "right" else position[0]
    rect = pygame.Rect(left, position[1], width, 20)
    background = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    pygame.draw.rect(background, (*tint, 34), background.get_rect(), border_radius=10)
    surface.blit(background, rect.topleft)
    pygame.draw.rect(surface, (*tint, 255), rect, 1, border_radius=10)
    draw_text(surface, fonts.tiny, text.upper(), (rect.centerx, rect.centery), tint,
              align="center", baseline="middle")
    return rect


def draw_tooltip(surface, fonts, text: str, anchor: tuple[int, int]) -> None:
    """A small label beside an icon, so navigation never relies on the icon
    alone (V27.10)."""
    if not text:
        return
    width = fonts.small.size(text)[0] + 20
    rect = pygame.Rect(anchor[0], anchor[1] - 14, width, 28)
    surface_rect = surface.get_rect()
    if rect.right > surface_rect.right - 8:
        rect.right = surface_rect.right - 8
    panel(surface, rect, fill=theme.SURFACE_RAISED, border=theme.BORDER_STRONG)
    draw_text(surface, fonts.small, text, (rect.left + 10, rect.centery),
              theme.TEXT, baseline="middle")
