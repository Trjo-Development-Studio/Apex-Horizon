"""Persistent interface chrome.

The parts of the interface that never go away: the sidebar (V14.4), breadcrumb
navigation (V14.6), simulation speed controls (V14.18), the save indicator
(V14.19), and the notification area (V14.16).

Together they are what keeps the player oriented — V14.23 asks that they always
know exactly where they are, and V27.4 that no page is ever a dead end.
"""

from __future__ import annotations

from dataclasses import dataclass

import pygame

from . import icons, theme
from .widgets import draw_text, draw_tooltip, panel


@dataclass(frozen=True)
class NavItem:
    """One destination in the sidebar (V14.5)."""

    key: str
    label: str
    icon: str


# The sections listed in V14.5, in that order.
NAV_ITEMS: tuple[NavItem, ...] = (
    NavItem("dashboard", "Dashboard", "dashboard"),
    NavItem("company", "Company", "company"),
    NavItem("investments", "Investments", "investments"),
    NavItem("market", "Market", "market"),
    NavItem("news", "News", "news"),
    NavItem("unlocks", "Unlock Tree", "unlocks"),
    NavItem("finance", "Financial Management", "finance"),
    NavItem("settings", "Settings", "settings"),
)


class Sidebar:
    """Permanent icon-only navigation down the left edge (V14.4).

    Icons are monochrome and carry no colour of their own; the active
    destination is marked with a single accent bar. Every icon shows its name on
    hover, because navigation must never depend on icon recognition alone
    (V27.10).
    """

    def __init__(self) -> None:
        self.active = "dashboard"
        self.hovered: NavItem | None = None
        self._rects: dict[str, pygame.Rect] = {}
        self.requested: str | None = None

    def handle_event(self, event) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for key, rect in self._rects.items():
                if rect.collidepoint(event.pos):
                    self.requested = key
                    return True
        return False

    def take_request(self) -> str | None:
        request, self.requested = self.requested, None
        return request

    def draw(self, surface, fonts, mouse) -> None:
        height = surface.get_height()
        rect = pygame.Rect(0, 0, theme.SIDEBAR_WIDTH, height)
        pygame.draw.rect(surface, theme.SURFACE, rect)
        pygame.draw.line(surface, theme.BORDER,
                         (theme.SIDEBAR_WIDTH, 0), (theme.SIDEBAR_WIDTH, height))

        # A restrained wordmark: the initials, not a logo.
        draw_text(surface, fonts.subheading, "AH", (theme.SIDEBAR_WIDTH // 2, 22),
                  theme.ACCENT, align="center", baseline="middle")

        self._rects.clear()
        self.hovered = None
        top = 60
        for index, item in enumerate(NAV_ITEMS):
            item_rect = pygame.Rect(8, top + index * 52, theme.SIDEBAR_WIDTH - 16, 44)
            self._rects[item.key] = item_rect
            active = item.key == self.active
            hovered = item_rect.collidepoint(mouse)
            if hovered:
                self.hovered = item
            if active:
                pygame.draw.rect(surface, theme.SURFACE_RAISED, item_rect, border_radius=6)
                pygame.draw.rect(surface, theme.ACCENT,
                                 pygame.Rect(0, item_rect.top + 10, 3, 24), border_radius=2)
            colour = theme.TEXT if active else (
                theme.TEXT_MUTED if hovered else theme.TEXT_FAINT
            )
            icons.draw(surface, item.icon, colour, item_rect.center, 22)

    def draw_tooltip(self, surface, fonts) -> None:
        """Drawn last so the label sits above the page beneath it."""
        if self.hovered is None:
            return
        rect = self._rects[self.hovered.key]
        draw_tooltip(surface, fonts, self.hovered.label, (rect.right + 10, rect.centery))


class Breadcrumb:
    """Clickable path showing where the player is (V14.6, V27.4).

    Behaves like a file explorer: every segment is clickable and selecting one
    returns immediately to that level, so there is always a way back.
    """

    def __init__(self) -> None:
        self.segments: list[tuple[str, str]] = []  # (label, destination key)
        self._rects: list[tuple[pygame.Rect, str]] = []
        self.requested: str | None = None

    def set(self, segments: list[tuple[str, str]]) -> None:
        self.segments = segments

    def handle_event(self, event) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for rect, destination in self._rects:
                if rect.collidepoint(event.pos):
                    self.requested = destination
                    return True
        return False

    def take_request(self) -> str | None:
        request, self.requested = self.requested, None
        return request

    def draw(self, surface, fonts, mouse, origin: tuple[int, int]) -> None:
        self._rects.clear()
        x, y = origin
        last = len(self.segments) - 1
        for index, (label, destination) in enumerate(self.segments):
            is_last = index == last
            colour = theme.TEXT if is_last else theme.TEXT_MUTED
            rect = draw_text(surface, fonts.small, label, (x, y), colour, baseline="middle")
            if not is_last:
                # Only earlier segments navigate; the last one is where we are.
                hit = rect.inflate(8, 12)
                self._rects.append((hit, destination))
                if hit.collidepoint(mouse):
                    draw_text(surface, fonts.small, label, (x, y), theme.ACCENT,
                              baseline="middle")
                icons.draw(surface, "chevron", theme.TEXT_FAINT, (rect.right + 12, y), 12)
                x = rect.right + 24
            else:
                x = rect.right


class TimeControls:
    """Simulation speed, always visible (V14.18).

    The Design Bible is precise here: the player may run at x1, x2 or x3, and
    pausing happens *only* through popups (V13.20). There is deliberately no
    pause button.
    """

    def __init__(self, speeds: tuple[int, ...] = (1, 2, 3)):
        self.speeds = speeds
        self._rects: dict[int, pygame.Rect] = {}
        self.requested: int | None = None

    def handle_event(self, event) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for speed, rect in self._rects.items():
                if rect.collidepoint(event.pos):
                    self.requested = speed
                    return True
        return False

    def take_request(self) -> int | None:
        request, self.requested = self.requested, None
        return request

    def draw(self, surface, fonts, mouse, right: int, centre_y: int,
             current: int, paused: bool) -> pygame.Rect:
        width = len(self.speeds) * 34 + 8
        rect = pygame.Rect(right - width, centre_y - 14, width, 28)
        panel(surface, rect, fill=theme.SURFACE_RAISED, border=theme.BORDER)
        self._rects.clear()
        for index, speed in enumerate(self.speeds):
            cell = pygame.Rect(rect.left + 4 + index * 34, rect.top + 3, 30, 22)
            self._rects[speed] = cell
            active = speed == current and not paused
            if active:
                pygame.draw.rect(surface, theme.ACCENT, cell, border_radius=4)
            elif cell.collidepoint(mouse):
                pygame.draw.rect(surface, theme.SURFACE_HOVER, cell, border_radius=4)
            colour = (255, 255, 255) if active else theme.TEXT_MUTED
            draw_text(surface, fonts.small, f"×{speed}", cell.center, colour,  # noqa: RUF001 (multiplication sign is intended)
                      align="center", baseline="middle")
        if paused:
            # Paused is a state the player is told about, not a control.
            draw_text(surface, fonts.tiny, "PAUSED", (rect.left - 12, centre_y),
                      theme.WARNING, align="right", baseline="middle")
        return rect


class SaveIndicator:
    """Shows whether there are unsaved changes (V14.19, V13.22)."""

    def __init__(self) -> None:
        self.unsaved = False

    def draw(self, surface, fonts, right: int, centre_y: int) -> pygame.Rect:
        text = "Unsaved changes" if self.unsaved else "All changes saved"
        colour = theme.WARNING if self.unsaved else theme.TEXT_FAINT
        rect = draw_text(surface, fonts.small, text, (right, centre_y), colour,
                         align="right", baseline="middle")
        pygame.draw.circle(surface, colour, (rect.left - 12, centre_y), 3)
        return rect


@dataclass
class Notification:
    """A passing message. Notifications never pause the game (V13.21)."""

    text: str
    created_ms: int
    lifetime_ms: int = 5200
    emphasis: bool = False


class NotificationCentre:
    """Messages that slide in at the lower left and slide away (V14.16, V27.7).

    The stack is capped so that older, still-relevant messages are never pushed
    out of view before the player has had a chance to read them.
    """

    MAX_VISIBLE = 4

    def __init__(self) -> None:
        self.items: list[Notification] = []

    def push(self, text: str, now_ms: int, *, emphasis: bool = False) -> None:
        self.items.append(Notification(text, now_ms, emphasis=emphasis))
        # Keep the queue short; the oldest are the ones already read.
        del self.items[: -12]

    def update(self, now_ms: int) -> None:
        self.items = [
            item for item in self.items if now_ms - item.created_ms < item.lifetime_ms
        ]

    def draw(self, surface, fonts, now_ms: int) -> None:
        visible = self.items[-self.MAX_VISIBLE:]
        bottom = surface.get_height() - 20
        for index, item in enumerate(reversed(visible)):
            age = now_ms - item.created_ms
            if age < 0:
                # A timestamp from ahead of the clock would otherwise park the
                # message off-screen forever; show it rather than lose it.
                age = theme.SLIDE_MS
            # Slide in on arrival and out again as the message expires (V27.8).
            # Both ends are clamped: an out-of-range age must never place a
            # message off the edge of the screen where it cannot be read.
            entering = min(1.0, max(0.0, age / theme.SLIDE_MS))
            remaining = item.lifetime_ms - age
            leaving = min(1.0, max(0.0, remaining) / theme.SLIDE_MS)
            progress = max(0.0, min(entering, leaving))
            offset = int((1.0 - progress) * (theme.NOTIFICATION_WIDTH + 24))

            rect = pygame.Rect(
                20 + theme.SIDEBAR_WIDTH - offset,
                bottom - (index + 1) * (theme.NOTIFICATION_HEIGHT + theme.NOTIFICATION_GAP),
                theme.NOTIFICATION_WIDTH,
                theme.NOTIFICATION_HEIGHT,
            )
            border = theme.ACCENT if item.emphasis else theme.BORDER_STRONG
            panel(surface, rect, fill=theme.SURFACE_RAISED, border=border)
            if item.emphasis:
                # Breaking news may carry more emphasis than routine messages
                # (V10.14, V27.7).
                pygame.draw.rect(surface, theme.ACCENT,
                                 pygame.Rect(rect.left, rect.top + 8, 3, rect.height - 16),
                                 border_radius=2)
            from .widgets import truncate
            draw_text(surface, fonts.small,
                      truncate(fonts.small, item.text, rect.width - 32),
                      (rect.left + 16, rect.centery), theme.TEXT, baseline="middle")
