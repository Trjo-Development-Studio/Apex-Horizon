"""Sidebar and interface icons.

Design Bible V1.15 requires icons throughout the game to use a consistent
monochrome outline style, and V14.4 makes the sidebar icon-only. The project
manager's direction — the cited reference being unavailable — is that icons be
clean, professional, simple, recognisable, neutral, and functional rather than
decorative.

They are drawn rather than loaded. Simple geometry keeps every icon in exactly
the same weight and palette, which is what makes the set read as one family; it
also means no icon can go missing at runtime.

Every icon is paired with a text label or tooltip wherever it appears, since
V27.10 forbids navigation that depends on icon recognition alone.
"""

from __future__ import annotations

from collections.abc import Callable

import pygame

# All icons are drawn inside a square of this size and scaled by the caller.
ICON_SIZE = 24
LINE_WIDTH = 2


def _rect(surface, colour, x, y, w, h, width=LINE_WIDTH, radius=2):
    pygame.draw.rect(surface, colour, pygame.Rect(x, y, w, h), width, border_radius=radius)


def _line(surface, colour, start, end, width=LINE_WIDTH):
    pygame.draw.line(surface, colour, start, end, width)


def _dashboard(surface, colour):
    """Four panels — an overview made of parts."""
    _rect(surface, colour, 3, 3, 8, 8)
    _rect(surface, colour, 13, 3, 8, 5)
    _rect(surface, colour, 3, 13, 8, 8)
    _rect(surface, colour, 13, 10, 8, 11)


def _company(surface, colour):
    """A tower block — the organisation itself."""
    _rect(surface, colour, 4, 5, 11, 16)
    _rect(surface, colour, 15, 10, 6, 11)
    for row in range(3):
        for col in range(2):
            pygame.draw.rect(surface, colour, pygame.Rect(7 + col * 4, 8 + row * 4, 2, 2))


def _investments(surface, colour):
    """A rising line with an arrow head — growth over time."""
    points = [(3, 18), (9, 12), (13, 15), (21, 6)]
    pygame.draw.lines(surface, colour, False, points, LINE_WIDTH)
    pygame.draw.lines(surface, colour, False, [(15, 6), (21, 6), (21, 12)], LINE_WIDTH)


def _market(surface, colour):
    """Bars of differing height — a market of many companies."""
    _line(surface, colour, (3, 21), (21, 21))
    for x, top in ((5, 13), (10, 7), (15, 15), (19, 10)):
        pygame.draw.rect(surface, colour, pygame.Rect(x, top, 3, 21 - top))


def _news(surface, colour):
    """A page with a headline and lines of body text."""
    _rect(surface, colour, 4, 4, 16, 17)
    pygame.draw.rect(surface, colour, pygame.Rect(7, 8, 6, 4))
    for index in range(3):
        _line(surface, colour, (14, 9 + index * 3), (17, 9 + index * 3), 1)
    for index in range(2):
        _line(surface, colour, (7, 15 + index * 3), (17, 15 + index * 3), 1)


def _unlocks(surface, colour):
    """A branching tree — progression that opens outward."""
    pygame.draw.circle(surface, colour, (5, 12), 3, LINE_WIDTH)
    pygame.draw.circle(surface, colour, (19, 6), 3, LINE_WIDTH)
    pygame.draw.circle(surface, colour, (19, 18), 3, LINE_WIDTH)
    _line(surface, colour, (8, 11), (12, 7), 1)
    _line(surface, colour, (12, 7), (16, 6), 1)
    _line(surface, colour, (8, 13), (12, 17), 1)
    _line(surface, colour, (12, 17), (16, 18), 1)


def _finance(surface, colour):
    """A ledger page with a column of figures."""
    _rect(surface, colour, 4, 3, 16, 18)
    _line(surface, colour, (4, 9), (20, 9))
    _line(surface, colour, (12, 9), (12, 21), 1)
    for index in range(3):
        _line(surface, colour, (6, 12 + index * 3), (10, 12 + index * 3), 1)
        _line(surface, colour, (14, 12 + index * 3), (18, 12 + index * 3), 1)


def _settings(surface, colour):
    """A gear, drawn as a ring with teeth."""
    pygame.draw.circle(surface, colour, (12, 12), 7, LINE_WIDTH)
    pygame.draw.circle(surface, colour, (12, 12), 3, LINE_WIDTH)
    for dx, dy in ((0, -10), (0, 10), (-10, 0), (10, 0)):
        x, y = 12 + dx, 12 + dy
        pygame.draw.rect(surface, colour, pygame.Rect(x - 2, y - 2, 4, 4))


def _search(surface, colour):
    pygame.draw.circle(surface, colour, (10, 10), 6, LINE_WIDTH)
    _line(surface, colour, (14, 14), (20, 20))


def _close(surface, colour):
    _line(surface, colour, (6, 6), (18, 18))
    _line(surface, colour, (18, 6), (6, 18))


def _chevron_right(surface, colour):
    pygame.draw.lines(surface, colour, False, [(9, 5), (15, 12), (9, 19)], LINE_WIDTH)


def _analytics(surface, colour):
    """A pie divided into segments - figures broken down and compared."""
    pygame.draw.circle(surface, colour, (12, 12), 8, LINE_WIDTH)
    pygame.draw.line(surface, colour, (12, 12), (12, 4), LINE_WIDTH)
    pygame.draw.line(surface, colour, (12, 12), (19, 16), LINE_WIDTH)


def _statistics(surface, colour):
    """A tally of rising columns - figures accumulated over time."""
    for index, height in enumerate((6, 10, 14)):
        x = 6 + index * 6
        pygame.draw.line(surface, colour, (x, 18), (x, 18 - height), LINE_WIDTH)
    pygame.draw.line(surface, colour, (4, 20), (20, 20), LINE_WIDTH)


def _sort(surface, colour):
    pygame.draw.lines(surface, colour, False, [(8, 10), (12, 6), (16, 10)], LINE_WIDTH)
    pygame.draw.lines(surface, colour, False, [(8, 14), (12, 18), (16, 14)], LINE_WIDTH)


ICONS: dict[str, Callable[[pygame.Surface, tuple[int, int, int]], None]] = {
    "dashboard": _dashboard,
    "company": _company,
    "investments": _investments,
    "market": _market,
    "news": _news,
    "analytics": _analytics,
    "statistics": _statistics,
    "unlocks": _unlocks,
    "finance": _finance,
    "settings": _settings,
    "search": _search,
    "close": _close,
    "chevron": _chevron_right,
    "sort": _sort,
}

_cache: dict[tuple[str, tuple[int, int, int], int], pygame.Surface] = {}


def render(name: str, colour: tuple[int, int, int], size: int = ICON_SIZE) -> pygame.Surface:
    """Draw an icon, caching the result so redrawing a frame stays cheap."""
    key = (name, colour, size)
    cached = _cache.get(key)
    if cached is not None:
        return cached

    surface = pygame.Surface((ICON_SIZE, ICON_SIZE), pygame.SRCALPHA)
    drawer = ICONS.get(name)
    if drawer is not None:
        drawer(surface, colour)
    if size != ICON_SIZE:
        surface = pygame.transform.smoothscale(surface, (size, size))
    _cache[key] = surface
    return surface


def draw(target: pygame.Surface, name: str, colour, centre: tuple[int, int], size: int = ICON_SIZE):
    """Draw an icon centred on a point."""
    icon = render(name, colour, size)
    target.blit(icon, icon.get_rect(center=centre))


def clear_cache() -> None:
    _cache.clear()
