"""Interface components.

Every page is assembled from these, which is what makes the consistency V14.20
requires structural rather than a matter of discipline (V14.28): learning how a
list behaves on one page teaches the player how every other list behaves
(V27.11).

Behaviour follows the standards of Volume 27 — search filters as the player
types (V27.2), sorting is chosen explicitly and remembered per list (V27.3),
tables place one row per entity with numeric columns aligned for comparison
(V27.5), and a single click opens a row, never a double click (V14.8).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

import pygame

from . import icons, theme


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


def panel(surface, rect, *, fill=theme.SURFACE, border=theme.BORDER, radius=theme.CORNER):
    pygame.draw.rect(surface, fill, rect, border_radius=radius)
    if border is not None:
        pygame.draw.rect(surface, border, rect, 1, border_radius=radius)


class Button:
    """A labelled action, optionally with an icon.

    Buttons report whether they were pressed rather than invoking callbacks
    during drawing, so game logic never runs inside a render pass (V15.5).
    """

    def __init__(self, label: str, *, icon: str | None = None, primary: bool = False,
                 enabled: bool = True, tooltip: str = ""):
        self.label = label
        self.icon = icon
        self.primary = primary
        self.enabled = enabled
        self.tooltip = tooltip
        self.rect = pygame.Rect(0, 0, 0, 0)
        self._pressed = False

    def handle_event(self, event) -> bool:
        if not self.enabled:
            return False
        if (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
                and self.rect.collidepoint(event.pos)):
            self._pressed = True
            return True
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            was = self._pressed
            self._pressed = False
            if was and self.rect.collidepoint(event.pos):
                self.clicked = True
                return True
        return False

    clicked = False

    def take_click(self) -> bool:
        """Consume a pending click, if there is one."""
        if self.clicked:
            self.clicked = False
            return True
        return False

    def draw(self, surface, rect, fonts, mouse):
        self.rect = pygame.Rect(rect)
        hovered = self.enabled and self.rect.collidepoint(mouse)
        if not self.enabled:
            fill, text_colour, border = theme.SURFACE, theme.TEXT_FAINT, theme.BORDER
        elif self.primary:
            fill = theme.mix(theme.ACCENT, theme.TEXT, 0.12) if hovered else theme.ACCENT
            text_colour, border = (255, 255, 255), None
        else:
            fill = theme.SURFACE_HOVER if hovered else theme.SURFACE_RAISED
            text_colour, border = theme.TEXT, theme.BORDER
        panel(surface, self.rect, fill=fill, border=border)

        content_x = self.rect.centerx
        if self.icon:
            label_width = fonts.small.size(self.label)[0]
            total = label_width + 24
            icons.draw(surface, self.icon, text_colour,
                       (self.rect.centerx - total // 2 + 8, self.rect.centery), 16)
            content_x = self.rect.centerx + 12
        draw_text(surface, fonts.small, self.label, (content_x, self.rect.centery),
                  text_colour, align="center", baseline="middle")


class SearchBox:
    """A filter that narrows a list as the player types (V14.9, V27.2)."""

    def __init__(self, placeholder: str = "Search"):
        self.placeholder = placeholder
        self.text = ""
        self.focused = False
        self.rect = pygame.Rect(0, 0, 0, 0)

    def handle_event(self, event) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.focused = self.rect.collidepoint(event.pos)
            return self.focused
        if not self.focused or event.type != pygame.KEYDOWN:
            return False
        if event.key == pygame.K_BACKSPACE:
            self.text = self.text[:-1]
        elif event.key == pygame.K_ESCAPE:
            self.text = ""
            self.focused = False
        elif event.unicode and event.unicode.isprintable():
            self.text += event.unicode
        else:
            return False
        return True

    def draw(self, surface, rect, fonts, mouse):
        self.rect = pygame.Rect(rect)
        border = theme.ACCENT if self.focused else theme.BORDER
        panel(surface, self.rect, fill=theme.SURFACE_RAISED, border=border)
        icons.draw(surface, "search", theme.TEXT_FAINT,
                   (self.rect.left + 18, self.rect.centery), 16)
        if self.text:
            draw_text(surface, fonts.small, self.text, (self.rect.left + 34, self.rect.centery),
                      theme.TEXT, baseline="middle")
        else:
            draw_text(surface, fonts.small, self.placeholder,
                      (self.rect.left + 34, self.rect.centery), theme.TEXT_FAINT,
                      baseline="middle")


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


@dataclass
class Table:
    """A searchable, sortable, paginated list of entities.

    Sorting is explicit and remembered for this specific list (V27.3); search
    combines with it additively rather than replacing it.
    """

    columns: Sequence[Column]
    search_key: str | None = None
    page_size: int = 12
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
    def draw(self, surface, rect, fonts, mouse, rows: list[dict], query: str = "") -> None:
        self._header_rects.clear()
        self._row_rects.clear()

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
                      "Nothing to show yet." if not query else f"No matches for “{query}”.",
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

        self._draw_pagination(surface, rect, fonts, mouse, len(visible), pages)

    def _draw_pagination(self, surface, rect, fonts, mouse, total: int, pages: int) -> None:
        bar_y = rect.bottom - 30
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


@dataclass
class Card:
    """A summary figure. Cards are the primary way information is shown (V14.13)."""

    label: str
    value: str
    detail: str = ""
    accent: tuple[int, int, int] | None = None

    def draw(self, surface, rect, fonts) -> None:
        panel(surface, rect, fill=theme.SURFACE)
        draw_text(surface, fonts.tiny, self.label.upper(),
                  (rect.left + 16, rect.top + 14), theme.TEXT_FAINT)
        draw_text(surface, fonts.heading, self.value,
                  (rect.left + 16, rect.top + 34), self.accent or theme.TEXT)
        if self.detail:
            draw_text(surface, fonts.small, self.detail,
                      (rect.left + 16, rect.bottom - 24), theme.TEXT_MUTED)


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
