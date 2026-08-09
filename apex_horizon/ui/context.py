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
    ai: Any = None
    statistics: Any = None
    saves: Any = None

    @property
    def company(self):
        """The company object, if the player has ever founded one.

        This is deliberately not "the player's operating company" — a bankrupt
        company is still a company, and V1.3 keeps it around exactly so the
        player and the save can still see what happened to it. Anything that
        means "is there a business currently running" must read
        :attr:`has_company` instead of checking this for ``None`` alone; reading
        this directly is for the small number of things that genuinely want the
        record regardless of its state (persistence, lifetime statistics, the
        bankruptcy notice itself).
        """
        return getattr(self.player, "company", None)

    @property
    def portfolio(self):
        """The player's own holdings, which exist from the first day (V1.19)."""
        return getattr(self.player, "portfolio", None)

    @property
    def unlocks(self):
        """What the player has earned so far (V6)."""
        return getattr(self.player, "unlocks", None)

    @property
    def has_company(self) -> bool:
        """Whether the player currently has a company that is open for business.

        The one check every page should use to decide whether to show company
        management: cards, buttons, sub-pages, rankings, all of it. A company
        that has gone bankrupt is not None, so a page that only asks "is there a
        company" instead of asking this would keep behaving as though a dead
        company were still trading.
        """
        company = self.company
        return company is not None and not company.bankrupt

    @property
    def bankrupt_company(self):
        """The player's most recent company, if it exists and has failed.

        For the one thing a bankrupt company's record is still for here: saying
        so. ``None`` both before a first company exists and once a new one has
        been founded, since at that point ``company`` points at the new one
        instead (V1.3 — a fresh company, not a revived one).
        """
        company = self.company
        return company if company is not None and company.bankrupt else None
