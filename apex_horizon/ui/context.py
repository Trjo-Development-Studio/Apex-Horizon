"""What the interface is allowed to see.

Pages read the simulation through this one object. V15.5 keeps the interface a
presentation layer: it may read game state and ask systems to do things, but no
gameplay logic lives here, and no system knows the interface exists.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class GameContext:
    """References to the running simulation, for display."""

    engine: Any = None
    world: Any = None
    market: Any = None
    economy: Any = None
    banking: Any = None
    player: Any = None
    # Generation state travels with the world so names and identifiers stay
    # unique when the market keeps creating companies after a reload (V34.3).
    allocator: Any = None
    names: Any = None
    news: Any = None
    analytics: Any = None
    saves: Any = None

    @property
    def company(self):
        """The player's company, or ``None`` before one is founded."""
        return getattr(self.player, "company", None)

    @property
    def has_company(self) -> bool:
        company = self.company
        return company is not None and not company.bankrupt
