"""Historical tracking.

V9.10 requires the game to show how things have developed over time, not only
how they stand today. Nothing else in the simulation keeps a record of the past:
the market keeps prices, but the player's wealth, the company's cash and the
mood of the market all exist only as their current value. This module is the
one place that remembers.

Snapshots are taken on a month boundary rather than daily (V13.10). A century of
play is then about twelve hundred rows — small enough to save and to chart,
while still fine-grained enough to show a recession as something with a shape.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from ..config import Config, get_config
from ..logging_setup import get_logger
from ..simulation import PeriodBoundary, SimulationContext, SimulationEngine
from ..values import Money

logger = get_logger(__name__)


@dataclass(frozen=True)
class Snapshot:
    """What the world looked like at one moment (V9.10)."""

    day: int
    net_worth: Money
    cash: Money
    company_cash: Money
    market_index: float

    def state(self) -> dict:
        return {
            "day": self.day,
            "net_worth": str(self.net_worth.amount),
            "cash": str(self.cash.amount),
            "company_cash": str(self.company_cash.amount),
            "market_index": self.market_index,
        }

    @classmethod
    def from_state(cls, data: dict) -> Snapshot:
        return cls(
            day=int(data.get("day", 0)),
            net_worth=Money(Decimal(str(data.get("net_worth", "0")))),
            cash=Money(Decimal(str(data.get("cash", "0")))),
            company_cash=Money(Decimal(str(data.get("company_cash", "0")))),
            market_index=float(data.get("market_index", 0.0)),
        )


class HistoryRecorder:
    """Keeps a monthly record of the figures the player is judged by."""

    def __init__(self, context, *, config: Config | None = None):
        self.config = config or get_config()
        self.context = context
        self.snapshots: list[Snapshot] = []
        self._limit = self.config.get_int("analytics.history_limit")
        self._last_recorded_day: int | None = None

    def register(self, engine: SimulationEngine) -> None:
        engine.register_boundary(PeriodBoundary.MONTH, self.record)

    def record(self, context: SimulationContext) -> None:
        """Take one snapshot, guarding against a repeated month (V15.26)."""
        if self._last_recorded_day == context.day_number:
            return
        self._last_recorded_day = context.day_number

        player = getattr(self.context, "player", None)
        company = getattr(self.context, "company", None)
        market = getattr(self.context, "market", None)
        self.snapshots.append(Snapshot(
            day=context.day_number,
            net_worth=player.net_worth() if player else Money(0),
            cash=player.cash if player else Money(0),
            company_cash=company.finances.cash if company else Money(0),
            market_index=market.market_index() if market else 0.0,
        ))
        del self.snapshots[: -self._limit]

    # -- reading back ------------------------------------------------------
    def series(self, attribute: str, count: int = 60) -> list[tuple[int, float]]:
        """A (day, value) series for charting, oldest first."""
        recent = self.snapshots[-count:]
        values = []
        for snapshot in recent:
            value = getattr(snapshot, attribute, 0)
            values.append((snapshot.day, float(getattr(value, "amount", value))))
        return values

    def change_over(self, attribute: str, months: int) -> float | None:
        """How much a figure has moved over the last ``months``, as a fraction.

        Returns ``None`` when there is not enough history to answer honestly —
        V9.21 would rather show nothing than a number the player cannot trust.
        """
        if len(self.snapshots) <= months:
            return None
        then = getattr(self.snapshots[-months - 1], attribute)
        now = getattr(self.snapshots[-1], attribute)
        start = float(getattr(then, "amount", then))
        end = float(getattr(now, "amount", now))
        if start == 0:
            return None
        return (end - start) / abs(start)

    # -- persistence -------------------------------------------------------
    def state(self) -> dict:
        return {
            "snapshots": [s.state() for s in self.snapshots],
            "last_recorded_day": self._last_recorded_day,
        }

    def restore(self, data: dict) -> None:
        self.snapshots = [Snapshot.from_state(s) for s in data.get("snapshots", [])]
        self._last_recorded_day = data.get("last_recorded_day")
