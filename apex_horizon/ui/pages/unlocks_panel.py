"""The Unlock Tree's details panel.

Split out of the page (2026-08-10) to keep each file within the size the
project works to. A mixin rather than a free function, so the panel goes on
reading ``self.selected_key`` exactly as it did when it was one of the page's
own methods — the split is about file size, not about changing how it works.
"""

from __future__ import annotations

import pygame

from .. import theme
from ..widgets import draw_text, panel, truncate
from .unlocks_layout import _wrap


class InfoPanelMixin:
    """The right-hand panel describing whatever node is selected (V6.14)."""

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
