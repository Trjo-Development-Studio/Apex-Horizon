"""A company's presence on the market.

Design Bible V4.3 gives every public company a share price, market value,
reputation, financial performance, and price history. Those live here rather
than on the :class:`~apex_horizon.engine.world.entities.Company` record itself:
the company entity carries identity — who it is — while the market owns market
data, so each system remains responsible for its own state (V15.7).
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from ..values import Money, Percentage


@dataclass
class PriceChange:
    """A breakdown of why a share price moved on one day.

    V4.4 requires that prices never feel completely random and that every
    movement has a believable explanation; V4.21 adds that movement must always
    be traceable to an underlying cause so losses feel explainable rather than
    arbitrary. Keeping the contributions rather than only the result is what
    makes that explanation available to news, analytics, and the player.
    """

    performance: Percentage = field(default_factory=Percentage.zero)
    industry: Percentage = field(default_factory=Percentage.zero)
    economy: Percentage = field(default_factory=Percentage.zero)
    sentiment: Percentage = field(default_factory=Percentage.zero)
    supply_demand: Percentage = field(default_factory=Percentage.zero)
    variation: Percentage = field(default_factory=Percentage.zero)
    total: Percentage = field(default_factory=Percentage.zero)

    def dominant_cause(self) -> str:
        """The single largest contributor, for explaining the day's movement."""
        contributions = {
            "company performance": self.performance,
            "industry conditions": self.industry,
            "economic conditions": self.economy,
            "market sentiment": self.sentiment,
            "supply and demand": self.supply_demand,
            "ordinary variation": self.variation,
        }
        return max(contributions, key=lambda name: abs(contributions[name].fraction))


@dataclass
class MarketListing:
    """The market's record of one public company (V4.3)."""

    company_id: str
    price: Money
    shares_outstanding: int
    volatility: Percentage

    # Underlying business performance, in the range -1.0 to 1.0. Strong
    # companies generally grow over time and weak ones struggle (V4.11).
    performance: float = 0.0
    financial_health: float = 0.5
    reputation: float = 0.5

    # Daily closing prices, oldest first. Bounded so a save cannot grow without
    # limit across hundreds of in-game years (V16.20).
    history: deque[Money] = field(default_factory=lambda: deque(maxlen=730))
    last_change: PriceChange = field(default_factory=PriceChange)

    # Net share demand accumulated since the last price update. Positive values
    # are net buying pressure, negative net selling (V4.8).
    pending_demand: int = 0

    delisted: bool = False
    delisted_on_day: int | None = None
    days_below_floor: int = 0

    @property
    def market_cap(self) -> Money:
        """Total value of the company's shares in issue."""
        return self.price * self.shares_outstanding

    @property
    def previous_close(self) -> Money | None:
        """Yesterday's closing price, if the company has traded before."""
        return self.history[-1] if self.history else None

    def daily_change(self) -> Percentage:
        """Change against the previous close."""
        previous = self.previous_close
        if previous is None or previous.is_zero:
            return Percentage.zero()
        return Percentage((self.price.amount - previous.amount) / previous.amount)

    def record_close(self) -> None:
        """Append today's price to the history."""
        self.history.append(self.price)

    def add_demand(self, shares: int) -> None:
        """Register buying (positive) or selling (negative) pressure (V4.8)."""
        self.pending_demand += shares

    def price_on(self, days_ago: int) -> Money | None:
        """A past closing price, or ``None`` if history does not reach back."""
        if days_ago <= 0 or days_ago > len(self.history):
            return None
        return self.history[-days_ago]

    def change_over(self, days: int) -> Percentage:
        """Price change over the last ``days`` of trading."""
        past = self.price_on(days)
        if past is None or past.is_zero:
            return Percentage.zero()
        return Percentage((self.price.amount - past.amount) / past.amount)
