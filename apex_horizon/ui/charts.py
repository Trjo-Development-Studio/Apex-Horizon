"""Data visualisation.

V14.3 names **business dashboards** as a primary inspiration, alongside
professional financial platforms and management software. Dashboards are the
part that had been missing: figures the game already tracked were being printed
as columns of digits when the underlying shape — a price over two years, a
reputation between nothing and everything, one industry against the rest — was
what the player actually needed to read.

Everything here is deliberately restrained, because V1.15 rules out flashy
effects and cartoon visuals, and V27.10 requires contrast to hold. These are
instruments, not decoration: no gradients for their own sake, no shadows, no
colour that does not mean something. Green and red keep their single meaning of
financial gain and loss (V27.2), and anything neutral stays grey.

Animation follows V27.8 — it exists only to clarify a state change and must
never delay the player. A meter slides to its value over a fraction of a second
because seeing it move tells you it changed; nothing here loops, pulses or waits
for attention.
"""

from __future__ import annotations

from collections.abc import Sequence

import pygame

from . import theme

#: How long a meter or bar takes to reach a new value (V27.8).
FILL_MS = 220


def ease_out(t: float) -> float:
    """Decelerating easing, so movement settles rather than stopping dead."""
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) * (1 - t)


class Animated:
    """A number that moves to its target rather than jumping (V27.8).

    Kept deliberately tiny. A widget owns one of these per animated value and
    reads :meth:`value` while drawing; nothing schedules callbacks or holds a
    clock of its own.
    """

    def __init__(self, value: float = 0.0, duration_ms: int = FILL_MS):
        self.duration_ms = duration_ms
        self._from = value
        self._to = value
        self._started_ms: int | None = None

    def target(self, value: float, now_ms: int) -> None:
        if value == self._to:
            return
        self._from = self.value(now_ms)
        self._to = value
        self._started_ms = now_ms

    def value(self, now_ms: int) -> float:
        if self._started_ms is None or not self.duration_ms:
            return self._to
        elapsed = now_ms - self._started_ms
        if elapsed >= self.duration_ms:
            return self._to
        return self._from + (self._to - self._from) * ease_out(elapsed / self.duration_ms)


def sparkline(surface, rect: pygame.Rect, values: Sequence[float], *,
              colour: tuple[int, int, int] | None = None,
              fill: bool = True, baseline: bool = False) -> None:
    """A small line of a series, showing shape rather than exact figures.

    Used where a table cell or card would otherwise hold a single number that
    says nothing about how it got there — a share price, a fund's assets, a
    company's worth.
    """
    points = [float(value) for value in values if value is not None]
    if len(points) < 2 or rect.width < 4 or rect.height < 4:
        return

    low, high = min(points), max(points)
    span = (high - low) or 1.0
    rising = points[-1] >= points[0]
    line = colour or theme.value_colour(rising)

    plotted = [
        (
            rect.left + rect.width * index / (len(points) - 1),
            rect.bottom - rect.height * (value - low) / span,
        )
        for index, value in enumerate(points)
    ]

    if fill:
        # A faint wash under the line gives the shape weight without drawing
        # attention to itself.
        area = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        shifted = [(x - rect.left, y - rect.top) for x, y in plotted]
        polygon = [(shifted[0][0], rect.height), *shifted, (shifted[-1][0], rect.height)]
        pygame.draw.polygon(area, (*line, 38), polygon)
        surface.blit(area, rect.topleft)

    if baseline:
        pygame.draw.line(surface, theme.BORDER,
                         (rect.left, rect.bottom), (rect.right, rect.bottom))
    pygame.draw.lines(surface, line, False, plotted, 2)


def meter(surface, rect: pygame.Rect, fraction: float, *,
          colour: tuple[int, int, int] | None = None,
          track: tuple[int, int, int] | None = None) -> None:
    """A bar showing how full something is.

    For the many values that run from nothing to everything — reputation,
    happiness, investor confidence, progress through a branch — where a
    percentage printed as text makes the reader do the work of picturing it.
    """
    fraction = max(0.0, min(1.0, fraction))
    radius = min(theme.CORNER, rect.height // 2)
    pygame.draw.rect(surface, track or theme.SURFACE_RAISED, rect, border_radius=radius)
    if fraction <= 0:
        return
    filled = pygame.Rect(rect.left, rect.top, max(2, int(rect.width * fraction)), rect.height)
    pygame.draw.rect(surface, colour or theme.ACCENT, filled, border_radius=radius)


def bars(surface, rect: pygame.Rect, fonts, entries: Sequence[tuple[str, float]], *,
         label_width: int = 130, value_format=None) -> None:
    """A horizontal bar for each entry, scaled against the largest magnitude.

    Comparisons — industry against industry, department against department —
    read as relative length far faster than as a column of signed percentages.
    Bars run either side of a centre line when values can be negative, so a
    losing industry reads as losing at a glance.
    """
    from .widgets import draw_text, truncate

    entries = list(entries)
    if not entries:
        return
    largest = max(abs(value) for _, value in entries) or 1.0
    negatives = any(value < 0 for _, value in entries)

    # Rows shrink to fit rather than overflowing. Dropping a row is worse than
    # a tight one: the entry that sets the scale is often the largest, and
    # losing it leaves every remaining bar measured against something invisible.
    row_height = max(13, min(28, rect.height // len(entries)))
    track_left = rect.left + label_width
    track_width = max(20, rect.width - label_width - 70)
    centre = track_left + (track_width // 2 if negatives else 0)

    for index, (label, value) in enumerate(entries):
        y = rect.top + index * row_height
        if y + row_height > rect.bottom:
            break
        draw_text(surface, fonts.small,
                  truncate(fonts.small, label, label_width - 12),
                  (rect.left, y + 3), theme.TEXT_MUTED)

        extent = int((abs(value) / largest) * (track_width / (2 if negatives else 1)))
        # A contribution that rounds to nothing still gets a visible sliver, so
        # "barely mattered" reads differently from "not drawn".
        colour = theme.value_colour(value >= 0) if negatives else theme.ACCENT
        thickness = max(4, row_height - 9)
        bar = pygame.Rect(centre if value >= 0 else centre - extent,
                          y + (row_height - thickness) // 2,
                          max(2, extent), thickness)
        pygame.draw.rect(surface, colour, bar, border_radius=2)

        text = value_format(value) if value_format else f"{value:+.1%}"
        draw_text(surface, fonts.mono_small, text, (rect.right, y + 3),
                  theme.TEXT_MUTED, align="right")

    if negatives:
        pygame.draw.line(surface, theme.BORDER_STRONG,
                         (centre, rect.top), (centre, min(rect.bottom, rect.top + len(entries) * row_height)))


def line_chart(surface, rect: pygame.Rect, fonts, values: Sequence[float], *,
               colour: tuple[int, int, int] | None = None,
               label: str = "", show_bounds: bool = True) -> None:
    """A full-size chart of a series, with its range labelled.

    The larger sibling of :func:`sparkline`, for when a screen has room to show
    a history properly rather than as a hint.
    """
    from .widgets import draw_text

    points = [float(value) for value in values if value is not None]
    if len(points) < 2:
        draw_text(surface, fonts.small,
                  "Not enough history yet to chart.",
                  (rect.left, rect.top), theme.TEXT_FAINT)
        return

    low, high = min(points), max(points)
    plot = pygame.Rect(rect.left, rect.top, rect.width - 78, rect.height)

    # Faint horizontal guides, so a reader can judge level without a grid that
    # competes with the data.
    for share in (0.0, 0.5, 1.0):
        y = plot.bottom - int(plot.height * share)
        pygame.draw.line(surface, theme.BORDER, (plot.left, y), (plot.right, y))

    sparkline(surface, plot, points, colour=colour, fill=True)

    if show_bounds:
        draw_text(surface, fonts.mono_small, f"{high:,.0f}",
                  (rect.right, plot.top - 6), theme.TEXT_FAINT, align="right")
        draw_text(surface, fonts.mono_small, f"{low:,.0f}",
                  (rect.right, plot.bottom - 10), theme.TEXT_FAINT, align="right")
    if label:
        draw_text(surface, fonts.small, label, (plot.left, plot.top - 18), theme.TEXT_FAINT)


def donut(surface, centre: tuple[int, int], radius: int, fraction: float, *,
          colour: tuple[int, int, int] | None = None, width: int = 6) -> None:
    """A ring filled to a fraction, for a single headline proportion."""
    fraction = max(0.0, min(1.0, fraction))
    box = pygame.Rect(centre[0] - radius, centre[1] - radius, radius * 2, radius * 2)
    pygame.draw.circle(surface, theme.SURFACE_RAISED, centre, radius, width)
    if fraction <= 0:
        return
    import math

    pygame.draw.arc(surface, colour or theme.ACCENT, box,
                    math.pi / 2, math.pi / 2 + 2 * math.pi * fraction, width)
