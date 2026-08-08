"""Investment funds.

Design Bible Volume 11. V11.23 is the rule that shapes the whole module: a fund
is its own entity that shares the Volume 8 investment workflow **through
composition rather than duplication**, so that a fix or improvement to that
workflow applies to company investments and fund investments alike.

That is why there is no fund-specific investing code here. The workflow only
ever asks its owner for three things — whether it is bankrupt, who its employees
are, and its finances — so a fund supplies exactly those and runs the identical
research → approval → execution → sale process (V11.9). Only the source of
capital changes.

Whose money it is matters more here than anywhere else in the game. V11.5 is
explicit: the money inside a fund belongs to its investors, not to the player
and not to the company. The company earns by *managing* it — a fee on what it
looks after — and that fee is the only money that ever crosses from the fund to
the company.
"""

from __future__ import annotations

from decimal import Decimal

from ..company.finances import CompanyFinances
from ..config import Config, get_config
from ..logging_setup import get_logger
from ..values import Money, Percentage

logger = get_logger(__name__)


class InvestmentFund:
    """External capital the company invests on someone else's behalf (V11.5).

    Deliberately shaped like the smallest possible thing the investment workflow
    can operate on. It is not a company (V11.14): it has no employees of its
    own, borrows the company's, and belongs to the company that runs it.
    """

    def __init__(self, fund_id: str, name: str, company, *,
                 opening_capital: Money | None = None,
                 created_on_day: int = 0, config: Config | None = None):
        self.config = config or get_config()
        self.id = fund_id
        self.name = name
        self.company = company
        self.created_on_day = created_on_day
        #: The fund's own money, kept entirely apart from the company's (V11.5).
        self.finances = CompanyFinances(cash=opening_capital, config=self.config)
        #: What investors have put in, and taken out, over the fund's life.
        self.contributed: Money = opening_capital or Money.zero()
        #: Fees this fund has paid the company for managing it.
        self.fees_paid: Money = Money.zero()
        #: How much investors trust the company with this fund (V11.11), 0 to 1.
        self.confidence: float = self.config.get_float("funds.starting_confidence")
        #: Value at each month end, so performance has a history (V11.10).
        self.history: list[str] = []
        #: Created when the fund is attached to a market, exactly as a company's
        #: investment operation is (V11.23: composition, not duplication).
        self.investments = None
        #: Called with each management fee charged, for anything keeping a tally.
        self.on_fee: list = []

        self.finances.register_asset_provider("investments", self._holdings_value)

    # -- what the investment workflow needs --------------------------------
    @property
    def bankrupt(self) -> bool:
        """A fund is never bankrupt in its own right (V11.21 leaves it open)."""
        return False

    @property
    def employees(self):
        """The company's people run the funds too (V11.14)."""
        return self.company.employees

    def _holdings_value(self) -> Money:
        return self.investments.holdings_value() if self.investments else Money.zero()

    # -- operating ---------------------------------------------------------
    def attach_market(self, market, allocator=None):
        """Give the fund an investment operation of its own (V11.9)."""
        from ..investments import InvestmentSystem

        self.investments = InvestmentSystem(
            self, market, allocator=allocator, config=self.config
        )
        return self.investments

    def register(self, engine) -> None:
        if self.investments is not None:
            self.investments.register(engine)

    # -- what the fund is worth (V11.8, V11.10) ----------------------------
    def assets_under_management(self) -> Money:
        """Everything the fund holds, in cash and in positions (V11.8)."""
        return self.finances.cash + self._holdings_value()

    def total_return(self) -> Percentage:
        """What the fund has made for its investors, against what they put in."""
        if not self.contributed.is_positive:
            return Percentage.zero()
        gain = self.assets_under_management() - self.contributed
        return Percentage(gain.amount / self.contributed.amount)

    def receive_investment(self, day: int, amount: Money) -> None:
        """Take money from external investors (V11.5).

        Their capital is not revenue — the fund has not earned it, it has been
        entrusted with it (V17.26), so it is recorded as financing exactly as an
        owner's capital is in a company.
        """
        if not amount.is_positive:
            return
        self.finances.receive_capital_injection(day, amount, "External investors")
        self.contributed = self.contributed + amount

    def charge_management_fee(self, day: int) -> Money:
        """Pay the company for managing this fund (V11.5).

        The only money that ever crosses from a fund to the company. Charged on
        assets under management rather than on profit, which is what makes funds
        expand the company's *influence* rather than simply its winnings
        (V11.4).
        """
        rate = Decimal(str(self.config.get_float("funds.annual_management_fee")))
        monthly = rate / Decimal(12)
        fee = Money(self.assets_under_management().amount * monthly)
        if not fee.is_positive or fee > self.finances.cash:
            return Money.zero()
        self.finances.spend_management_fee(day, fee, self.name)
        self.company.finances.receive_fund_income(day, fee, self.name)
        self.fees_paid = self.fees_paid + fee
        for callback in list(self.on_fee):
            callback(fee)
        return fee

    # -- statistics (V11.10) ----------------------------------------------
    def statistics(self) -> dict[str, object]:
        positions = self.investments.open_positions() if self.investments else []
        return {
            "Assets under management": self.assets_under_management(),
            "Invested by clients": self.contributed,
            "Total return": self.total_return(),
            "Active investments": len(positions),
            "Fees earned": self.fees_paid,
            "Investor confidence": Percentage(self.confidence),
        }

    # -- persistence -------------------------------------------------------
    def state(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "created_on_day": self.created_on_day,
            "finances": self.finances.state(),
            "contributed": str(self.contributed.amount),
            "fees_paid": str(self.fees_paid.amount),
            "confidence": self.confidence,
            "history": list(self.history),
            "investments": self.investments.state() if self.investments else {},
        }

    def restore(self, data: dict) -> None:
        self.name = data.get("name", self.name)
        self.created_on_day = int(data.get("created_on_day", 0))
        self.finances.restore(data.get("finances", {}))
        self.contributed = Money(data.get("contributed", "0"))
        self.fees_paid = Money(data.get("fees_paid", "0"))
        self.confidence = float(data.get("confidence", self.confidence))
        self.history = list(data.get("history", []))
        if self.investments is not None:
            self.investments.restore(data.get("investments", {}))
