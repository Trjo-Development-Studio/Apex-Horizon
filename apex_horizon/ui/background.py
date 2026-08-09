"""The backdrop behind full-screen menus.

A screen with nothing on it but a colour reads as an application that has not
finished loading. This gives one some depth without giving it anything to look
at: a dark base, a slow gradient, one off-centre light, and a few very faint
geometric shapes overlapping across it.

It is deliberately abstract. The project manager ruled out anything
representational — no skylines, no charts, no axes, no symbols — and ruled out a
regular grid, which is the shape that makes an interface look like financial
software. What is left is soft overlapping geometry, which suggests depth
without suggesting *meaning*.

**The composition is designed, not rolled.** Every shape is written down here in
fractions of the window, so it is the same arrangement at every size and on
every launch, and it can be adjusted by moving a number rather than by hunting
for a seed that happens to look right. Nothing here uses randomness at all.

**Softness comes from scale.** The shapes are drawn into a surface a fraction of
the window's size and then scaled up, so their edges arrive blurred for the cost
of one smooth scale rather than a blur pass over a million pixels. The lines are
drawn at full size, because a line wants a clean edge even at this contrast.

It is a component rather than a picture of one screen: :class:`Backdrop` draws
into any surface it is handed and caches one rendering per size, so another
screen that wants the same treatment constructs one and calls ``draw``.
"""

from __future__ import annotations

import math

import pygame

from . import theme

#: How much smaller the facet layer is drawn before being scaled up. Larger
#: numbers are softer and cheaper, and eventually lose the shapes entirely.
SOFTNESS = 2

#: How finely a radial falloff is computed before being scaled to a shape.
FALLOFF_DETAIL = 160

#: Soft masses, as (centre x, centre y, radius x, radius y, alpha) in fractions
#: of the window. Arranged along a shallow diagonal so the eye is led across
#: rather than around, and kept away from the middle where the menu sits.
SHAPES = (
    (0.10, 0.16, 0.44, 0.38, 26),
    (0.88, 0.26, 0.38, 0.34, 20),
    (0.74, 0.80, 0.34, 0.30, 18),
    (0.20, 0.86, 0.40, 0.30, 16),
)

#: Angular facets, as (points, alpha). Overlapping the masses above, at angles
#: that share no rhythm with each other — a repeated angle starts to look like
#: a pattern, and a pattern at right angles starts to look like a grid.
FACETS = (
    (((-0.06, 0.58), (0.30, 0.26), (0.52, 0.44), (0.14, 0.82)), 11),
    (((0.58, 0.06), (1.06, -0.04), (1.06, 0.38), (0.70, 0.32)), 9),
    (((0.40, 0.74), (0.88, 0.54), (1.06, 0.84), (0.56, 1.06)), 8),
    (((0.02, -0.04), (0.34, -0.06), (0.26, 0.20), (-0.04, 0.16)), 8),
)

#: Long lines, as (start, end, alpha, width). Three, crossing at three
#: different angles, so they read as depth rather than as a chart.
LINES = (
    (((-0.05, 0.42), (1.05, 0.14)), 20, 1),
    (((-0.05, 0.76), (1.05, 0.46)), 14, 1),
    (((0.16, 1.05), (0.92, -0.05)), 11, 1),
)

#: The one light in the picture, as (x, y, radius, alpha) — off-centre, so the
#: gradient is not symmetrical and the screen does not look printed.
LIGHT = (0.38, 0.20, 0.78, 30)

#: How dark the edges go, keeping whatever sits in the middle the brightest
#: thing on the screen.
VIGNETTE = 120


class Backdrop:
    """A drawn background for a full-screen menu, cached per window size."""

    def __init__(self, *, softness: int = SOFTNESS):
        self.softness = max(1, softness)
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
        self._gradient(canvas, width, height)
        self._light(canvas, width, height)
        self._geometry(canvas, size)
        self._lines(canvas, width, height)
        self._vignette(canvas, size)
        return canvas

    def _gradient(self, canvas, width: int, height: int) -> None:
        """The base, a row at a time because it only happens once per size."""
        top, bottom = theme.BACKDROP_TOP, theme.BACKDROP_BOTTOM
        for y in range(height):
            # Eased rather than linear, so most of the screen is the darker end
            # and the lift at the top stays a suggestion.
            t = (y / max(1, height - 1)) ** 0.7
            pygame.draw.line(canvas, theme.mix(top, bottom, t), (0, y), (width, y))

    def _light(self, canvas, width: int, height: int) -> None:
        x, y, extent, alpha = LIGHT
        radius = int(min(width, height) * extent)
        glow = _blob((radius * 2, radius * 2), theme.BACKDROP_SHAPE, alpha)
        canvas.blit(glow, (int(width * x) - radius, int(height * y) - radius))

    def _geometry(self, canvas, size: tuple[int, int]) -> None:
        """Masses first, then facets over them.

        The masses are radial falloffs rather than filled ellipses: a shape with
        no edge cannot show one, which matters at this contrast, where a single
        step in alpha is visible as a seam.
        """
        width, height = size
        for centre_x, centre_y, radius_x, radius_y, alpha in SHAPES:
            box = pygame.Rect(0, 0, int(width * radius_x * 2),
                              int(height * radius_y * 2))
            box.center = (int(width * centre_x), int(height * centre_y))
            canvas.blit(_blob(box.size, theme.BACKDROP_SHAPE, alpha), box.topleft)

        # The facets do have edges, so they are drawn small and scaled up, which
        # turns each edge into a ramp a few pixels wide.
        small = (max(8, width // self.softness), max(8, height // self.softness))
        layer = pygame.Surface(small, pygame.SRCALPHA)
        for points, alpha in FACETS:
            pygame.draw.polygon(layer, (*theme.BACKDROP_SHAPE, alpha),
                                [(x * small[0], y * small[1]) for x, y in points])
        canvas.blit(pygame.transform.smoothscale(layer, size), (0, 0))

    def _lines(self, canvas, width: int, height: int) -> None:
        layer = pygame.Surface((width, height), pygame.SRCALPHA)
        for (start, end), alpha, thickness in LINES:
            pygame.draw.line(
                layer, (*theme.BACKDROP_LINE, alpha),
                (start[0] * width, start[1] * height),
                (end[0] * width, end[1] * height), thickness,
            )
        canvas.blit(layer, (0, 0))

    def _vignette(self, canvas, size: tuple[int, int]) -> None:
        """Darkened edges, so whatever the screen is for keeps its contrast."""
        canvas.blit(_blob(size, theme.OVERLAY, VIGNETTE, edge=0.35, invert=True),
                    (0, 0))


#: Falloff masks, built once and kept: the same two shapes serve every blob on
#: the screen, so a window resize costs a scale rather than a hundred thousand
#: pixels of arithmetic.
_FALLOFFS: dict[tuple, pygame.Surface] = {}


def _blob(size: tuple[int, int], colour, peak: int, *, edge: float = 0.0,
          invert: bool = False) -> pygame.Surface:
    """A soft shape of ``colour``, fading to nothing, at ``peak`` strength.

    The mask is scaled while it still has all 255 levels of alpha, and only then
    dimmed to the strength wanted. Dimming first would leave twenty-odd levels
    for the scale to interpolate between, and at these strengths that shows up
    as a mosaic of the mask's own pixels instead of a gradient.
    """
    shape = pygame.transform.smoothscale(_falloff(FALLOFF_DETAIL, edge, invert), size)
    shape.fill((*colour, peak), special_flags=pygame.BLEND_RGBA_MULT)
    return shape


def _falloff(size: int, edge: float, invert: bool) -> pygame.Surface:
    """A circular white-to-clear falloff, computed pixel by pixel and cached.

    ``edge`` is how far out the falloff starts, as a fraction of the radius;
    ``invert`` puts the solid part at the edges instead of in the middle.
    """
    key = (size, edge, invert)
    cached = _FALLOFFS.get(key)
    if cached is not None:
        return cached
    mask = pygame.Surface((size, size), pygame.SRCALPHA)
    centre = (size - 1) / 2
    furthest = math.hypot(centre, centre)
    for y in range(size):
        for x in range(size):
            distance = math.hypot(x - centre, y - centre) / furthest
            level = max(0.0, distance - edge) if invert else 1.0 - distance
            mask.set_at((x, y), (255, 255, 255, min(255, int(255 * level ** 2))))
    _FALLOFFS[key] = mask
    return mask
