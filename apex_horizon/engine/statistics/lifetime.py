"""Lifetime statistics.

V28.7 asks for cumulative figures across an entire playthrough — total profit
ever generated, total employees ever hired, total companies ever acquired — as
**permanent, never-reset records**. They exist to give a long-running player a
sense of the full scale of what they have built, beyond whatever the company
happens to look like today.

That "never reset" is the whole point, and it is what makes these different from
every other figure in the game. A company can go bankrupt and be founded again
(V1.3); its ledger starts over, its employees are released, its subsidiaries are
gone. None of that touches these counters. They describe the *playthrough*, not
the company.

V28.8 sets the bar for what belongs here: every statistic should answer a
question the player would actually ask, rather than existing because the number
was easy to record. So this counts things a player would say out loud — how much
I ever made, how many people I ever employed, how many companies I ever bought —
and not, say, how many times a page was opened.

Nothing else in the engine knows this module exists. Counters are fed through
the callback lists systems already expose, so the roster does not know what a
statistic is (V15.7).
"""

from __future__ import annotations

from typing import Any

from ..config import Config, get_config
from ..logging_setup import get_logger
from ..values import Money

logger = get_logger(__name__)


class LifetimeStatistics:
    """Cumulative records for a whole playthrough (V28.7)."""

    def __init__(self, *, config: Config | None = None):
        self.config = config or get_config()
        #: Money figures that only ever grow.
        self.total_profit: Money = Money.zero()
        self.total_losses: Money = Money.zero()
        self.total_invested: Money = Money.zero()
        self.total_fees_earned: Money = Money.zero()
        self.total_spent_acquiring: Money = Money.zero()
        self.highest_net_worth: Money = Money.zero()
        self.highest_company_value: Money = Money.zero()
        #: Counts of things that happened.
        self.employees_hired: int = 0
        self.companies_acquired: int = 0
        self.companies_founded: int = 0
        self.companies_lost: int = 0
        self.funds_opened: int = 0
        self.trades_made: int = 0
        self.positions_closed: int = 0
        self.unlocks_bought: int = 0

    # -- recording ---------------------------------------------------------
    def record_hire(self, *_ignored) -> None:
        self.employees_hired += 1

    def record_acquisition(self, subsidiary) -> None:
        self.companies_acquired += 1
        self.total_spent_acquiring = self.total_spent_acquiring + subsidiary.purchase_price

    def record_founding(self, *_ignored) -> None:
        self.companies_founded += 1

    def record_bankruptcy(self, *_ignored) -> None:
        self.companies_lost += 1

    def record_fund(self, *_ignored) -> None:
        self.funds_opened += 1

    def record_unlock(self, *_ignored) -> None:
        self.unlocks_bought += 1

    def record_trade(self, *_ignored) -> None:
        self.trades_made += 1

    def record_closed_position(self, gain: Money) -> None:
        """A position sold, for better or worse."""
        self.positions_closed += 1
        if gain.is_negative:
            self.total_losses = self.total_losses + Money(-gain.amount)
        else:
            self.total_profit = self.total_profit + gain

    def record_invested(self, amount: Money) -> None:
        if amount.is_positive:
            self.total_invested = self.total_invested + amount

    def record_fee(self, amount: Money) -> None:
        if amount.is_positive:
            self.total_fees_earned = self.total_fees_earned + amount

    def observe(self, *, net_worth: Money | None = None,
                company_value: Money | None = None) -> None:
        """Track high-water marks, which only ever rise (V28.7)."""
        if net_worth is not None and net_worth > self.highest_net_worth:
            self.highest_net_worth = net_worth
        if company_value is not None and company_value > self.highest_company_value:
            self.highest_company_value = company_value

    # -- reading -----------------------------------------------------------
    def net_lifetime_profit(self) -> Money:
        return self.total_profit - self.total_losses

    def summary(self) -> dict[str, Any]:
        """Everything worth showing, in the order a player would ask it."""
        return {
            "Companies founded": self.companies_founded,
            "Companies lost": self.companies_lost,
            "Employees ever hired": self.employees_hired,
            "Companies acquired": self.companies_acquired,
            "Funds opened": self.funds_opened,
            "Unlocks bought": self.unlocks_bought,
            "Trades made": self.trades_made,
            "Positions closed": self.positions_closed,
            "Profit ever made": self.total_profit,
            "Losses ever taken": self.total_losses,
            "Net lifetime profit": self.net_lifetime_profit(),
            "Ever invested": self.total_invested,
            "Fees ever earned": self.total_fees_earned,
            "Spent acquiring": self.total_spent_acquiring,
            "Highest net worth": self.highest_net_worth,
            "Highest company value": self.highest_company_value,
        }

    # -- persistence -------------------------------------------------------
    def state(self) -> dict:
        money = (
            "total_profit", "total_losses", "total_invested", "total_fees_earned",
            "total_spent_acquiring", "highest_net_worth", "highest_company_value",
        )
        counts = (
            "employees_hired", "companies_acquired", "companies_founded",
            "companies_lost", "funds_opened", "trades_made", "positions_closed",
            "unlocks_bought",
        )
        data = {name: str(getattr(self, name).amount) for name in money}
        data.update({name: getattr(self, name) for name in counts})
        return data

    def restore(self, data: dict) -> None:
        for name in (
            "total_profit", "total_losses", "total_invested", "total_fees_earned",
            "total_spent_acquiring", "highest_net_worth", "highest_company_value",
        ):
            setattr(self, name, Money(data.get(name, "0")))
        for name in (
            "employees_hired", "companies_acquired", "companies_founded",
            "companies_lost", "funds_opened", "trades_made", "positions_closed",
            "unlocks_bought",
        ):
            setattr(self, name, int(data.get(name, 0)))
