"""Developer commands that act on the world: staff, research, events, economy."""

from __future__ import annotations

from decimal import Decimal

from ...engine.values import Money
from .base import no


class WorldCommands:
    """The remaining V15.18 commands, mixed into :class:`DeveloperCommands`."""

    # -- the rest of V15.18 ------------------------------------------------
    def _hire(self, count: str = "1") -> str:
        company = self.context.company
        if company is None:
            return no("No company currently exists.")
        roster = company.employees
        engine = self.context.engine
        # Deliberately calls refresh_applicants directly rather than
        # request_applicants: a debug command should stay instant, not wait
        # out the same real recruitment delay a player would.
        roster.refresh_applicants(engine.rng, self.context.names,
                                  self.context.allocator, engine.date.day)
        hired = 0
        for applicant in list(roster.applicants)[: int(count)]:
            if roster.hire(applicant, engine.date.day)[0]:
                hired += 1
        self.changed()
        return f"Hired {hired}; the company now employs {len(roster)}."

    def _research(self) -> str:
        """Finish what research has found, so it can be acted on at once."""
        company = self.context.company
        system = getattr(company, "investments", None) if company else None
        if system is None:
            return no("No company currently exists.")
        moved = 0
        for opportunity in list(system.opportunities):
            if getattr(opportunity, "ready_on_day", None) is not None:
                opportunity.ready_on_day = self.context.engine.date.day
                moved += 1
        self.changed()
        return f"Brought {moved} opportunit(y/ies) forward."

    def _event(self, direction: str = "up", percent: str = "5") -> str:
        """Move every listed price at once (V15.18: trigger market events)."""
        market = self.context.market
        if market is None:
            return no("No game is running.")
        if direction.lower() not in ("up", "down"):
            return no("Direction must be 'up' or 'down'.")
        size = Decimal(str(float(percent) / 100))
        if direction.lower() == "down":
            size = -size
        listings = market.active_listings()
        for listing in listings:
            listing.price = Money(listing.price.amount * (Decimal(1) + size))
        self.changed()
        return f"Moved {len(listings)} listings by {float(size):+.1%}."

    def _economy(self, health: str) -> str:
        economy = self.context.economy
        if economy is None:
            return no("No game is running.")
        economy.health = max(-1.0, min(1.0, float(health)))
        self.changed()
        return f"Economy health set to {economy.health:+.2f} ({economy.state})."

    def _status(self) -> str:
        context = self.context
        if context.engine is None:
            return no("No game is running.")
        company = context.company
        lines = [
            f"Day {context.engine.date.day} ({context.engine.date.label()})",
            f"Personal cash {context.player.cash.format(decimals=0)}, "
            f"net worth {context.player.net_worth().format(decimals=0)}",
            f"Economy {context.economy.state}, market index "
            f"{context.market.market_index():,.0f}",
        ]
        if company is not None:
            lines.append(
                f"{company.name}: level {company.level}, "
                f"cash {company.finances.cash.format(decimals=0)}, "
                f"{len(company.employees)} employees"
            )
        else:
            lines.append("No company founded yet.")
        if self.busy:
            lines.append(f"Simulating {self.pending_days:,} more day(s).")
        return "\n".join(lines)


# -- parsing helpers --------------------------------------------------------
