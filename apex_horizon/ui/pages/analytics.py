"""The analytics page.

Every report is drawn the same way, from the plain data the analytics service
returns (V9.22) — this module knows how a report looks, and nothing about how
any figure in it was arrived at.

V9.10 asks for development over time, which a column of numbers cannot show, so
net worth is drawn as a line beneath the reports.
"""

from __future__ import annotations

import pygame

from .. import theme
from ..widgets import Card, draw_text, panel, truncate
from .base import Page

#: Narrowest a report column may be before the grid wraps to a new row.
REPORT_WIDTH = 200
#: Space above the first metric, for the report title and its note.
HEADER_HEIGHT = 68
ROW_HEIGHT = 44


class AnalyticsPage(Page):
    """The five analytics views V9 asks for, side by side.

    Not a sidebar destination of its own: Portfolio owns navigation to it as
    one of its tabs and calls :meth:`draw_content` directly rather than
    :meth:`Page.draw`, so this never gets a ``key`` to navigate to, a title
    bar, or a breadcrumb of its own (bug fix, 2026-08-09 — the leftover `key`
    used to look like a real, reachable destination when it was not).
    """

    @property
    def analytics(self):
        return getattr(self.context, "analytics", None)

    @property
    def locked(self) -> bool:
        """True until Basic Analytics is unlocked (V6.6.1)."""
        service = self.analytics
        return service is not None and not getattr(service, "enabled", True)

    def cards(self) -> list[Card]:
        service = self.analytics
        if service is None or self.locked:
            return []
        history = service.history
        months = len(history.snapshots) if history else 0
        cards = [
            Card("Detail level", str(service.tier), "Raised through the Unlock Tree"),
            Card("Reports", str(len(service.reports())), "Unlocked at this level"),
            Card("History", f"{months} month(s)", "Recorded since you began"),
        ]
        change = history.change_over("net_worth", 12) if history else None
        if change is not None:
            cards.append(Card(
                "Net worth, 1 year", f"{change:+.1%}", "Change over twelve months",
                accent=theme.value_colour(change >= 0),
            ))
        return cards

    def draw_content(self, surface, rect, fonts, mouse) -> None:
        service = self.analytics
        if self.locked:
            box = pygame.Rect(rect.left, rect.top, rect.width, min(220, rect.height))
            panel(surface, box)
            draw_text(surface, fonts.subheading, "Analytics are not open yet",
                      (box.centerx, box.centery - 20), theme.TEXT_MUTED,
                      align="center", baseline="middle")
            draw_text(surface, fonts.body,
                      "Basic Analytics, on the Unlock Tree, shows how your position stands.",
                      (box.centerx, box.centery + 8), theme.TEXT_FAINT,
                      align="center", baseline="middle")
            return
        if service is None:
            panel(surface, pygame.Rect(rect.left, rect.top, rect.width, 160))
            draw_text(surface, fonts.body, "Analytics are unavailable.",
                      (rect.left + 24, rect.top + 60), theme.TEXT_MUTED)
            return

        reports = service.reports()
        if not reports:
            box = pygame.Rect(rect.left, rect.top, rect.width, 160)
            panel(surface, box)
            draw_text(surface, fonts.body, "Found a company to see analytics.",
                      (box.centerx, box.centery), theme.TEXT_MUTED,
                      align="center", baseline="middle")
            return

        # Reports wrap onto further rows rather than being cut off at the edge
        # of the first: a report the player has unlocked but cannot see reads as
        # a missing feature, and V9.21 asks for figures to be shown or withheld
        # deliberately, never lost to the layout.
        columns = max(1, min(len(reports), rect.width // (REPORT_WIDTH + theme.GAP)))
        rows = -(-len(reports) // columns)
        width = (rect.width - theme.GAP * (columns - 1)) // columns

        # Every row is tall enough for the longest report in the grid, so a
        # metric is never half-drawn; the chart takes what is left, and steps
        # aside entirely on a window too short to hold both.
        longest = max(len(report.metrics) for report in reports)
        height = HEADER_HEIGHT + longest * ROW_HEIGHT + 12
        available = rect.height - (rows - 1) * theme.GAP
        height = min(height, max(120, available // rows))

        for index, report in enumerate(reports):
            column, row = index % columns, index // columns
            box = pygame.Rect(rect.left + column * (width + theme.GAP),
                              rect.top + row * (height + theme.GAP), width, height)
            self._draw_report(surface, box, fonts, report)

        used = rows * height + rows * theme.GAP
        chart = pygame.Rect(rect.left, rect.top + used, rect.width,
                            max(0, rect.bottom - rect.top - used))
        if chart.height >= 120:
            self._draw_history(surface, chart, fonts)

    def _draw_report(self, surface, rect, fonts, report) -> None:
        panel(surface, rect)
        draw_text(surface, fonts.subheading, report.title, (rect.left + 18, rect.top + 14))
        if report.note:
            draw_text(surface, fonts.small,
                      truncate(fonts.small, report.note, rect.width - 36),
                      (rect.left + 18, rect.top + 40), theme.TEXT_FAINT)

        y = rect.top + HEADER_HEIGHT
        for metric in report.metrics:
            if y + ROW_HEIGHT > rect.bottom - 4:
                break
            draw_text(surface, fonts.small,
                      truncate(fonts.small, metric.label, rect.width - 36),
                      (rect.left + 18, y), theme.TEXT_MUTED)
            draw_text(surface, fonts.mono_small, metric.value,
                      (rect.right - 18, y), theme.value_colour(metric.positive),
                      align="right")
            if metric.note:
                draw_text(surface, fonts.small,
                          truncate(fonts.small, metric.note, rect.width - 36),
                          (rect.left + 18, y + 18), theme.TEXT_FAINT)
            y += ROW_HEIGHT

    def _draw_history(self, surface, rect, fonts) -> None:
        """Net worth over time (V9.10)."""
        panel(surface, rect)
        draw_text(surface, fonts.subheading, "Net worth over time",
                  (rect.left + 18, rect.top + 14))
        history = self.analytics.history if self.analytics else None
        series = history.series("net_worth", 120) if history else []
        if len(series) < 2:
            draw_text(surface, fonts.small,
                      "A line appears once a few months have been recorded.",
                      (rect.left + 18, rect.top + 46), theme.TEXT_FAINT)
            return

        plot = pygame.Rect(rect.left + 18, rect.top + 46,
                           rect.width - 36, rect.height - 70)
        values = [value for _, value in series]
        low, high = min(values), max(values)
        span = (high - low) or 1.0
        points = []
        for index, value in enumerate(values):
            x = plot.left + int(plot.width * index / (len(values) - 1))
            y = plot.bottom - int(plot.height * (value - low) / span)
            points.append((x, y))
        colour = theme.value_colour(values[-1] >= values[0])
        pygame.draw.lines(surface, colour, False, points, 2)

        draw_text(surface, fonts.mono_small, f"{high:,.0f}",
                  (rect.right - 18, plot.top - 2), theme.TEXT_FAINT, align="right")
        draw_text(surface, fonts.mono_small, f"{low:,.0f}",
                  (rect.right - 18, plot.bottom - 12), theme.TEXT_FAINT, align="right")
