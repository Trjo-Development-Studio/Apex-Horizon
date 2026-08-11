"""The Unlock Tree page.

V6.10 asks for a professional roadmap: large spacing, clean alignment, straight
horizontal connections, no crossing lines, and a layout where the player always
understands how every branch connects back to Basic Investing. That shapes the
whole design here.

The tree is laid out on a grid: one horizontal spine through the middle
carrying Basic Investing, Create Company, the Company Levels and Investment
Funds (V6.5, V6.8), with the branches fanning symmetrically above and below it
(V6.6, V6.7) — see :mod:`.unlocks_layout` for which row each one takes. The
layout follows the prerequisite graph, not the legacy roadmap picture: where
the two disagree the graph wins, so a drawn connection always means a real
dependency (project manager, 2026-08-11).

Connections are drawn as elbows: down or up a shared vertical, then straight
across. Where several branches converge on one node — Investment Funds, which
every branch feeds — they share a single vertical rail just left of it instead
of each drawing its own midpoint elbow, so seven incoming lines read as one
junction rather than a fan. Because each branch owns its own row, no two
connections ever cross: a guarantee that is topological (fixed row and column
per branch) rather than pixel-based.

The viewport is compact and fixed (project manager, 2026-08-11). Every branch
is always visible: the tree is drawn at whatever scale makes all its rows fit
the height available, so there is no vertical scrolling to do and none is
offered. The tree is far wider than it is tall, so the one direction that does
need navigating — sideways, towards the later unlocks — gets a scrollbar of
its own beneath the map. The scrollable width comes from where the nodes
actually end, so adding an unlock further right extends the scroll by itself.
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
    GUTTER_WIDTH,
    INFO_PANEL_WIDTH,
    MAP_PADDING_X,
    MAP_PADDING_Y,
    MAX_SCALE,
    MIN_SCALE,
    NODE_HEIGHT,
    NODE_WIDTH,
    PAN_STEP,
    ROW_STEP,
    SCROLLBAR_GAP,
    SCROLLBAR_HEIGHT,
    grid_bounds,
    position_of,
)
from .unlocks_panel import InfoPanelMixin

#: Height of the strip above the map holding the hint text.
HEADER_HEIGHT = 26


class UnlockTreePage(InfoPanelMixin, Page):
    """The player's map of their own future (V6.14)."""

    key = "unlocks"
    TITLE = "Unlock Tree"
    SUBTITLE = "Everything your company can become"

    def __init__(self, context):
        super().__init__(context)
        self._buttons: dict[str, Button] = {}
        self.unlock_request: str | None = None
        #: How far the map is scrolled sideways, in pixels. There is no
        #: vertical equivalent by design: every branch is always on screen.
        self.scroll_x = 0
        self._dragging = False
        self._drag_origin = (0, 0)
        self._drag_distance = 0.0
        self._dragging_thumb = False
        self._node_rects: dict[str, pygame.Rect] = {}
        #: Session-only UI state — deliberately not written to the save.
        self.selected_key: str | None = None
        #: Worked out afresh on every draw from the space available.
        self._scale = MAX_SCALE
        self._scroll_limit = 0
        self._map_view = pygame.Rect(0, 0, 0, 0)
        self._track_rect = pygame.Rect(0, 0, 0, 0)
        self._thumb_rect = pygame.Rect(0, 0, 0, 0)

    def take_unlock_request(self) -> str | None:
        request, self.unlock_request = self.unlock_request, None
        return request

    def _button(self, key: str) -> Button:
        if key not in self._buttons:
            self._buttons[key] = Button("Unlock", primary=True)
        return self._buttons[key]

    # -- geometry ------------------------------------------------------------
    def _scaled(self, value: float) -> int:
        return round(value * self._scale)

    def _unlocks(self) -> list:
        tree = self.context.unlocks
        return list(tree.all) if tree is not None else []

    def scale_for(self, height: int) -> float:
        """The scale at which every row fits into ``height``.

        Never above 1.0 — a tree with room to spare should sit comfortably in
        its viewport rather than inflate to fill it — and never below
        MIN_SCALE, past which the text stops being readable (V6.10).
        """
        first, last, _ = grid_bounds(self._unlocks())
        rows = (last - first) + 1
        needed = rows * ROW_STEP + MAP_PADDING_Y * 2
        if needed <= 0:
            return MAX_SCALE
        return max(MIN_SCALE, min(MAX_SCALE, height / needed))

    def viewport_height(self, available: int) -> int:
        """How tall the map itself is drawn: the whole tree, and no more.

        Compact by construction — it is the tree's own height at the scale
        that fits, so it never grows with how *wide* the tree becomes, and
        never claims space it has nothing to put in.
        """
        scale = self.scale_for(available)
        first, last, _ = grid_bounds(self._unlocks())
        rows = (last - first) + 1
        return min(available, round(rows * ROW_STEP * scale) + MAP_PADDING_Y * 2)

    def _content_width(self) -> int:
        """How wide the tree is in pixels, out to the far edge of the last node."""
        _, _, last_column = grid_bounds(self._unlocks())
        return (last_column * self._scaled(COLUMN_STEP) + self._scaled(NODE_WIDTH)
                + MAP_PADDING_X * 2)

    def _clamp_scroll(self) -> None:
        self.scroll_x = max(0, min(self.scroll_x, self._scroll_limit))

    def _position(self, tree, unlock) -> tuple[int, int]:
        return position_of(unlock)

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
            # Sideways only: there is nothing above or below to scroll to.
            if event.key == pygame.K_LEFT:
                self.scroll_x -= PAN_STEP
                self._clamp_scroll()
                return True
            if event.key == pygame.K_RIGHT:
                self.scroll_x += PAN_STEP
                self._clamp_scroll()
                return True
        elif event.type == pygame.MOUSEWHEEL:
            # The wheel scrolls the one axis this page has. Either axis of a
            # trackpad gesture is accepted, so a sideways swipe works too.
            step = event.x if event.x else -event.y
            self.scroll_x += step * PAN_STEP
            self._clamp_scroll()
            return True
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._thumb_rect.height and self._track_rect.collidepoint(event.pos):
                self._dragging_thumb = True
                if not self._thumb_rect.collidepoint(event.pos):
                    self._scroll_to_thumb_centre(event.pos[0])
                self._drag_origin = event.pos
                return True
            if self._map_view.collidepoint(event.pos):
                self._dragging = True
                self._drag_origin = event.pos
                self._drag_distance = 0.0
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            was_thumb, self._dragging_thumb = self._dragging_thumb, False
            self._dragging = False
            if was_thumb:
                return True
            # A click barely moved; a drag almost never holds this still.
            # Telling them apart is what lets a node be both draggable (the
            # map) and selectable (the node) with one mouse-down/up pair.
            if self._drag_distance <= CLICK_TOLERANCE:
                clicked = next(
                    (key for key, rect in self._node_rects.items()
                     if rect.collidepoint(event.pos)),
                    None,
                )
                if clicked is not None:
                    self.selected_key = clicked
                    return True
        elif event.type == pygame.MOUSEMOTION:
            if self._dragging_thumb:
                self._scroll_to_thumb_centre(event.pos[0])
                return True
            if self._dragging:
                dx = event.pos[0] - self._drag_origin[0]
                dy = event.pos[1] - self._drag_origin[1]
                self.scroll_x -= dx
                self._clamp_scroll()
                self._drag_origin = event.pos
                self._drag_distance += abs(dx) + abs(dy)
                return True
        return False

    def _scroll_to_thumb_centre(self, x: int) -> None:
        """Put the middle of the thumb under ``x`` and scroll to match."""
        travel = self._track_rect.width - self._thumb_rect.width
        if travel <= 0:
            self.scroll_x = 0
            return
        offset = x - self._track_rect.left - self._thumb_rect.width / 2
        self.scroll_x = round(self._scroll_limit * max(0.0, min(1.0, offset / travel)))
        self._clamp_scroll()

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
                  "Drag the map, scroll, or use the left and right arrow keys.",
                  (rect.left, rect.top), theme.TEXT_MUTED)

        # The map takes only the height the tree needs; the scrollbar sits
        # directly beneath it, and whatever is left over stays empty rather
        # than being absorbed into an oversized viewport.
        room = max(0, rect.height - HEADER_HEIGHT - SCROLLBAR_HEIGHT - SCROLLBAR_GAP)
        if room <= 0:
            return
        self._scale = self.scale_for(room)
        view = pygame.Rect(rect.left, rect.top + HEADER_HEIGHT,
                           rect.width, self.viewport_height(room))
        panel(surface, view)
        if view.width <= 0 or view.height <= 0:
            return

        info_width = min(INFO_PANEL_WIDTH, max(0, view.width // 3))
        info_panel_rect = pygame.Rect(view.right - info_width, view.top, info_width, view.height)
        self._map_view = pygame.Rect(view.left, view.top, view.width - info_width, view.height)

        visible = max(0, self._map_view.width - GUTTER_WIDTH)
        self._scroll_limit = max(0, self._content_width() - visible)
        self._clamp_scroll()

        # Everything inside the map is clipped to it, so a node scrolled past
        # the edge does not spill over the rest of the interface.
        previous_clip = surface.get_clip()
        surface.set_clip(self._map_view)

        self._node_rects = {
            unlock.key: self._rect_for(tree, unlock, self._map_view) for unlock in tree.all
        }
        self._draw_connections(surface, tree)
        for unlock in tree.all:
            node = self._node_rects[unlock.key]
            if node.colliderect(self._map_view):
                self._draw_node(surface, node, fonts, mouse, unlock, tree, player)
            else:
                self._button(unlock.key).enabled = False

        # Branch names sit in a fixed gutter drawn over the map. Scrolling them
        # with the nodes would let them collide with whatever passed underneath;
        # keeping them still means the player can always tell which row is which.
        self._draw_branch_labels(surface, fonts, tree)
        surface.set_clip(previous_clip)

        self._draw_scrollbar(surface, view)
        self._draw_info_panel(surface, info_panel_rect, fonts, tree)

    def _draw_scrollbar(self, surface, view: pygame.Rect) -> None:
        """A horizontal scrollbar under the map, and only a horizontal one."""
        self._track_rect = pygame.Rect(
            self._map_view.left, view.bottom + SCROLLBAR_GAP,
            self._map_view.width, SCROLLBAR_HEIGHT)
        if self._scroll_limit <= 0:
            # The whole tree already fits: no thumb, and nothing to drag.
            self._thumb_rect = pygame.Rect(0, 0, 0, 0)
            return
        panel(surface, self._track_rect, fill=theme.SURFACE, border=theme.BORDER)
        total = self._content_width()
        fraction = max(0.12, self._track_rect.width / total) if total else 1.0
        width = max(40, round(self._track_rect.width * fraction))
        travel = self._track_rect.width - width
        position = self.scroll_x / self._scroll_limit if self._scroll_limit else 0.0
        self._thumb_rect = pygame.Rect(
            self._track_rect.left + round(travel * position), self._track_rect.top,
            width, SCROLLBAR_HEIGHT)
        panel(surface, self._thumb_rect, fill=theme.BORDER_STRONG, border=None)

    def _rect_for(self, tree, unlock, map_view: pygame.Rect) -> pygame.Rect:
        row, column = self._position(tree, unlock)
        first_row, _, _ = grid_bounds(self._unlocks())
        x = (map_view.left + GUTTER_WIDTH + MAP_PADDING_X
             + column * self._scaled(COLUMN_STEP) - self.scroll_x)
        y = (map_view.top + MAP_PADDING_Y
             + (row - first_row) * self._scaled(ROW_STEP))
        return pygame.Rect(x, y, self._scaled(NODE_WIDTH), self._scaled(NODE_HEIGHT))

    def _draw_connections(self, surface, tree) -> None:
        """Elbow connections: along a shared vertical, then straight across."""
        radius = max(2, self._scaled(3))
        for unlock in tree.all:
            target = self._node_rects[unlock.key]
            sources = [(key, self._node_rects[key]) for key in unlock.requires
                       if key in self._node_rects]
            # Several branches converging on one node share a single vertical
            # rail just left of it, rather than each running its own elbow
            # from its own midpoint — which stops Investment Funds' incoming
            # lines reading as a fan of near-parallel diagonals.
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
                # A dot at each end: it marks where a branch leaves its parent
                # and where it arrives, which V6.10 wants legible at a glance.
                pygame.draw.circle(surface, colour, start, radius)
                pygame.draw.circle(surface, colour, end, radius)

    def _draw_branch_labels(self, surface, fonts, tree) -> None:
        map_view = self._map_view
        gutter = pygame.Rect(map_view.left + 1, map_view.top + 1,
                             GUTTER_WIDTH, map_view.height - 2)
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
            draw_text(surface, fonts.tiny,
                      truncate(fonts.tiny, label.upper(), GUTTER_WIDTH - 14),
                      (gutter.left + 8, first.centery - 6), theme.TEXT_FAINT)

    def _draw_node(self, surface, rect, fonts, mouse, unlock, tree, player) -> None:
        label_font = fonts.small if self._scale >= 0.95 else fonts.tiny
        owned = tree.has(unlock.key)
        ready = not owned and tree.prerequisites_met(unlock.key) and unlock.implemented
        panel(surface, rect)
        if self.selected_key == unlock.key:
            pygame.draw.rect(surface, theme.ACCENT, rect, 2, border_radius=8)
        elif owned:
            pygame.draw.rect(surface, theme.POSITIVE, rect, 2, border_radius=8)
        elif ready:
            pygame.draw.rect(surface, theme.ACCENT_MUTED, rect, 1, border_radius=8)

        # Two rows: the name, then the state and its action side by side. The
        # node is only tall enough for two, so nothing is drawn below them.
        pad = self._scaled(10)
        name_y = rect.top + self._scaled(7)
        status_y = rect.top + self._scaled(30)
        draw_text(surface, label_font,
                  truncate(label_font, unlock.name, rect.width - pad * 2),
                  (rect.left + pad, name_y),
                  theme.TEXT if owned or ready else theme.TEXT_MUTED)

        button = self._button(unlock.key)
        if owned:
            button.enabled = False
            draw_text(surface, fonts.tiny, "Unlocked", (rect.left + pad, status_y),
                      theme.POSITIVE)
            return
        if not unlock.implemented:
            button.enabled = False
            draw_text(surface, fonts.tiny, "Coming later", (rect.left + pad, status_y),
                      theme.TEXT_FAINT)
            return

        cost = tree.cost_of(unlock.key)
        if not ready:
            button.enabled = False
            draw_text(surface, fonts.tiny, "Locked", (rect.left + pad, status_y),
                      theme.TEXT_FAINT)
            draw_text(surface, fonts.tiny, cost.format(decimals=0),
                      (rect.right - pad, status_y), theme.TEXT_FAINT, align="right")
            return

        affordable = player is not None and player.cash >= cost
        button.enabled = affordable
        draw_text(surface, fonts.tiny, cost.format(decimals=0),
                  (rect.left + pad, status_y),
                  theme.TEXT if affordable else theme.NEGATIVE)
        button.draw(surface, pygame.Rect(
            rect.right - self._scaled(60), rect.top + self._scaled(27),
            self._scaled(52), self._scaled(20)), fonts, mouse)
