"""The Unlock Tree page.

V6.10 asks for a professional roadmap: large spacing, clean alignment, straight
horizontal connections, no crossing lines, and a layout where the player always
understands how every branch connects back to Basic Investing. That shapes the
whole design here.

The tree is laid out on a grid rather than drawn ad hoc, following the roadmap
reference kept with the legacy prototype for its *layout* (colours and styling
remain Design Bible 2.0's): one horizontal spine straight through the middle
carrying Basic Investing, Create Company, the Company Levels and Investment
Funds (V6.5, V6.8), with the branches fanning symmetrically above and below it
(V6.6, V6.7) — see ``LAYOUT`` for which row each one takes and why.

Connections are drawn as elbows: down or up a shared vertical, then straight
across. Where several branches converge on one node — Investment Funds, which
every branch feeds — they share a single vertical rail just left of it instead
of each drawing its own midpoint elbow, so seven incoming lines read as one
junction rather than a fan. Because each branch owns its own row, no two
connections ever cross: a guarantee that is topological (fixed row and column
per branch), not pixel-based, which is what makes zooming safe (QoL pass,
2026-08-10) — scaling every dimension by the same factor cannot change which
row or column anything sits in, so it cannot introduce a crossing that did not
already exist.

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

from .. import theme
from ..widgets import Button, Card, draw_text, panel, truncate
from .base import Page
from .unlocks_layout import (
    BRANCH_LABELS,
    CLICK_TOLERANCE,
    COLUMN_STEP,
    DEFAULT_ZOOM_INDEX,
    GUTTER_WIDTH,
    INFO_PANEL_WIDTH,
    LAYOUT,
    NODE_HEIGHT,
    NODE_WIDTH,
    PAN_STEP,
    ROW_STEP,
    ZOOM_LEVELS,
)
from .unlocks_panel import InfoPanelMixin


class UnlockTreePage(InfoPanelMixin, Page):
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
        self.fit_button = Button("Fit", tooltip="Zoom to fit the whole tree on screen.")

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
        radius = max(2, self._scaled(4))
        for unlock in tree.all:
            target = self._node_rects[unlock.key]
            sources = [(key, self._node_rects[key]) for key in unlock.requires
                       if key in self._node_rects]
            # Several branches converging on one node share a single vertical
            # rail just left of it, rather than each running its own elbow
            # from its own midpoint — which is what the roadmap reference
            # does, and what stops Investment Funds' seven incoming lines
            # reading as a fan of near-parallel diagonals (2026-08-10).
            rail = None
            if len(sources) > 1:
                rail = target.left - self._scaled((COLUMN_STEP - NODE_WIDTH) // 2)
            for key, source in sources:
                done = tree.has(key) and tree.has(unlock.key)
                colour = theme.POSITIVE if done else theme.BORDER
                start = (source.right, source.centery)
                end = (target.left, target.centery)
                if start[1] == end[1]:
                    pygame.draw.line(surface, colour, start, end, 2)
                else:
                    # Drop or rise on a shared vertical, then run straight in —
                    # which is what keeps lines from crossing.
                    midway = rail if rail is not None else (start[0] + end[0]) // 2
                    pygame.draw.line(surface, colour, start, (midway, start[1]), 2)
                    pygame.draw.line(surface, colour, (midway, start[1]), (midway, end[1]), 2)
                    pygame.draw.line(surface, colour, (midway, end[1]), end, 2)
                # A dot at each end, as the reference has: it marks where a
                # branch leaves its parent and where it arrives, which is the
                # thing V6.10 wants legible at a glance.
                pygame.draw.circle(surface, colour, start, radius)
                pygame.draw.circle(surface, colour, end, radius)

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
