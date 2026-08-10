"""Widgets the player types into or chooses from: search, tabs and dropdowns."""

from __future__ import annotations

import pygame

from .. import icons, theme
from .text import draw_text, panel


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
