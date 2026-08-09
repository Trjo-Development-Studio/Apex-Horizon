"""Visual language.

Design Bible V1.15 sets the identity: clean, modern, professional, minimalistic,
drawing on business software and professional financial platforms rather than
game interfaces. V14.3 repeats it, and V27.10 requires text to keep sufficient
contrast against its background.

Everything visual comes from here. A screen that invents its own colour or
spacing breaks the consistency V14.20 and V27.11 depend on — that a player who
has learned one page already knows how the next one behaves.
"""

from __future__ import annotations

from dataclasses import dataclass

import pygame

# -- colour -----------------------------------------------------------------
# A restrained, near-monochrome palette. Colour carries meaning rather than
# decoration: one accent for the active element, and green/red reserved strictly
# for financial gain and loss.
BACKGROUND = (15, 17, 21)
SURFACE = (23, 26, 32)
SURFACE_RAISED = (30, 34, 42)
SURFACE_HOVER = (37, 42, 52)
BORDER = (42, 47, 58)
BORDER_STRONG = (58, 65, 79)

TEXT = (230, 233, 239)
TEXT_MUTED = (138, 146, 158)
TEXT_FAINT = (98, 105, 117)

ACCENT = (76, 141, 255)
ACCENT_MUTED = (44, 74, 130)
POSITIVE = (63, 185, 80)
NEGATIVE = (248, 81, 73)
WARNING = (219, 154, 62)

OVERLAY = (8, 9, 12)

# -- metrics ----------------------------------------------------------------
SIDEBAR_WIDTH = 68
#: Width once the player expands it to show the names beside the icons.
SIDEBAR_EXPANDED = 208
TOPBAR_HEIGHT = 56
PAGE_PADDING = 28
CARD_HEIGHT = 84
ROW_HEIGHT = 38
HEADER_ROW_HEIGHT = 34
CORNER = 6
GAP = 16

# Notifications live in the lower-right corner (V14.16, V27.7), clear of the
# sidebar, which has to stay usable while a message is showing.
NOTIFICATION_WIDTH = 340
NOTIFICATION_HEIGHT = 56
NOTIFICATION_GAP = 8

# Animations exist only to clarify a state change and must never delay the
# player's next action (V27.8).
SLIDE_MS = 180


@dataclass
class Fonts:
    """The type scale. Loaded once and shared."""

    title: pygame.font.Font
    heading: pygame.font.Font
    subheading: pygame.font.Font
    body: pygame.font.Font
    small: pygame.font.Font
    tiny: pygame.font.Font
    # Numeric columns are compared down a column at a glance (V27.5), which
    # only works if digits share a width.
    mono: pygame.font.Font
    mono_small: pygame.font.Font

    @classmethod
    def load(cls) -> Fonts:
        sans = _first_available(
            ["Inter", "Segoe UI", "Helvetica Neue", "DejaVu Sans", "Liberation Sans", "Arial"]
        )
        mono = _first_available(
            ["JetBrains Mono", "Consolas", "DejaVu Sans Mono", "Liberation Mono", "Courier New"]
        )
        return cls(
            title=pygame.font.SysFont(sans, 30, bold=True),
            heading=pygame.font.SysFont(sans, 22, bold=True),
            subheading=pygame.font.SysFont(sans, 16, bold=True),
            body=pygame.font.SysFont(sans, 15),
            small=pygame.font.SysFont(sans, 13),
            tiny=pygame.font.SysFont(sans, 11, bold=True),
            mono=pygame.font.SysFont(mono, 15),
            mono_small=pygame.font.SysFont(mono, 13),
        )


def _first_available(candidates: list[str]) -> str:
    """Pick the first installed font, falling back to pygame's default."""
    available = set(pygame.font.get_fonts())
    for name in candidates:
        key = name.lower().replace(" ", "")
        if key in available:
            return key
    return pygame.font.get_default_font()


# -- helpers ----------------------------------------------------------------
def value_colour(is_positive: bool | None) -> tuple[int, int, int]:
    """Green for gain, red for loss, plain text for neutral."""
    if is_positive is None:
        return TEXT
    return POSITIVE if is_positive else NEGATIVE


def mix(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    """Blend two colours; ``t`` of 0 gives ``a`` and 1 gives ``b``."""
    t = max(0.0, min(1.0, t))
    return (
        round(a[0] + (b[0] - a[0]) * t),
        round(a[1] + (b[1] - a[1]) * t),
        round(a[2] + (b[2] - a[2]) * t),
    )
