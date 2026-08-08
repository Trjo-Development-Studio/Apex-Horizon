"""Every fund the company runs.

V11.7 has the company eventually operating several funds at once, each working
independently while all belonging to the one investment company (V11.14). This
module is that collection, and the monthly rhythm they share: investors put more
money in, or less, according to how much they have come to trust the company
(V11.11), and each fund pays the company for managing what it holds.

Deposits arrive without the player doing anything (V11.20). That is the point of
the system — the player's job is to manage well, and capital follows a record.
"""

from __future__ import annotations

from decimal import Decimal
from random import Random

from ..config import Config, get_config
from ..logging_setup import get_logger
from ..simulation import PeriodBoundary, SimulationContext, SimulationEngine
from ..values import EntityKind, IdAllocator, Money, Percentage
from .fund import InvestmentFund

logger = get_logger(__name__)


class FundBook:
    """The company's investment funds (V11.7, V11.14)."""

    def __init__(self, company, *, allocator: IdAllocator | None = None,
                 config: Config | None = None):
        self.config = config or get_config()
        self.company = company
        self.allocator = allocator or IdAllocator()
        self.funds: list[InvestmentFund] = []
        self.market = None
        #: Unlocked through the Unlock Tree's final node (V11.3, V6.8).
        self.unlocked: bool = False
        self._last_month_day: int | None = None
        #: Called with each fund opened, for anything keeping a tally.
        self.on_created: list = []

        # Assets under management are the client's, never the company's, so
        # they are deliberately *not* registered as a company asset (V11.5).
        # What the company owns is the fee income it has already earned.

    # -- reading -----------------------------------------------------------
    def __len__(self) -> int:
        return len(self.funds)

    def __iter__(self):
        return iter(self.funds)

    def by_id(self, fund_id: str) -> InvestmentFund | None:
        return next((fund for fund in self.funds if fund.id == fund_id), None)

    def assets_under_management(self) -> Money:
        """Total AUM across every fund (V11.8)."""
        total = Money.zero()
        for fund in self.funds:
            total = total + fund.assets_under_management()
        return total

    def fees_earned(self) -> Money:
        total = Money.zero()
        for fund in self.funds:
            total = total + fund.fees_paid
        return total

    def statistics(self) -> dict[str, object]:
        return {
            "Funds": len(self.funds),
            "Assets under management": self.assets_under_management(),
            "Fees earned": self.fees_earned(),
            "Average confidence": Percentage(
                sum(fund.confidence for fund in self.funds) / len(self.funds)
            ) if self.funds else Percentage.zero(),
        }

    # -- creating a fund (V11.6) -------------------------------------------
    def can_create(self) -> tuple[bool, str]:
        if not self.unlocked:
            # V11.3: the final unlock, behind every branch of the tree (V6.8).
            return False, (
                "Investment Funds must be unlocked before the company can manage "
                "money for anyone else."
            )
        if self.company.bankrupt:
            return False, "A bankrupt company cannot open a fund."
        limit = self.config.get_int("funds.maximum_funds")
        if limit and len(self.funds) >= limit:
            return False, f"The company already runs {limit} funds."
        return True, ""

    def create(self, name: str, day: int) -> tuple[InvestmentFund | None, str]:
        """Open a fund, with whatever investors are willing to seed it (V11.6)."""
        allowed, reason = self.can_create()
        if not allowed:
            return None, reason
        name = name.strip()
        if not name:
            return None, "Give the fund a name."
        if any(fund.name.lower() == name.lower() for fund in self.funds):
            return None, f"You already run a fund called {name}."

        fund = InvestmentFund(
            fund_id=self.allocator.next_id(EntityKind.FUND),
            name=name,
            company=self.company,
            created_on_day=day,
            config=self.config,
        )
        # V11.20: a first fund receives only a modest initial deposit; what it
        # grows to depends on the record it goes on to build.
        seed = Money(self.config.get_int("funds.initial_deposit"))
        fund.receive_investment(day, seed)
        if self.market is not None:
            fund.attach_market(self.market, self.allocator)
        self.funds.append(fund)
        logger.info("Opened fund %s with %s.", name, seed.format(decimals=0))
        for callback in list(self.on_created):
            callback(fund)
        return fund, f"{name} opened with {seed.format(decimals=0)} under management."

    # -- simulation --------------------------------------------------------
    def attach_market(self, market, engine=None) -> None:
        """Connect the funds to the market they invest in."""
        self.market = market
        for fund in self.funds:
            if fund.investments is None:
                fund.attach_market(market, self.allocator)
            if engine is not None:
                fund.register(engine)

    def register(self, engine: SimulationEngine) -> None:
        engine.register_boundary(PeriodBoundary.MONTH, self.close_month)
        for fund in self.funds:
            fund.register(engine)

    def close_month(self, context: SimulationContext) -> None:
        """Fees, confidence and new deposits, once a month."""
        if self._last_month_day == context.day_number:
            return
        self._last_month_day = context.day_number
        for fund in self.funds:
            fund.charge_management_fee(context.day_number)
            self._update_confidence(fund)
            self._receive_deposits(fund, context)
            fund.history.append(str(fund.assets_under_management().amount))
            del fund.history[: -self.config.get_int("funds.history_months")]

    def _update_confidence(self, fund: InvestmentFund) -> None:
        """Trust follows the record, and moves slowly either way (V11.11)."""
        speed = self.config.get_float("funds.confidence_speed")
        target = float(fund.total_return().fraction)
        # A fund that has merely held its value earns middling confidence; one
        # that has grown earns more, and one that has lost money earns less.
        wanted = max(0.0, min(1.0, 0.5 + target * 2))
        fund.confidence += (wanted - fund.confidence) * speed

    def _receive_deposits(self, fund: InvestmentFund, context: SimulationContext) -> None:
        """More money arrives when the company has earned the trust (V11.20)."""
        threshold = self.config.get_float("funds.deposit_confidence_threshold")
        if fund.confidence < threshold:
            return
        rate = Decimal(str(self.config.get_float("funds.monthly_deposit_rate")))
        confidence = Decimal(str(fund.confidence))
        base = fund.assets_under_management()
        deposit = Money(base.amount * rate * confidence)
        minimum = Money(self.config.get_int("funds.minimum_deposit"))
        if deposit < minimum:
            deposit = minimum
        fund.receive_investment(context.day_number, deposit)

    # -- persistence -------------------------------------------------------
    def state(self) -> dict:
        return {
            "funds": [fund.state() for fund in self.funds],
            "unlocked": self.unlocked,
            "last_month_day": self._last_month_day,
        }

    def restore(self, data: dict, *, market=None) -> None:
        self.unlocked = bool(data.get("unlocked", False))
        self._last_month_day = data.get("last_month_day")
        self.funds = []
        for saved in data.get("funds", []):
            fund = InvestmentFund(
                fund_id=saved["id"],
                name=saved.get("name", ""),
                company=self.company,
                created_on_day=int(saved.get("created_on_day", 0)),
                config=self.config,
            )
            target = market if market is not None else self.market
            if target is not None:
                fund.attach_market(target, self.allocator)
            fund.restore(saved)
            self.funds.append(fund)


def seeded_name(rng: Random) -> str:
    """A plausible fund name, for when one is generated rather than chosen."""
    return f"Fund {rng.randrange(100, 999)}"
