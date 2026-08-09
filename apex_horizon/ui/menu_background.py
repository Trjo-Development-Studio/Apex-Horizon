"""The Start Menu's backdrop.

The project manager asked for the front of the game to look like a finished game
rather than an empty application window, without becoming a financial dashboard
and without competing with the menu in front of it.

So: a city at dusk, drawn rather than photographed. Skylines are what a business
simulation looks like from the outside — the thing the player is being invited
to go and own — and a silhouette carries that in a shape rather than in numbers.
Above it a single index line rises, which is the only figure the menu shows and
it has no axis, no value and no label; it is a horizon, not a chart.

Everything is built from the palette in :mod:`.theme` and kept within a few
values of the background it replaces, so the buttons and the title still have
all the contrast they had against flat black (V27.10). It is scenery: if a
player notices it after the first ten seconds, it is too loud.

It is drawn once per window size into a cached surface — a menu should not spend
a frame's budget redrawing a static picture sixty times a second — and rebuilt
from a fixed seed, so the skyline is the same city every time the game opens
rather than a different one each launch.
"""

from __future__ import annotations

import math
from random import Random

import pygame

from . import theme

#: The same city every launch (V15.11's determinism, applied to scenery).
SEED = 20260809

#: Where each row of buildings stands, as a fraction of the window height, and
#: how tall its tallest tower may be. The skyline keeps to the bottom quarter:
#: the menu itself sits above it and must not have to compete.
FAR_BASE, FAR_MAX = 0.78, 0.15
NEAR_BASE, NEAR_MAX = 0.86, 0.20

WINDOW_CHANCE = 0.14
WINDOW_SIZE = (2, 3)


class MenuBackground:
    """A drawn backdrop, cached for the size of window it was drawn for."""

    def __init__(self, seed: int = SEED):
        self.seed = seed
        self._cache: pygame.Surface | None = None
        self._size: tuple[int, int] = (0, 0)

    def surface_for(self, size: tuple[int, int]) -> pygame.Surface:
        if self._cache is None or self._size != size:
            self._cache = self._render(size)
            self._size = size
        return self._cache

    def draw(self, surface) -> None:
        surface.blit(self.surface_for(surface.get_size()), (0, 0))

    # -- building the picture ----------------------------------------------
    def _render(self, size: tuple[int, int]) -> pygame.Surface:
        width, height = size
        canvas = pygame.Surface(size).convert()
        rng = Random(self.seed)

        self._sky(canvas, width, height)
        self._glow(canvas, width, height)
        self._index_line(canvas, width, height, rng)
        self._skyline(canvas, rng, width, height, int(height * FAR_BASE),
                      theme.MENU_SKYLINE_FAR, FAR_MAX, step=(30, 56), windows=False)
        self._skyline(canvas, rng, width, height, int(height * NEAR_BASE),
                      theme.MENU_SKYLINE_NEAR, NEAR_MAX, step=(52, 96), windows=True)
        self._vignette(canvas, size)
        return canvas

    def _sky(self, canvas, width: int, height: int) -> None:
        """A dusk gradient, drawn a row at a time because it only happens once."""
        top, bottom = theme.MENU_SKY_TOP, theme.MENU_SKY_BOTTOM
        for y in range(height):
            t = y / max(1, height - 1)
            pygame.draw.line(canvas, theme.mix(top, bottom, t), (0, y), (width, y))

    def _glow(self, canvas, width: int, height: int) -> None:
        """A trace of light behind the title, so the type has something to sit on.

        Built small and scaled up: a smooth falloff costs a few thousand pixels
        once, where stacked circles cost either banding or a lot of them.
        """
        radius = int(min(width, height) * 0.62)
        glow = pygame.transform.smoothscale(
            _radial(64, theme.ACCENT_MUTED, peak=26, edge=0.0, invert=True),
            (radius * 2, radius * 2))
        canvas.blit(glow, (width // 2 - radius, int(height * 0.26) - radius))

    def _index_line(self, canvas, width: int, height: int, rng: Random) -> None:
        """One line rising across the sky: a horizon, not a chart."""
        top, bottom = int(height * 0.20), int(height * FAR_BASE)
        points, value = [], 0.0
        steps = max(24, width // 26)
        for index in range(steps + 1):
            value += rng.uniform(-0.06, 0.10)
            # A gentle climb the noise moves around rather than overwhelms.
            level = index / steps * 0.62 + value * 0.18
            x = int(index / steps * width)
            y = int(bottom - (bottom - top) * max(0.0, min(1.0, level)))
            points.append((x, y))

        area = pygame.Surface((width, height), pygame.SRCALPHA)
        pygame.draw.polygon(area, (*theme.ACCENT, 10),
                            [(0, bottom), *points, (width, bottom)])
        pygame.draw.lines(area, (*theme.ACCENT, 40), False, points, 2)
        canvas.blit(area, (0, 0))

    def _skyline(self, canvas, rng: Random, width: int, height: int, base: int,
                 colour, tallest: float, step: tuple[int, int], windows: bool) -> None:
        """One row of buildings, silhouetted against the sky."""
        lit = pygame.Surface((width, height), pygame.SRCALPHA)
        x = -rng.randint(0, step[1])
        while x < width:
            building = rng.randint(*step)
            top = base - int(height * rng.uniform(tallest * 0.28, tallest))
            rect = pygame.Rect(x, top, building, height - top)
            pygame.draw.rect(canvas, colour, rect)
            # A hairline along the roof, so the shapes read as separate towers
            # rather than as one flat mass.
            pygame.draw.line(canvas, theme.MENU_HORIZON,
                             (rect.left, rect.top), (rect.right - 1, rect.top))
            if windows:
                self._windows(lit, rng, rect)
            x += building + rng.randint(2, 9)
        canvas.blit(lit, (0, 0))

    def _windows(self, lit, rng: Random, rect) -> None:
        """A scattering of offices still working, which is the whole joke."""
        pane_width, pane_height = WINDOW_SIZE
        for y in range(rect.top + 8, rect.bottom - 6, pane_height + 6):
            for x in range(rect.left + 6, rect.right - pane_width - 4, pane_width + 6):
                if rng.random() > WINDOW_CHANCE:
                    continue
                alpha = rng.randint(25, 70)
                colour = theme.ACCENT if rng.random() < 0.75 else theme.WARNING
                pygame.draw.rect(lit, (*colour, alpha),
                                 pygame.Rect(x, y, pane_width, pane_height))

    def _vignette(self, canvas, size: tuple[int, int]) -> None:
        """Darkened edges, so the menu in the middle keeps its contrast."""
        canvas.blit(pygame.transform.smoothscale(
            _radial(64, theme.OVERLAY, peak=130, edge=0.35), size), (0, 0))


def _radial(size: int, colour, *, peak: int, edge: float, invert: bool = False):
    """A circular alpha falloff, built small enough to compute pixel by pixel.

    ``edge`` is how far from the centre the falloff starts, as a fraction of the
    radius; ``invert`` makes it brightest in the middle instead of at the edges.
    """
    mask = pygame.Surface((size, size), pygame.SRCALPHA)
    centre = (size - 1) / 2
    furthest = math.hypot(centre, centre)
    for y in range(size):
        for x in range(size):
            distance = math.hypot(x - centre, y - centre) / furthest
            level = (1.0 - distance) if invert else max(0.0, distance - edge)
            alpha = int(peak * max(0.0, level) ** 2)
            mask.set_at((x, y), (*colour, min(peak, alpha)))
    return mask
