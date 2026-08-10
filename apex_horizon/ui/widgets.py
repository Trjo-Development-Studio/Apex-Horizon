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
            from .charts import meter

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


class Tabs:
    """A selector between views of one system.

    V14.5 wants the sidebar to list *systems*, so closely related views belong
    inside the system they describe rather than beside it in the navigation.
    Tabs are how a page holds several views without becoming several
    destinations, and they keep V14.20's page order intact: the tab strip sits
    with the content, below the cards, not in place of the breadcrumb.
    """

    def __init__(self, labels: list[str], selected: str | None = None):
        self.labels = labels
        self.selected = selected or (labels[0] if labels else "")
        self._rects: list[tuple[pygame.Rect, str]] = []

    def set_labels(self, labels: list[str]) -> None:
        """Update the available views, keeping the selection if it survives."""
        self.labels = labels
        if self.selected not in labels:
            self.selected = labels[0] if labels else ""

    def handle_event(self, event) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for rect, label in self._rects:
                if rect.collidepoint(event.pos):
                    self.selected = label
                    return True
        return False

    def height(self) -> int:
        return 38

    def draw(self, surface, rect, fonts, mouse) -> None:
        self._rects.clear()
        x = rect.left
        for label in self.labels:
            width = fonts.small.size(label)[0] + 32
            tab = pygame.Rect(x, rect.top, width, 32)
            self._rects.append((tab, label))
            active = label == self.selected
            hovered = tab.collidepoint(mouse)
            if active:
                pygame.draw.rect(surface, theme.SURFACE_RAISED, tab, border_radius=6)
            elif hovered:
                pygame.draw.rect(surface, theme.SURFACE, tab, border_radius=6)
            draw_text(surface, fonts.small, label, (tab.centerx, tab.centery),
                      theme.TEXT if active else (
                          theme.TEXT_MUTED if hovered else theme.TEXT_FAINT),
                      align="center", baseline="middle")
            if active:
                pygame.draw.rect(surface, theme.ACCENT,
                                 pygame.Rect(tab.left + 10, tab.bottom - 2,
                                             tab.width - 20, 2), border_radius=1)
            x += width + 4


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


class Dropdown:
    """A menu that opens to show its options.

    V5.5 and V5.15 call for department priorities to be chosen with dropdown
    menus. The open list is drawn in a later pass than the rest of the page, so
    it always sits above the content beneath it rather than being covered by it.
    """

    def __init__(self, options: list[str], selected: str, *, width: int = 150):
        self.options = options
        self.selected = selected
        self.width = width
        self.open = False
        self.rect = pygame.Rect(0, 0, 0, 0)
        self._option_rects: list[tuple[pygame.Rect, str]] = []
        self.changed_to: str | None = None

    def handle_event(self, event) -> bool:
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return False
        if self.open:
            for rect, option in self._option_rects:
                if rect.collidepoint(event.pos):
                    if option != self.selected:
                        self.selected = option
                        self.changed_to = option
                    self.open = False
                    return True
            self.open = False
            return self.rect.collidepoint(event.pos)
        if self.rect.collidepoint(event.pos):
            self.open = True
            return True
        return False

    def take_change(self) -> str | None:
        change, self.changed_to = self.changed_to, None
        return change

    def draw(self, surface, rect, fonts, mouse) -> None:
        self.rect = pygame.Rect(rect)
        hovered = self.rect.collidepoint(mouse)
        panel(surface, self.rect,
              fill=theme.SURFACE_HOVER if hovered or self.open else theme.SURFACE_RAISED,
              border=theme.ACCENT if self.open else theme.BORDER)
        draw_text(surface, fonts.small, self.selected,
                  (self.rect.left + 10, self.rect.centery), theme.TEXT, baseline="middle")
        chevron = icons.render("chevron", theme.TEXT_FAINT, 12)
        chevron = pygame.transform.rotate(chevron, -90)
        surface.blit(chevron, chevron.get_rect(center=(self.rect.right - 14, self.rect.centery)))

    def draw_open(self, surface, fonts, mouse) -> None:
        """Draw the expanded list. Called after the page, so it sits on top."""
        self._option_rects.clear()
        if not self.open:
            return
        height = len(self.options) * 26 + 8
        panel_rect = pygame.Rect(self.rect.left, self.rect.bottom + 2, self.rect.width, height)
        panel(surface, panel_rect, fill=theme.SURFACE_RAISED, border=theme.BORDER_STRONG)
        for index, option in enumerate(self.options):
            option_rect = pygame.Rect(panel_rect.left + 4, panel_rect.top + 4 + index * 26,
                                      panel_rect.width - 8, 24)
            self._option_rects.append((option_rect, option))
            if option_rect.collidepoint(mouse):
                pygame.draw.rect(surface, theme.SURFACE_HOVER, option_rect, border_radius=4)
            colour = theme.ACCENT if option == self.selected else theme.TEXT
            draw_text(surface, fonts.small, option,
                      (option_rect.left + 8, option_rect.centery), colour, baseline="middle")
