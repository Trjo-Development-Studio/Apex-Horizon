"""The Unlock Tree page.

V6.10 asks for a professional roadmap: large spacing, clean alignment, straight
horizontal connections, no crossing lines, and a layout where the player always
understands how every branch connects back to Basic Investing. That shapes the
whole design here.

The tree is laid out on a grid rather than drawn ad hoc — the primary
progression along row 0 (V6.5), the Analytics branch above it and the News
branch below (V6.6), the five Company Level 2 branches stacked in the order
V6.7 gives, and Investment Funds and Subsidiaries together on the right where
every branch converges (V6.8). Connections are drawn as elbows: down or up a
shared vertical, then straight across. Because each branch owns its own row,
no two connections ever cross — a guarantee that is topological (fixed row and
column per branch), not pixel-based, which is what makes zooming safe (QoL
pass, 2026-08-10): scaling every dimension by the same factor cannot change
which row or column anything sits in, so it cannot introduce a crossing that
did not already exist.

Thirty-two-plus nodes do not fit on one screen at a readable size, so the view
pans — by dragging, the arrow keys, or scrolling — and zooms between three
preset levels rather than continuously: pygame's fonts are bitmap, not vector,
so a level between presets would blur text rather than shrink it cleanly,
which is exactly what V6.10's readability requirement rules out. A right-hand
panel shows whatever node is selected, built from the tree's own data rather
than a second copy of the same description written out again.
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
#: A fixed strip on the left holding branch names, which never scrolls or
#: scales with zoom — it is chrome, not part of the map.
GUTTER_WIDTH = 104
#: A fixed strip on the right showing whatever node is selected.
INFO_PANEL_WIDTH = 260

#: Discrete zoom presets, applied uniformly to every dimension of the map.
ZOOM_LEVELS: tuple[float, ...] = (0.75, 1.0, 1.4)
DEFAULT_ZOOM_INDEX = 1
#: Movement, in pixels, below which a mouse-down/up is a click rather than a
#: drag — a real drag rarely holds perfectly still, and a real click rarely
#: drifts this far.
CLICK_TOLERANCE = 6

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


def _wrap(surface, font, text, rect, colour) -> None:
    words, line, y = str(text).split(), "", rect.top
    for word in words:
        candidate = f"{line} {word}".strip()
        if font.size(candidate)[0] <= rect.width or not line:
            line = candidate
            continue
        draw_text(surface, font, line, (rect.left, y), colour)
        y += font.get_height() + 3
        line = word
    if line:
        draw_text(surface, font, line, (rect.left, y), colour)


class UnlockTreePage(Page):
    """The player's map of their own future (V6.14)."""

    key = "unlocks"
    TITLE = "Unlock Tree"
    SUBTITLE = "Everything your company can become"

    def __init__(self, context):
        super().__init__(context)
        self._buttons: dict[str, Button] = {}
        self.unlock_request: str | None = None
        #: How far the view has been panned, in pixels, at the current zoom.
        self.offset = [0, 0]
        self._dragging = False
        self._drag_origin = (0, 0)
        self._drag_distance = 0.0
        self._node_rects: dict[str, pygame.Rect] = {}
        #: Session-only UI state (V18 QoL pass, 2026-08-10) — deliberately not
        #: written to the save; reopening the tree starts at the default view.
        self.zoom_index = DEFAULT_ZOOM_INDEX
        self.selected_key: str | None = None
        self._pending_fit = False
        self.zoom_out_button = Button("-")
        self.zoom_in_button = Button("+")
        self.fit_button = Button("Fit")

    def take_unlock_request(self) -> str | None:
        request, self.unlock_request = self.unlock_request, None
        return request

    def _button(self, key: str) -> Button:
        if key not in self._buttons:
            self._buttons[key] = Button("Unlock", primary=True)
        return self._buttons[key]

    # -- zoom ----------------------------------------------------------------
    @property
    def zoom(self) -> float:
        return ZOOM_LEVELS[self.zoom_index]

    def _scaled(self, value: float) -> int:
        return round(value * self.zoom)

    def zoom_in(self) -> None:
        self.zoom_index = min(len(ZOOM_LEVELS) - 1, self.zoom_index + 1)

    def zoom_out(self) -> None:
        self.zoom_index = max(0, self.zoom_index - 1)

    def _tree_size(self, zoom: float) -> tuple[int, int]:
        rows = [row for row, _ in LAYOUT.values()]
        width = (max(column for _, column in LAYOUT.values()) + 1) * round(COLUMN_STEP * zoom)
        height = (max(rows) - min(rows) + 1) * round(ROW_STEP * zoom)
        return width, height

    def fit_to_screen(self, map_view: pygame.Rect) -> None:
        """The largest zoom preset whose full tree fits the map area, panned
        back to the top-left corner of it. Not a true center — supporting
        that would mean allowing a negative pan offset everywhere else this
        page clamps to zero — but every node is at least on screen and
        readable, which is what "fit" is actually for.
        """
        best = 0
        for index in range(len(ZOOM_LEVELS)):
            width, height = self._tree_size(ZOOM_LEVELS[index])
            if width <= map_view.width and height <= map_view.height:
                best = index
        self.zoom_index = best
        self.offset = [0, 0]

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

        if self.zoom_out_button.handle_event(event) and self.zoom_out_button.take_click():
            self.zoom_out()
            return True
        if self.zoom_in_button.handle_event(event) and self.zoom_in_button.take_click():
            self.zoom_in()
            return True
        if self.fit_button.handle_event(event) and self.fit_button.take_click():
            self._pending_fit = True
            return True

        for unlock in tree.all:
            button = self._button(unlock.key)
            if not button.enabled:
                continue
            if button.handle_event(event) and button.take_click():
                self.unlock_request = unlock.key
                return True

        if event.type == pygame.KEYDOWN:
            moves = {
                pygame.K_LEFT: (-1, 0), pygame.K_RIGHT: (1, 0),
                pygame.K_UP: (0, -1), pygame.K_DOWN: (0, 1),
            }
            if event.key in moves:
                dx, dy = moves[event.key]
                step = self._scaled(PAN_STEP)
                self.offset[0] += dx * step
                self.offset[1] += dy * step
                return True
        elif event.type == pygame.MOUSEWHEEL:
            # Not used anywhere else in the interface yet, so this is the
            # first place a wheel event can be read — the primary zoom
            # input, with the +/- buttons as a discoverable, always-visible
            # fallback for anyone whose input device has no wheel.
            if event.y > 0:
                self.zoom_in()
            elif event.y < 0:
                self.zoom_out()
            return True
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._dragging = True
            self._drag_origin = event.pos
            self._drag_distance = 0.0
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self._dragging = False
            # A click barely moved; a drag almost never holds this still.
            # Distinguishing the two is what lets a node be both draggable
            # (the map) and selectable (the node itself) with the same
            # mouse-down/mouse-up pair (bug avoided, not fixed: there was no
            # node selection before this to conflict with).
            if self._drag_distance <= CLICK_TOLERANCE:
                clicked = next(
                    (key for key, rect in self._node_rects.items()
                     if rect.collidepoint(event.pos)),
                    None,
                )
                if clicked is not None:
                    self.selected_key = clicked
                    return True
        elif event.type == pygame.MOUSEMOTION and self._dragging:
            x, y = event.pos
            dx, dy = x - self._drag_origin[0], y - self._drag_origin[1]
            self.offset[0] -= dx
            self.offset[1] -= dy
            self._drag_origin = (x, y)
            self._drag_distance += abs(dx) + abs(dy)
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

        header = pygame.Rect(rect.left, rect.top, rect.width, 30)
        draw_text(surface, fonts.small,
                  "Drag or use the arrow keys to move around the tree. "
                  "Scroll or use +/- to zoom.",
                  (header.left, header.top), theme.TEXT_MUTED)
        self._draw_zoom_controls(surface, header, fonts, mouse)

        view = pygame.Rect(rect.left, rect.top + 34, rect.width, max(0, rect.height - 34))
        panel(surface, view)
        if view.width <= 0 or view.height <= 0:
            return

        info_width = min(INFO_PANEL_WIDTH, max(0, view.width // 3))
        info_panel_rect = pygame.Rect(view.right - info_width, view.top, info_width, view.height)
        map_view = pygame.Rect(view.left, view.top, view.width - info_width, view.height)

        if self._pending_fit:
            self.fit_to_screen(pygame.Rect(0, 0, max(1, map_view.width - GUTTER_WIDTH - 20),
                                           max(1, map_view.height - 40)))
            self._pending_fit = False
        self._clamp(map_view)

        # Everything inside the map is clipped to it, so a node panned past the
        # edge does not spill over the rest of the interface.
        previous_clip = surface.get_clip()
        surface.set_clip(map_view)

        self._node_rects = {
            unlock.key: self._rect_for(tree, unlock, map_view) for unlock in tree.all
        }
        self._draw_connections(surface, tree)
        for unlock in tree.all:
            node = self._node_rects[unlock.key]
            if node.colliderect(map_view):
                self._draw_node(surface, node, fonts, mouse, unlock, tree, player)
            else:
                self._button(unlock.key).enabled = False

        # Branch names sit in a fixed gutter drawn over the map. Scrolling them
        # with the nodes would let them collide with whatever panned underneath;
        # keeping them still means the player can always tell which row is which.
        self._draw_branch_labels(surface, fonts, tree, map_view)
        surface.set_clip(previous_clip)

        self._draw_info_panel(surface, info_panel_rect, fonts, tree)

    def _draw_zoom_controls(self, surface, header: pygame.Rect, fonts, mouse) -> None:
        y = header.top - 3
        plus_rect = pygame.Rect(header.right - 28, y, 28, 26)
        minus_rect = pygame.Rect(plus_rect.left - 8 - 28, y, 28, 26)
        fit_rect = pygame.Rect(minus_rect.left - 8 - 56, y, 56, 26)
        self.zoom_out_button.enabled = self.zoom_index > 0
        self.zoom_in_button.enabled = self.zoom_index < len(ZOOM_LEVELS) - 1
        self.fit_button.draw(surface, fit_rect, fonts, mouse)
        self.zoom_out_button.draw(surface, minus_rect, fonts, mouse)
        self.zoom_in_button.draw(surface, plus_rect, fonts, mouse)

    def _clamp(self, map_view: pygame.Rect) -> None:
        """Keep the map from being panned entirely out of sight."""
        width, height = self._tree_size(self.zoom)
        self.offset[0] = max(0, min(self.offset[0], max(0, width - map_view.width + 80)))
        self.offset[1] = max(0, min(self.offset[1], max(0, height - map_view.height + 80)))

    def _rect_for(self, tree, unlock, map_view: pygame.Rect) -> pygame.Rect:
        row, column = self._position(tree, unlock)
        rows = [r for r, _ in LAYOUT.values()]
        x = (map_view.left + GUTTER_WIDTH + self._scaled(20) + column * self._scaled(COLUMN_STEP)
             - self.offset[0])
        y = (map_view.top + self._scaled(40) + (row - min(rows)) * self._scaled(ROW_STEP)
             - self.offset[1])
        return pygame.Rect(x, y, self._scaled(NODE_WIDTH), self._scaled(NODE_HEIGHT))

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

    def _draw_branch_labels(self, surface, fonts, tree, map_view: pygame.Rect) -> None:
        gutter = pygame.Rect(map_view.left + 1, map_view.top + 1, GUTTER_WIDTH, map_view.height - 2)
        pygame.draw.rect(surface, theme.SURFACE, gutter)
        pygame.draw.line(surface, theme.BORDER,
                         (gutter.right, gutter.top), (gutter.right, gutter.bottom))
        for branch, label in BRANCH_LABELS.items():
            nodes = tree.branch(branch)
            if not nodes:
                continue
            first = self._node_rects[nodes[0].key]
            if not (map_view.top < first.centery < map_view.bottom):
                continue
            draw_text(surface, fonts.small, truncate(fonts.small, label.upper(),
                                                     GUTTER_WIDTH - 16),
                      (gutter.left + 10, first.centery - 8), theme.TEXT_FAINT)

    def _draw_node(self, surface, rect, fonts, mouse, unlock, tree, player) -> None:
        label_font = fonts.tiny if self.zoom < 1.0 else fonts.small
        owned = tree.has(unlock.key)
        ready = not owned and tree.prerequisites_met(unlock.key) and unlock.implemented
        panel(surface, rect)
        if self.selected_key == unlock.key:
            pygame.draw.rect(surface, theme.ACCENT, rect, 2, border_radius=8)
        elif owned:
            pygame.draw.rect(surface, theme.POSITIVE, rect, 2, border_radius=8)
        elif ready:
            pygame.draw.rect(surface, theme.ACCENT_MUTED, rect, 1, border_radius=8)

        pad = self._scaled(12)
        name_y = rect.top + self._scaled(10)
        status_y = rect.top + self._scaled(34)
        draw_text(surface, label_font,
                  truncate(label_font, unlock.name, rect.width - pad * 2),
                  (rect.left + pad, name_y),
                  theme.TEXT if owned or ready else theme.TEXT_MUTED)

        button = self._button(unlock.key)
        if owned:
            button.enabled = False
            draw_text(surface, label_font, "Unlocked", (rect.left + pad, status_y), theme.POSITIVE)
            return
        if not unlock.implemented:
            button.enabled = False
            draw_text(surface, label_font, "Coming later", (rect.left + pad, status_y),
                      theme.TEXT_FAINT)
            return

        cost = tree.cost_of(unlock.key)
        if not ready:
            button.enabled = False
            draw_text(surface, label_font, "Locked", (rect.left + pad, status_y), theme.TEXT_FAINT)
            draw_text(surface, label_font, cost.format(decimals=0),
                      (rect.right - pad, status_y), theme.TEXT_FAINT, align="right")
            return

        affordable = player is not None and player.cash >= cost
        button.enabled = affordable
        draw_text(surface, label_font, cost.format(decimals=0),
                  (rect.left + pad, status_y),
                  theme.TEXT if affordable else theme.NEGATIVE)
        button.draw(surface, pygame.Rect(
            rect.right - self._scaled(80), rect.bottom - self._scaled(32),
            self._scaled(68), self._scaled(24)), fonts, mouse)

    def _draw_info_panel(self, surface, rect, fonts, tree) -> None:
        """What the tree itself knows about the selected unlock (V6.14).

        Deliberately reads Unlock.description/.requires and the tree's own
        prerequisite/ownership state rather than a second, hand-written
        summary of the same node that would drift out of sync with the
        first (bug class avoided: the earlier per-node cards already show
        cost/status this way; this panel goes further into prerequisites
        and what a purchase unlocks, still from the same source of truth).
        """
        panel(surface, rect)
        if rect.width < 60 or rect.height < 20:
            return
        # Bound-checked against rect.bottom throughout, and clipped besides:
        # this panel sits directly above the notification stack's reserved
        # area (V27.7), and a locked unlock can have seven prerequisites to
        # list — on a short window under a full stack there is no guarantee
        # all of it fits, and the alternative to stopping early is spilling
        # into whatever is drawn next (bug fix, 2026-08-10).
        previous_clip = surface.get_clip()
        surface.set_clip(rect)
        unlock = tree.by_key.get(self.selected_key) if self.selected_key else None
        if unlock is None:
            if rect.height >= 40:
                draw_text(surface, fonts.small, "Click a node to see its details.",
                          (rect.left + 16, rect.top + 20), theme.TEXT_FAINT)
            surface.set_clip(previous_clip)
            return

        owned = tree.has(unlock.key)
        ready = not owned and tree.prerequisites_met(unlock.key) and unlock.implemented
        y = rect.top + 18
        if y > rect.bottom - 20:
            surface.set_clip(previous_clip)
            return
        draw_text(surface, fonts.subheading,
                  truncate(fonts.subheading, unlock.name, rect.width - 32), (rect.left + 16, y))
        y += 30

        if y <= rect.bottom - 20:
            _wrap(surface, fonts.small, unlock.description,
                  pygame.Rect(rect.left + 16, y, rect.width - 32, max(0, rect.bottom - y - 4)),
                  theme.TEXT_MUTED)
        y += 70

        if not unlock.implemented:
            status_label, status_colour = "Not implemented yet", theme.TEXT_FAINT
        elif owned:
            status_label, status_colour = "Purchased", theme.POSITIVE
        elif ready:
            status_label, status_colour = "Available", theme.ACCENT
        else:
            status_label, status_colour = "Locked", theme.NEGATIVE
        if y <= rect.bottom - 20:
            draw_text(surface, fonts.small, "Status", (rect.left + 16, y), theme.TEXT_FAINT)
            draw_text(surface, fonts.small, status_label, (rect.right - 16, y), status_colour,
                      align="right")
        y += 26

        if unlock.implemented and not owned and y <= rect.bottom - 20:
            cost = tree.cost_of(unlock.key)
            draw_text(surface, fonts.small, "Cost", (rect.left + 16, y), theme.TEXT_FAINT)
            draw_text(surface, fonts.mono_small, cost.format(decimals=0),
                      (rect.right - 16, y), theme.TEXT, align="right")
            y += 26

        if y > rect.bottom - 20:
            surface.set_clip(previous_clip)
            return
        missing = {requirement.key for requirement in tree.missing_prerequisites(unlock.key)}
        draw_text(surface, fonts.small, "Requires", (rect.left + 16, y), theme.TEXT_FAINT)
        y += 22
        if unlock.requires:
            for requirement_key in unlock.requires:
                if y > rect.bottom - 22:
                    break
                requirement = tree.by_key.get(requirement_key)
                if requirement is None:
                    continue
                met = requirement_key not in missing
                draw_text(surface, fonts.small, requirement.name, (rect.left + 24, y),
                          theme.TEXT if met else theme.NEGATIVE)
                y += 20
        else:
            draw_text(surface, fonts.small, "Nothing — a starting point.",
                      (rect.left + 24, y), theme.TEXT_MUTED)
            y += 20

        enables = [other for other in tree.all if unlock.key in other.requires]
        if y <= rect.bottom - 44:
            y += 8
            draw_text(surface, fonts.small, "Leads to", (rect.left + 16, y), theme.TEXT_FAINT)
            y += 22
            if enables:
                for other in enables:
                    if y > rect.bottom - 8:
                        break
                    draw_text(surface, fonts.small, other.name, (rect.left + 24, y),
                              theme.TEXT_MUTED)
                    y += 20
            else:
                draw_text(surface, fonts.small, "Nothing further yet.",
                          (rect.left + 24, y), theme.TEXT_MUTED)
        surface.set_clip(previous_clip)
