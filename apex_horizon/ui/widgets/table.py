"""The table widget, and the columns it is built from."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

import pygame

from .. import icons, theme
from .text import draw_text, panel, truncate


@dataclass
class Column:
    """One column of a table (V27.5: one column per attribute)."""

    key: str
    title: str
    width: int
    align: str = "left"
    numeric: bool = False
    format: Callable[[Any], str] = str
    colour: Callable[[Any], tuple] | None = None

    def render_value(self, value: Any) -> str:
        try:
            return self.format(value)
        except Exception:
            return str(value)


#: Space reserved at the foot of a table for the item count and page controls.
FOOTER_HEIGHT = 48


@dataclass
class Table:
    """A searchable, sortable, paginated list of entities.

    Sorting is explicit and remembered for this specific list (V27.3); search
    combines with it additively rather than replacing it.
    """

    columns: Sequence[Column]
    search_key: str | None = None
    page_size: int = 12  # replaced on every draw by what the panel can hold
    sort_key: str | None = None
    sort_descending: bool = False
    page: int = 0
    opened_row: dict | None = field(default=None, repr=False)
    _header_rects: dict[str, pygame.Rect] = field(default_factory=dict, repr=False)
    _row_rects: list[tuple[pygame.Rect, dict]] = field(default_factory=list, repr=False)
    _prev_rect: pygame.Rect = field(default_factory=lambda: pygame.Rect(0, 0, 0, 0), repr=False)
    _next_rect: pygame.Rect = field(default_factory=lambda: pygame.Rect(0, 0, 0, 0), repr=False)

    # -- data ------------------------------------------------------------
    def visible_rows(self, rows: list[dict], query: str = "") -> list[dict]:
        """Apply search and sorting, in that order (V27.2, V27.3)."""
        filtered = rows
        if query and self.search_key:
            needle = query.lower()
            filtered = [
                row for row in rows if needle in str(row.get(self.search_key, "")).lower()
            ]
        if self.sort_key:
            filtered = sorted(
                filtered,
                key=lambda row: _sort_value(row.get(self.sort_key)),
                reverse=self.sort_descending,
            )
        return filtered

    def _rows_that_fit(self, rect) -> int:
        """How many rows the panel has room for, below its header and footer."""
        available = rect.height - theme.HEADER_ROW_HEIGHT - FOOTER_HEIGHT
        return max(1, available // theme.ROW_HEIGHT)

    def page_count(self, total: int) -> int:
        return max(1, (total + self.page_size - 1) // self.page_size)

    def sort_by(self, key: str) -> None:
        """Choose the sort field, reversing direction when already sorted by it."""
        if self.sort_key == key:
            self.sort_descending = not self.sort_descending
        else:
            self.sort_key = key
            self.sort_descending = False
        self.page = 0

    # -- interaction -----------------------------------------------------
    def handle_event(self, event) -> bool:
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return False
        for key, rect in self._header_rects.items():
            if rect.collidepoint(event.pos):
                self.sort_by(key)
                return True
        if self._prev_rect.collidepoint(event.pos) and self.page > 0:
            self.page -= 1
            return True
        if self._next_rect.collidepoint(event.pos):
            self.page += 1
            return True
        for rect, row in self._row_rects:
            if rect.collidepoint(event.pos):
                # A single click opens a row; double-clicking is never required.
                self.opened_row = row
                return True
        return False

    def take_opened(self) -> dict | None:
        row, self.opened_row = self.opened_row, None
        return row

    # -- drawing ---------------------------------------------------------
    def draw(self, surface, rect, fonts, mouse, rows: list[dict], query: str = "",
             empty_message: str = "Nothing to show yet.") -> None:
        self._header_rects.clear()
        self._row_rects.clear()

        # A page holds as many rows as actually fit. A fixed count draws past
        # the bottom of the panel whenever a window is short or the page above
        # grows, and rows running off the edge look like a broken list rather
        # than a full one (V14.8: lists paginate).
        self.page_size = self._rows_that_fit(rect)

        visible = self.visible_rows(rows, query)
        pages = self.page_count(len(visible))
        self.page = max(0, min(self.page, pages - 1))
        start = self.page * self.page_size
        page_rows = visible[start:start + self.page_size]

        panel(surface, rect)
        x = rect.left + 16
        header_y = rect.top + theme.HEADER_ROW_HEIGHT // 2
        for column in self.columns:
            # Headers use the same inset as their cells; anything else makes a
            # right-aligned header collide with the next column's title.
            anchor = x + column.width - 12 if column.align == "right" else x
            label_rect = draw_text(
                surface, fonts.tiny, column.title.upper(), (anchor, header_y),
                theme.ACCENT if self.sort_key == column.key else theme.TEXT_FAINT,
                align=column.align, baseline="middle",
            )
            hit = pygame.Rect(x - 6, rect.top, column.width + 12, theme.HEADER_ROW_HEIGHT)
            self._header_rects[column.key] = hit
            if self.sort_key == column.key:
                side = label_rect.left - 11 if column.align == "right" else label_rect.right + 7
                _sort_marker(surface, (side, header_y), self.sort_descending)
            x += column.width

        line_y = rect.top + theme.HEADER_ROW_HEIGHT
        pygame.draw.line(surface, theme.BORDER, (rect.left + 8, line_y), (rect.right - 8, line_y))

        if not page_rows:
            # An empty list gets a clear, intentional empty state (V14.26).
            draw_text(surface, fonts.small,
                      empty_message if not query else f"No matches for “{query}”.",
                      (rect.centerx, line_y + 40), theme.TEXT_FAINT,
                      align="center", baseline="middle")
        for index, row in enumerate(page_rows):
            row_rect = pygame.Rect(
                rect.left + 6, line_y + 4 + index * theme.ROW_HEIGHT,
                rect.width - 12, theme.ROW_HEIGHT,
            )
            hovered = row_rect.collidepoint(mouse)
            if hovered:
                pygame.draw.rect(surface, theme.SURFACE_HOVER, row_rect, border_radius=4)
            self._row_rects.append((row_rect, row))

            cell_x = rect.left + 16
            for column in self.columns:
                value = row.get(column.key)
                text = column.render_value(value)
                font = fonts.mono_small if column.numeric else fonts.small
                colour = column.colour(value) if column.colour else theme.TEXT
                anchor = cell_x + column.width - 12 if column.align == "right" else cell_x
                draw_text(surface, font, truncate(font, text, column.width - 12),
                          (anchor, row_rect.centery), colour,
                          align=column.align, baseline="middle")
                cell_x += column.width

        self._draw_pagination(surface, rect, fonts, mouse, len(visible), pages, len(page_rows),
                              line_y)

    def _draw_pagination(self, surface, rect, fonts, mouse, total: int, pages: int,
                         rows_drawn: int = 0, content_top: int | None = None) -> None:
        bar_y = rect.bottom - 30
        # _rows_that_fit always leaves room for at least one row (V27.7), which
        # can still be more row than a very short panel has space for once the
        # notification safe-area comes out of that panel's rect too. Rather
        # than let the footer print on top of that row, it goes unshown: a
        # missing page count is a far smaller defect than text laid over text.
        if content_top is not None:
            content_bottom = content_top + 4 + rows_drawn * theme.ROW_HEIGHT
            if bar_y < content_bottom + 8:
                self._prev_rect = pygame.Rect(0, 0, 0, 0)
                self._next_rect = pygame.Rect(0, 0, 0, 0)
                return
        draw_text(surface, fonts.small,
                  f"{total} item{'s' if total != 1 else ''}",
                  (rect.left + 16, bar_y), theme.TEXT_FAINT, baseline="middle")
        if pages <= 1:
            self._prev_rect = pygame.Rect(0, 0, 0, 0)
            self._next_rect = pygame.Rect(0, 0, 0, 0)
            return

        self._next_rect = pygame.Rect(rect.right - 44, bar_y - 12, 28, 24)
        self._prev_rect = pygame.Rect(rect.right - 78, bar_y - 12, 28, 24)
        label = f"Page {self.page + 1} of {pages}"
        draw_text(surface, fonts.small, label, (self._prev_rect.left - 12, bar_y),
                  theme.TEXT_MUTED, align="right", baseline="middle")
        for control, enabled, forward in (
            (self._prev_rect, self.page > 0, False),
            (self._next_rect, self.page < pages - 1, True),
        ):
            hovered = enabled and control.collidepoint(mouse)
            panel(surface, control,
                  fill=theme.SURFACE_HOVER if hovered else theme.SURFACE_RAISED,
                  border=theme.BORDER)
            # Drawn rather than typed: arrow characters are missing from many
            # system fonts and render as an empty box.
            colour = theme.TEXT if enabled else theme.TEXT_FAINT
            chevron = icons.render("chevron", colour, 14)
            if not forward:
                chevron = pygame.transform.flip(chevron, True, False)
            surface.blit(chevron, chevron.get_rect(center=control.center))


def _sort_marker(surface, centre, descending: bool) -> None:
    """A small triangle showing sort direction.

    Drawn rather than typed: the arrow characters are missing from many system
    fonts and render as an empty box, which reads as a broken interface.
    """
    x, y = centre
    if descending:
        points = [(x - 4, y - 2), (x + 4, y - 2), (x, y + 3)]
    else:
        points = [(x - 4, y + 2), (x + 4, y + 2), (x, y - 3)]
    pygame.draw.polygon(surface, theme.ACCENT, points)


def _sort_value(value):
    """Sort text case-insensitively and everything else naturally."""
    if isinstance(value, str):
        return (1, value.lower())
    if value is None:
        return (0, "")
    try:
        return (0, float(value))
    except (TypeError, ValueError):
        return (1, str(value).lower())
