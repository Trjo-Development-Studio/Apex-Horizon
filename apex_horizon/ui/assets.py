"""Loaded image assets — the game's real logo, kept apart from the drawn icons.

V1.15's icon language (:mod:`.icons`) is deliberately drawn rather than loaded,
because a handful of simple shapes can be kept in one consistent weight and
palette forever. The project's actual mark is not that kind of icon — it is the
game's real visual identity, made once outside the engine — so it is loaded
from `assets/` instead of redrawn in code.

Only one file lives there: a square crop of the mark alone, with the "Apex
Horizon" wordmark trimmed away. The wordmark reads at the size the Start Menu
gives it, but not at the handful of pixels a window icon or a collapsed sidebar
gets, so what is used at that size is the mark by itself rather than the full
lockup scaled down until its type disappears.

Every size ever asked for is cached, so drawing it costs one decode and one
scale for the whole run, not one per frame.
"""

from __future__ import annotations

import pygame

from ..engine.paths import asset_path

_cache: dict[int, pygame.Surface] = {}


def mark(size: int) -> pygame.Surface | None:
    """The Apex Horizon mark, smooth-scaled to a square of ``size`` pixels.

    Returns ``None`` if the asset file is missing rather than raising: this is
    artwork, not gameplay data, and a checkout without the binary asset should
    still run rather than crash on start (V15.19 tests what is actually there).

    Safe to call before a display mode is set — the window icon is loaded that
    way — and after, where converting to the display format speeds up the
    sidebar's every-frame blit.
    """
    if size in _cache:
        return _cache[size]
    path = asset_path("images", "apex_horizon_mark.png")
    if not path.exists():
        return None
    image = pygame.image.load(path)
    if pygame.display.get_surface() is not None:
        image = image.convert_alpha()
    scaled = pygame.transform.smoothscale(image, (size, size))
    _cache[size] = scaled
    return scaled
