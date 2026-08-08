"""Acquisitions and subsidiaries.

Design Bible Volume 12. Two of its rules do most of the shaping:

* **V12.23** wants a subsidiary to be a *lightweight ownership wrapper* around
  the same company data the market already lists, so acquiring a company mainly
  changes an ownership reference rather than introducing a second model. The
  world's :class:`~apex_horizon.engine.world.Company` already carries
  ``owner_id`` for exactly this, and that is what an acquisition sets.
* **V12.22** requires the full purchase price in available company cash, with no
  financing of any kind, so that every acquisition represents accumulated
  success rather than leveraged speculation (V25.11).

Money comes from the company and never from the player (V12.4, V1.4), and an
attempt that cannot be afforded fails gracefully rather than driving the balance
negative (V12.21).

A subsidiary is not an investment. V12.12 draws the line: shares are temporary,
an acquisition is permanent ownership of a business that keeps operating in its
own industry (V12.5) and pays its owner an ongoing share of what it earns.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from ..config import Config, get_config
from ..logging_setup import get_logger
from ..simulation import PeriodBoundary, SimulationContext, SimulationEngine
from ..values import Money, Percentage

logger = get_logger(__name__)


@dataclass
class Subsidiary:
    """One acquired company, owned outright by an investment company."""

    company_id: str
    name: str
    industry: str
    acquired_on_day: int
    #: What was paid, kept so the acquisition can be judged honestly later.
    purchase_price: Money
    #: What the business is reckoned to be worth now.
    valuation: Money
    #: Income paid up to the parent since the acquisition (V12.5).
    lifetime_income: Money = field(default_factory=Money.zero)

    def return_since_purchase(self) -> Percentage:
        """Value plus income against what was paid — was it a good buy?"""
        if not self.purchase_price.is_positive:
            return Percentage.zero()
        gain = (self.valuation + self.lifetime_income) - self.purchase_price
        return Percentage(gain.amount / self.purchase_price.amount)

    def state(self) -> dict:
        return {
            "company_id": self.company_id,
            "name": self.name,
            "industry": self.industry,
            "acquired_on_day": self.acquired_on_day,
            "purchase_price": str(self.purchase_price.amount),
            "valuation": str(self.valuation.amount),
            "lifetime_income": str(self.lifetime_income.amount),
        }

    @classmethod
    def from_state(cls, data: dict) -> Subsidiary:
        return cls(
            company_id=data["company_id"],
            name=data.get("name", ""),
            industry=data.get("industry", ""),
            acquired_on_day=int(data.get("acquired_on_day", 0)),
            purchase_price=Money(data.get("purchase_price", "0")),
            valuation=Money(data.get("valuation", "0")),
            lifetime_income=Money(data.get("lifetime_income", "0")),
        )


class SubsidiaryBook:
    """Every company one investment company owns (V12.6, V12.7).

    The parent is always the investment company itself — the player never runs
    more than one, and subsidiaries never own subsidiaries of their own.
    """

    def __init__(self, company, world, market, *, config: Config | None = None):
        self.config = config or get_config()
        self.company = company
        self.world = world
        self.market = market
        self.subsidiaries: list[Subsidiary] = []
        self._last_income_day: int | None = None

        # Subsidiaries count toward company value (V12.11, V17.12) without the
        # finances module needing to know what a subsidiary is (V15.7).
        company.finances.register_asset_provider("subsidiaries", self.total_value)

    # -- reading -----------------------------------------------------------
    def __len__(self) -> int:
        return len(self.subsidiaries)

    def __iter__(self):
        return iter(self.subsidiaries)

    def by_id(self, company_id: str) -> Subsidiary | None:
        return next(
            (s for s in self.subsidiaries if s.company_id == company_id), None
        )

    def owns(self, company_id: str) -> bool:
        return self.by_id(company_id) is not None

    def total_value(self) -> Money:
        total = Money.zero()
        for subsidiary in self.subsidiaries:
            total = total + subsidiary.valuation
        return total

    def total_income(self) -> Money:
        total = Money.zero()
        for subsidiary in self.subsidiaries:
            total = total + subsidiary.lifetime_income
        return total

    # -- what a company costs ---------------------------------------------
    def price_of(self, company_id: str) -> Money | None:
        """What it would cost to buy a listed company outright.

        The Design Bible does not give a formula, so the market's own valuation
        is used: the whole company at its traded price, plus a premium, since
        nobody sells control for the same price as a single share. The premium
        is configuration, so the cost of expansion stays tunable (V15.10).
        """
        listing = self.market.listing_for(company_id)
        if listing is None or listing.delisted:
            return None
        premium = Decimal(str(self.config.get_float("acquisitions.control_premium")))
        return Money(listing.market_cap.amount * (Decimal(1) + premium))

    def can_acquire(self, company_id: str) -> tuple[bool, str]:
        """Whether this company may be bought now, and why not if not."""
        if self.company.bankrupt:
            return False, "A bankrupt company cannot acquire anything."
        record = self.world.company_by_id(company_id)
        if record is None:
            return False, "That company does not exist."
        if record.is_subsidiary:
            return False, f"{record.name} already belongs to another company."
        if self.owns(company_id):
            return False, f"You already own {record.name}."

        minimum_level = self.config.get_int("acquisitions.minimum_company_level")
        if self.company.level < minimum_level:
            # V12.15 places acquisitions among the later stages of growth.
            return False, (
                f"Acquiring companies requires Company Level {minimum_level}."
            )

        price = self.price_of(company_id)
        if price is None:
            return False, f"{record.name} is not trading."
        if price > self.company.finances.cash:
            # V12.21, V12.22: no financing, and never a negative balance.
            return False, (
                f"{record.name} would cost {price.format(decimals=0)}; "
                f"the company has {self.company.finances.cash.format(decimals=0)}."
            )
        return True, ""

    # -- acquiring ---------------------------------------------------------
    def acquire(self, company_id: str, day: int) -> tuple[Subsidiary | None, str]:
        """Buy a company outright, in cash (V12.4, V12.22)."""
        allowed, reason = self.can_acquire(company_id)
        if not allowed:
            return None, reason

        record = self.world.company_by_id(company_id)
        price = self.price_of(company_id)

        # Paying for a business is an exchange of cash for an asset, not an
        # expense: it must never look like a loss on the profit statement
        # (V17.26), exactly as buying shares does not.
        self.company.finances.invest(day, price, f"Acquired {record.name}")

        # V12.23: ownership is a reference on the company that already exists.
        record.owner_id = self.company.id
        subsidiary = Subsidiary(
            company_id=company_id,
            name=record.name,
            industry=record.industry.value,
            acquired_on_day=day,
            purchase_price=price,
            valuation=price,
        )
        self.subsidiaries.append(subsidiary)

        # Owning a company outright means its shares no longer trade (project
        # manager ruling). The market is told, so nobody keeps buying a company
        # that is no longer for sale.
        self.market.delist(company_id, reason="acquired")
        logger.info("%s acquired %s for %s.",
                    self.company.name, record.name, price.format(decimals=0))
        return subsidiary, f"Acquired {record.name} for {price.format(decimals=0)}."

    # -- ongoing operation (V12.5) ----------------------------------------
    def register(self, engine: SimulationEngine) -> None:
        """Subsidiaries pay up monthly, alongside the rest of the accounts."""
        engine.register_boundary(PeriodBoundary.MONTH, self.collect_income)

    def collect_income(self, context: SimulationContext) -> None:
        """Take each subsidiary's monthly contribution (V12.5, V18.4).

        A subsidiary keeps operating in its own industry, so what it earns
        follows that industry's fortunes: a healthy sector pays more, a
        declining one less. V12.21 leaves the severe-decline case deliberately
        open, so income simply falls rather than triggering anything else.
        """
        if self._last_income_day == context.day_number:
            return
        self._last_income_day = context.day_number
        if self.company.bankrupt or not self.subsidiaries:
            return

        base = Decimal(str(self.config.get_float("acquisitions.monthly_income_yield")))
        sensitivity = Decimal(
            str(self.config.get_float("acquisitions.industry_income_sensitivity"))
        )
        for subsidiary in self.subsidiaries:
            trend = Decimal(str(self._industry_trend(subsidiary)))
            rate = base * (Decimal(1) + trend * sensitivity)
            if rate < 0:
                rate = Decimal(0)
            income = Money(subsidiary.valuation.amount * rate)
            if not income.is_positive:
                continue
            subsidiary.lifetime_income = subsidiary.lifetime_income + income
            self.company.finances.receive_subsidiary_income(
                context.day_number, income, subsidiary.name
            )
            # The business is worth more or less as its industry moves, which is
            # what makes a poor acquisition genuinely poor (V12.11).
            subsidiary.valuation = Money(
                subsidiary.valuation.amount * (Decimal(1) + trend * sensitivity / 12)
            )

    def _industry_trend(self, subsidiary: Subsidiary) -> float:
        if self.market is None:
            return 0.0
        for industry, trend in self.market.industry_trends.items():
            if industry.value == subsidiary.industry:
                return trend
        return 0.0

    # -- persistence -------------------------------------------------------
    def state(self) -> dict:
        return {
            "subsidiaries": [s.state() for s in self.subsidiaries],
            "last_income_day": self._last_income_day,
        }

    def restore(self, data: dict) -> None:
        self.subsidiaries = [
            Subsidiary.from_state(item) for item in data.get("subsidiaries", [])
        ]
        self._last_income_day = data.get("last_income_day")
