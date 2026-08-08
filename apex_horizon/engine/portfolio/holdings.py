"""The player's own portfolio.

The player begins as an individual investor with $10,000 and no company (V1.19,
V1.21). V1.20 confirms this is a playstyle in its own right: a player may choose
never to found a company and remain an individual investor indefinitely. So
personal investing cannot depend on company ownership — it is what the opening
of the game *is*, and what earns the $25,000 a company costs to found (V3.3).

Two rules shape everything here:

* **Personal money is not company money** (V1.4, V3.4). This portfolio spends
  and receives the player's cash only. It has no access to company funds, and
  the company's own investment operation (Volume 8) is a separate system with
  its own holdings.
* **The player trades personally.** Where the company invests through its
  employees — research finds, management approves, an investor executes (V8.3)
  — the player buys and sells directly. That difference is the point: hiring
  people is what buys the player leverage over their own time.

Personal orders reach the market the same way the company's do, through
recorded demand (V4.8), so buying genuinely pushes a price rather than drawing
from an infinite pool.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from ..config import Config, get_config
from ..logging_setup import get_logger
from ..values import Money, Percentage

logger = get_logger(__name__)


@dataclass
class Holding:
    """Shares of one company held personally, and what they cost."""

    company_id: str
    shares: int
    #: Total paid for the shares still held, so gains are measured honestly
    #: against what was actually spent rather than against the last price.
    cost_basis: Money

    @property
    def average_price(self) -> Money:
        if self.shares <= 0:
            return Money.zero()
        return Money(self.cost_basis.amount / Decimal(self.shares))

    def value_at(self, price: Money) -> Money:
        return Money(price.amount * Decimal(self.shares))

    def unrealised(self, price: Money) -> Money:
        return self.value_at(price) - self.cost_basis

    def unrealised_return(self, price: Money) -> Percentage:
        if not self.cost_basis.is_positive:
            return Percentage.zero()
        return Percentage(self.unrealised(price).amount / self.cost_basis.amount)

    def state(self) -> dict:
        return {
            "company_id": self.company_id,
            "shares": self.shares,
            "cost_basis": str(self.cost_basis.amount),
        }

    @classmethod
    def from_state(cls, data: dict) -> Holding:
        return cls(
            company_id=data["company_id"],
            shares=int(data.get("shares", 0)),
            cost_basis=Money(data.get("cost_basis", "0")),
        )


@dataclass(frozen=True)
class Trade:
    """One completed personal trade, kept so the player can review decisions."""

    day: int
    company_id: str
    shares: int
    price: Money
    #: Profit or loss booked on a sale; zero for a purchase.
    realised: Money
    is_purchase: bool

    def state(self) -> dict:
        return {
            "day": self.day,
            "company_id": self.company_id,
            "shares": self.shares,
            "price": str(self.price.amount),
            "realised": str(self.realised.amount),
            "is_purchase": self.is_purchase,
        }

    @classmethod
    def from_state(cls, data: dict) -> Trade:
        return cls(
            day=int(data.get("day", 0)),
            company_id=data["company_id"],
            shares=int(data.get("shares", 0)),
            price=Money(data.get("price", "0")),
            realised=Money(data.get("realised", "0")),
            is_purchase=bool(data.get("is_purchase", True)),
        )


class PersonalPortfolio:
    """What the player owns personally, and how they trade it."""

    #: Trades kept for review; older ones fall off.
    MAX_HISTORY = 200

    def __init__(self, player, market, *, config: Config | None = None):
        self.config = config or get_config()
        self.player = player
        self.market = market
        self.holdings: dict[str, Holding] = {}
        self.trades: list[Trade] = []
        self.realised: Money = Money.zero()
        #: Called with each completed trade, for anything keeping a tally.
        self.on_trade: list = []

    # -- access ------------------------------------------------------------
    def holding_for(self, company_id: str) -> Holding | None:
        return self.holdings.get(company_id)

    def shares_of(self, company_id: str) -> int:
        holding = self.holdings.get(company_id)
        return holding.shares if holding else 0

    def value(self) -> Money:
        """What the holdings are worth at today's prices."""
        total = Money.zero()
        for holding in self.holdings.values():
            listing = self.market.listing_for(holding.company_id)
            if listing is not None:
                total = total + holding.value_at(listing.price)
        return total

    def cost_basis(self) -> Money:
        total = Money.zero()
        for holding in self.holdings.values():
            total = total + holding.cost_basis
        return total

    def unrealised(self) -> Money:
        return self.value() - self.cost_basis()

    def recent_trades(self, count: int = 20) -> list[Trade]:
        return list(reversed(self.trades))[:count]

    # -- trading -----------------------------------------------------------
    def max_affordable(self, company_id: str) -> int:
        """How many shares the player's cash could buy right now."""
        listing = self.market.listing_for(company_id)
        if listing is None or not listing.price.is_positive:
            return 0
        return int(self.player.cash.amount / listing.price.amount)

    def can_buy(self, company_id: str, shares: int) -> tuple[bool, str]:
        if shares <= 0:
            return False, "Enter how many shares to buy."
        listing = self.market.listing_for(company_id)
        if listing is None or listing.delisted:
            return False, "That company is not trading."
        cost = Money(listing.price.amount * Decimal(shares))
        if cost > self.player.cash:
            return False, (
                f"That costs {cost.format(decimals=0)}; "
                f"you have {self.player.cash.format(decimals=0)}."
            )
        return True, ""

    def buy(self, company_id: str, shares: int, day: int) -> tuple[bool, str]:
        """Buy shares with personal cash (V1.4: personal money only)."""
        allowed, reason = self.can_buy(company_id, shares)
        if not allowed:
            return False, reason

        listing = self.market.listing_for(company_id)
        cost = Money(listing.price.amount * Decimal(shares))
        self.player.cash = self.player.cash - cost

        holding = self.holdings.get(company_id)
        if holding is None:
            self.holdings[company_id] = Holding(company_id, shares, cost)
        else:
            holding.shares += shares
            holding.cost_basis = holding.cost_basis + cost

        # The order reaches the market like any other (V4.8).
        self.market.record_demand(company_id, shares)
        self._record(Trade(day, company_id, shares, listing.price, Money.zero(), True))
        logger.info("Player bought %d shares of %s for %s.",
                    shares, company_id, cost.format(decimals=0))
        return True, f"Bought {shares:,} shares for {cost.format(decimals=0)}."

    def can_sell(self, company_id: str, shares: int) -> tuple[bool, str]:
        if shares <= 0:
            return False, "Enter how many shares to sell."
        held = self.shares_of(company_id)
        if shares > held:
            return False, f"You hold {held:,} shares."
        listing = self.market.listing_for(company_id)
        if listing is None or listing.delisted:
            return False, "That company is not trading."
        return True, ""

    def sell(self, company_id: str, shares: int, day: int) -> tuple[bool, str]:
        """Sell shares, booking the profit or loss against what they cost."""
        allowed, reason = self.can_sell(company_id, shares)
        if not allowed:
            return False, reason

        listing = self.market.listing_for(company_id)
        holding = self.holdings[company_id]
        proceeds = Money(listing.price.amount * Decimal(shares))

        # Cost is released in proportion to the shares sold, so selling part of
        # a holding leaves the rest carrying its own share of what was paid.
        portion = Decimal(shares) / Decimal(holding.shares)
        released = Money(holding.cost_basis.amount * portion)
        gain = proceeds - released

        holding.shares -= shares
        holding.cost_basis = holding.cost_basis - released
        if holding.shares <= 0:
            del self.holdings[company_id]

        self.player.cash = self.player.cash + proceeds
        self.realised = self.realised + gain
        self.market.record_demand(company_id, -shares)
        self._record(Trade(day, company_id, shares, listing.price, gain, False))
        logger.info("Player sold %d shares of %s for %s (%s).",
                    shares, company_id, proceeds.format(decimals=0),
                    gain.format(decimals=0, signed=True))
        return True, (
            f"Sold {shares:,} shares for {proceeds.format(decimals=0)} "
            f"({gain.format(decimals=0, signed=True)})."
        )

    def _record(self, trade: Trade) -> None:
        self.trades.append(trade)
        del self.trades[: -self.MAX_HISTORY]
        for callback in list(self.on_trade):
            callback(trade)

    # -- statistics --------------------------------------------------------
    def statistics(self) -> dict[str, object]:
        sales = [trade for trade in self.trades if not trade.is_purchase]
        wins = [trade for trade in sales if trade.realised.is_positive]
        return {
            "Holdings value": self.value(),
            "Companies held": len(self.holdings),
            "Unrealised": self.unrealised(),
            "Realised": self.realised,
            "Trades": len(self.trades),
            "Win rate": (
                Percentage(len(wins) / len(sales)).format() if sales else "—"
            ),
        }

    # -- persistence -------------------------------------------------------
    def state(self) -> dict:
        return {
            "holdings": [h.state() for h in self.holdings.values()],
            "trades": [t.state() for t in self.trades],
            "realised": str(self.realised.amount),
        }

    def restore(self, data: dict) -> None:
        self.holdings = {
            item["company_id"]: Holding.from_state(item)
            for item in data.get("holdings", [])
        }
        self.trades = [Trade.from_state(item) for item in data.get("trades", [])]
        self.realised = Money(data.get("realised", "0"))
