"""The button widget."""

from __future__ import annotations

import pygame

from .. import icons, theme
from .text import draw_text, draw_tooltip, panel


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
        # `tooltip` was set on every button since it was added but never once
        # read (formatting-consistency pass, 2026-08-10) — this is its only
        # consumer. Drawn last, above the button's own top edge, the same
        # primitive the Sidebar already uses for its own icon tooltips.
        if self.tooltip and hovered:
            draw_tooltip(surface, fonts, self.tooltip, (self.rect.left, self.rect.top - 20))
