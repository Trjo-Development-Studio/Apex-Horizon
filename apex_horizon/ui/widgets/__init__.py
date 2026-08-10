"""Interface components.

Every page is assembled from these, which is what makes the consistency V14.20
requires structural rather than a matter of discipline (V14.28): learning how a
list behaves on one page teaches the player how every other list behaves
(V27.11).

Behaviour follows the standards of Volume 27 — search filters as the player
types (V27.2), sorting is chosen explicitly and remembered per list (V27.3),
tables place one row per entity with numeric columns aligned for comparison
(V27.5), and a single click opens a row, never a double click (V14.8).

The widgets themselves live in sibling modules — this package re-exports every
one of them, so ``from ..widgets import Button`` reads exactly as it did when
they all shared a single file (split 2026-08-10, to keep each file within the
size the project works to).
"""

from .buttons import Button
from .cards import Card
from .inputs import Dropdown, SearchBox, Tabs
from .table import FOOTER_HEIGHT, Column, Table
from .text import chip, draw_text, draw_tooltip, format_fraction, panel, truncate

__all__ = [
    "FOOTER_HEIGHT",
    "Button",
    "Card",
    "Column",
    "Dropdown",
    "SearchBox",
    "Table",
    "Tabs",
    "chip",
    "draw_text",
    "draw_tooltip",
    "format_fraction",
    "panel",
    "truncate",
]
