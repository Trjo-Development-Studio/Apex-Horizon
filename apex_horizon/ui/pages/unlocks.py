"""The Unlock Tree page.

V6.10 asks for a professional roadmap: large spacing, clean alignment, straight
horizontal connections, no crossing lines, and a layout where the player always
understands how every branch connects back to Basic Investing. That shapes the
whole design here.

The tree is laid out on a grid rather than drawn ad hoc — the primary
progression along row 0 (V6.5), the Analytics branch above it and the News
branch below (V6.6), the five Company Level 2 branches stacked in the order
V6.7 gives, and Investment Funds alone on the right where every branch converges
(V6.8). Connections are drawn as elbows: down or up a shared vertical, then
straight across. Because each branch owns its own row, no two connections ever
cross.

Thirty-two nodes do not fit on one screen at a readable size, so the view pans —
by dragging, or with the arrow keys. Zooming out far enough to fit everything
would defeat V6.10's readability requirement.
"""

from __future__ import annotations

import pygame

from ...engine.unlocks import (
    ANALYTICS_BRANCH,
    COMPANY_BRANCH,
    EMPLOYEE_BRANCH,
    FINAL,
    FINANCE_BRANCH,
    NEWS_BRANCH,
    PRIMARY,
    RECRUITMENT_BRANCH,
    TRAINING_BRANCH,
)
from .. import theme
from ..widgets import Button, Card, draw_text, panel, truncate
from .base import Page

NODE_WIDTH = 168
NODE_HEIGHT = 78
COLUMN_STEP = 208
ROW_STEP = 96
PAN_STEP = 60
#: A fixed strip on the left holding branch names, which never scrolls.
GUTTER_WIDTH = 104

#: Row for each branch, and the column its first node sits in. The five Company
#: Level 2 branches follow the top-to-bottom order V6.7 states.
LAYOUT: dict[str, tuple[int, int]] = {
    ANALYTICS_BRANCH: (-1, 1),
    PRIMARY: (0, 0),
    NEWS_BRANCH: (1, 1),
    FINANCE_BRANCH: (2, 3),
    EMPLOYEE_BRANCH: (3, 3),
    COMPANY_BRANCH: (4, 2),
    TRAINING_BRANCH: (5, 3),
    RECRUITMENT_BRANCH: (6, 3),
    FINAL: (3, 8),
}

BRANCH_LABELS = {
    ANALYTICS_BRANCH: "Analytics",
    NEWS_BRANCH: "News",
    FINANCE_BRANCH: "Finance",
    EMPLOYEE_BRANCH: "Employees",
    COMPANY_BRANCH: "Company",
    TRAINING_BRANCH: "Training",
    RECRUITMENT_BRANCH: "Recruitment",
}


class UnlockTreePage(Page):
    """The player's map of their own future (V6.14)."""

    key = "unlocks"
    TITLE = "Unlock Tree"
    SUBTITLE = "Everything your company can become"

    def __init__(self, context):
        super().__init__(context)
        self._buttons: dict[str, Button] = {}
        self.unlock_request: str | None = None
        #: How far the view has been panned, in pixels.
        self.offset = [0, 0]
        self._dragging = False
        self._drag_origin = (0, 0)
        self._node_rects: dict[str, pygame.Rect] = {}

    def take_unlock_request(self) -> str | None:
        request, self.unlock_request = self.unlock_request, None
        return request

    def _button(self, key: str) -> Button:
        if key not in self._buttons:
            self._buttons[key] = Button("Unlock", primary=True)
        return self._buttons[key]

    # -- layout ------------------------------------------------------------
    def _position(self, tree, unlock) -> tuple[int, int]:
        """Grid position (row, column) for one unlock."""
        row, first_column = LAYOUT.get(unlock.branch, (0, 0))
        return row, first_column + unlock.position

    def cards(self) -> list[Card]:
        tree = self.context.unlocks
        player = self.context.player
        if tree is None:
            return []
        available = tree.available()
        buyable = [
            unlock for unlock in available
            if player is not None and player.cash >= tree.cost_of(unlock.key)
        ]
        return [
            Card("Unlocked", f"{len(tree.unlocked)} of {len(tree.all)}",
                 "Progress through the tree"),
            Card("Available now", str(len(available)),
                 f"{len(buyable)} you can afford"),
            Card("Next", available[0].name if available else "—",
                 tree.cost_of(available[0].key).format(decimals=0) if available
                 else "Nothing available"),
        ]

    # -- interaction -------------------------------------------------------
    def handle_event(self, event) -> bool:
        tree = self.context.unlocks
        if tree is None:
            return False

        for unlock in tree.all:
            button = self._button(unlock.key)
            if not button.enabled:
                continue
            if button.handle_event(event) and button.take_click():
                self.unlock_request = unlock.key
                return True

        if event.type == pygame.KEYDOWN:
            moves = {
                pygame.K_LEFT: (-PAN_STEP, 0), pygame.K_RIGHT: (PAN_STEP, 0),
                pygame.K_UP: (0, -PAN_STEP), pygame.K_DOWN: (0, PAN_STEP),
            }
            if event.key in moves:
                dx, dy = moves[event.key]
                self.offset[0] += dx
                self.offset[1] += dy
                return True
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._dragging = True
            self._drag_origin = event.pos
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self._dragging = False
        elif event.type == pygame.MOUSEMOTION and self._dragging:
            x, y = event.pos
            self.offset[0] -= x - self._drag_origin[0]
            self.offset[1] -= y - self._drag_origin[1]
            self._drag_origin = (x, y)
            return True
        return False

    # -- drawing -----------------------------------------------------------
    def draw_content(self, surface, rect, fonts, mouse) -> None:
        tree = self.context.unlocks
        player = self.context.player
        if tree is None:
            panel(surface, pygame.Rect(rect.left, rect.top, rect.width, 140))
            draw_text(surface, fonts.body, "The Unlock Tree is unavailable.",
                      (rect.left + 24, rect.top + 56), theme.TEXT_MUTED)
            return

        draw_text(surface, fonts.small,
                  "Every unlock requires the one before it. Drag or use the arrow "
                  "keys to move around the tree.",
                  (rect.left, rect.top), theme.TEXT_MUTED)

        view = pygame.Rect(rect.left, rect.top + 26, rect.width,
                           max(0, rect.height - 26))
        panel(surface, view)
        self._clamp(view)

        # Everything inside the map is clipped to it, so a node panned past the
        # edge does not spill over the rest of the interface.
        previous_clip = surface.get_clip()
        surface.set_clip(view)

        self._node_rects = {
            unlock.key: self._rect_for(tree, unlock, view) for unlock in tree.all
        }
        self._draw_connections(surface, tree)
        for unlock in tree.all:
            node = self._node_rects[unlock.key]
            if node.colliderect(view):
                self._draw_node(surface, node, fonts, mouse, unlock, tree, player)
            else:
                self._button(unlock.key).enabled = False

        # Branch names sit in a fixed gutter drawn over the map. Scrolling them
        # with the nodes would let them collide with whatever panned underneath;
        # keeping them still means the player can always tell which row is which.
        self._draw_branch_labels(surface, fonts, tree, view)
        surface.set_clip(previous_clip)

    def _clamp(self, view: pygame.Rect) -> None:
        """Keep the map from being panned entirely out of sight."""
        rows = [row for row, _ in LAYOUT.values()]
        width = (max(column for _, column in LAYOUT.values()) + 1) * COLUMN_STEP
        height = (max(rows) - min(rows) + 1) * ROW_STEP
        self.offset[0] = max(0, min(self.offset[0], max(0, width - view.width + 80)))
        self.offset[1] = max(0, min(self.offset[1], max(0, height - view.height + 80)))

    def _rect_for(self, tree, unlock, view: pygame.Rect) -> pygame.Rect:
        row, column = self._position(tree, unlock)
        rows = [r for r, _ in LAYOUT.values()]
        x = view.left + GUTTER_WIDTH + 20 + column * COLUMN_STEP - self.offset[0]
        y = view.top + 40 + (row - min(rows)) * ROW_STEP - self.offset[1]
        return pygame.Rect(x, y, NODE_WIDTH, NODE_HEIGHT)

    def _draw_connections(self, surface, tree) -> None:
        """Elbow connections: along a shared vertical, then straight across."""
        for unlock in tree.all:
            target = self._node_rects[unlock.key]
            for requirement in unlock.requires:
                source = self._node_rects.get(requirement)
                if source is None:
                    continue
                done = tree.has(requirement) and tree.has(unlock.key)
                colour = theme.POSITIVE if done else theme.BORDER
                start = (source.right, source.centery)
                end = (target.left, target.centery)
                if start[1] == end[1]:
                    pygame.draw.line(surface, colour, start, end, 2)
                    continue
                # Drop or rise on a vertical midway between the columns, then
                # run straight in — which is what keeps lines from crossing.
                midway = (start[0] + end[0]) // 2
                pygame.draw.line(surface, colour, start, (midway, start[1]), 2)
                pygame.draw.line(surface, colour, (midway, start[1]), (midway, end[1]), 2)
                pygame.draw.line(surface, colour, (midway, end[1]), end, 2)

    def _draw_branch_labels(self, surface, fonts, tree, view: pygame.Rect) -> None:
        gutter = pygame.Rect(view.left + 1, view.top + 1, GUTTER_WIDTH, view.height - 2)
        pygame.draw.rect(surface, theme.SURFACE, gutter)
        pygame.draw.line(surface, theme.BORDER,
                         (gutter.right, gutter.top), (gutter.right, gutter.bottom))
        for branch, label in BRANCH_LABELS.items():
            nodes = tree.branch(branch)
            if not nodes:
                continue
            first = self._node_rects[nodes[0].key]
            if not (view.top < first.centery < view.bottom):
                continue
            draw_text(surface, fonts.small, truncate(fonts.small, label.upper(),
                                                     GUTTER_WIDTH - 16),
                      (gutter.left + 10, first.centery - 8), theme.TEXT_FAINT)

    def _draw_node(self, surface, rect, fonts, mouse, unlock, tree, player) -> None:
        owned = tree.has(unlock.key)
        ready = not owned and tree.prerequisites_met(unlock.key) and unlock.implemented
        panel(surface, rect)
        if owned:
            pygame.draw.rect(surface, theme.POSITIVE, rect, 2, border_radius=8)
        elif ready:
            pygame.draw.rect(surface, theme.ACCENT_MUTED, rect, 1, border_radius=8)

        draw_text(surface, fonts.small,
                  truncate(fonts.small, unlock.name, rect.width - 24),
                  (rect.left + 12, rect.top + 10),
                  theme.TEXT if owned or ready else theme.TEXT_MUTED)

        button = self._button(unlock.key)
        if owned:
            button.enabled = False
            draw_text(surface, fonts.small, "Unlocked",
                      (rect.left + 12, rect.top + 34), theme.POSITIVE)
            return
        if not unlock.implemented:
            button.enabled = False
            draw_text(surface, fonts.small, "Coming later",
                      (rect.left + 12, rect.top + 34), theme.TEXT_FAINT)
            return

        cost = tree.cost_of(unlock.key)
        if not ready:
            button.enabled = False
            draw_text(surface, fonts.small, "Locked",
                      (rect.left + 12, rect.top + 34), theme.TEXT_FAINT)
            draw_text(surface, fonts.small, cost.format(decimals=0),
                      (rect.right - 12, rect.top + 34), theme.TEXT_FAINT, align="right")
            return

        affordable = player is not None and player.cash >= cost
        button.enabled = affordable
        draw_text(surface, fonts.small, cost.format(decimals=0),
                  (rect.left + 12, rect.top + 34),
                  theme.TEXT if affordable else theme.NEGATIVE)
        button.draw(surface, pygame.Rect(rect.right - 80, rect.bottom - 32, 68, 24),
                    fonts, mouse)
