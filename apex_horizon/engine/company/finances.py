"""Company finances.

Design Bible Volume 17 defines the financial backbone: cash flow, revenue,
expenses, profit, assets, liabilities, net worth, and company value. V17.2 sets
the standard they must meet — the player should always understand where money
comes from, where it is spent, and why profit rises or falls.

Every movement of money passes through :meth:`receive` or :meth:`spend`, which
write to the single append-only ledger required by V17.27. Nothing adjusts cash
without recording why, so the cash balance and the financial reports can never
disagree.

Assets the company holds outside cash — investments, subsidiaries, funds — are
supplied by the systems that own them through registered providers, rather than
being duplicated here. That keeps each system responsible for its own data
(V15.7) while V17.9's definition of assets stays in one place.
"""

from __future__ import annotations

from collections.abc import Callable

from ..config import Config, get_config
from ..values import Money, Percentage
from .ledger import ExpenseCategory, Ledger, PeriodTotals, RevenueCategory

# A provider reports the current value of assets owned elsewhere in the game.
AssetProvider = Callable[[], Money]


class CompanyFinances:
    """The company's money, and everything derived from it."""

    def __init__(self, *, cash: Money | None = None, config: Config | None = None):
        self.config = config or get_config()
        self.cash = cash or Money.zero()
        self.ledger = Ledger()
        self._asset_providers: dict[str, AssetProvider] = {}
        self._liability_providers: dict[str, AssetProvider] = {}
        # Most recent closed-period figures, for reporting (V17.14).
        self.last_week = PeriodTotals()
        self.last_month = PeriodTotals()
        self.last_year = PeriodTotals()

    # -- movements of money ------------------------------------------------
    def receive(
        self, day: int, category: RevenueCategory, amount: Money, description: str = ""
    ) -> None:
        """Take money in, recording why (V17.5)."""
        if amount.is_negative:
            raise ValueError("Revenue amounts must be positive")
        self.cash = self.cash + amount
        self.ledger.record_revenue(day, category, amount, description)

    def spend(
        self, day: int, category: ExpenseCategory, amount: Money, description: str = ""
    ) -> None:
        """Pay money out, recording why (V17.7).

        Spending is allowed to push cash negative. A company that cannot meet
        its commitments is exactly what bankruptcy represents (V17.19), and
        silently refusing payments would make that consequence untraceable.
        Callers that must not overspend should check ``can_afford`` first.
        """
        if amount.is_negative:
            raise ValueError("Expense amounts must be positive")
        self.cash = self.cash - amount
        self.ledger.record_expense(day, category, amount, description)

    def receive_financing(
        self, day: int, category: RevenueCategory, amount: Money, description: str = ""
    ) -> None:
        """Take in cash that was not earned — owner capital or a loan (V17.5).

        It moves cash and shows in cash flow, but never counts as revenue, so
        borrowing can never be mistaken for trading profitably (V17.26).
        """
        if amount.is_negative:
            raise ValueError("Financing amounts must be positive")
        self.cash = self.cash + amount
        self.ledger.record_financing_in(day, category, amount, description)

    def repay_financing(
        self, day: int, category: ExpenseCategory, amount: Money, description: str = ""
    ) -> None:
        """Repay borrowed capital. Principal is not a cost; interest is."""
        if amount.is_negative:
            raise ValueError("Financing amounts must be positive")
        self.cash = self.cash - amount
        self.ledger.record_financing_out(day, category, amount, description)

    # -- investing (V8.7, V8.11) -------------------------------------------
    def invest(self, day: int, amount: Money, description: str = "") -> None:
        """Commit cash to an investment.

        Buying is not a cost: it exchanges cash for an asset of the same value,
        so it moves cash and appears in cash flow but never reduces profit. Only
        the eventual gain or loss does — which is the same reasoning that keeps
        borrowing out of revenue (V17.6, V17.26).
        """
        if amount.is_negative:
            raise ValueError("Investment amounts must be positive")
        self.cash = self.cash - amount
        self.ledger.record_financing_out(
            day, ExpenseCategory.INVESTMENTS, amount, description
        )

    def realise_investment(
        self, day: int, proceeds: Money, cost_basis: Money, description: str = ""
    ) -> Money:
        """Close an investment, booking the profit or loss (V8.11).

        The capital that comes back is financing; only the difference between
        proceeds and what was paid is profit or loss. Cash moves once, and the
        ledger records the two halves separately so the player can see where
        company profit actually came from (V9.12).
        """
        if proceeds.is_negative or cost_basis.is_negative:
            raise ValueError("Proceeds and cost basis must be positive")

        self.cash = self.cash + proceeds
        returned = proceeds if proceeds < cost_basis else cost_basis
        if returned.is_positive:
            self.ledger.record_financing_in(
                day, RevenueCategory.ASSET_SALE, returned, description
            )
        gain = proceeds - cost_basis
        if gain.is_positive:
            self.ledger.record_revenue(
                day, RevenueCategory.INVESTMENT_PROFIT, gain, description
            )
        elif gain.is_negative:
            # Recorded straight onto the ledger: the cash movement has already
            # happened, and this is the loss, not a second payment.
            self.ledger.record_expense(
                day, ExpenseCategory.INVESTMENTS, -gain, description
            )
        return gain

    def cash_flow(self) -> dict[str, Money]:
        """Total cash in and out, including financing (V17.5)."""
        return {
            "Cash In": self.ledger.cash_in,
            "Cash Out": self.ledger.cash_out,
            "Net": self.ledger.cash_in - self.ledger.cash_out,
        }

    def can_afford(self, amount: Money) -> bool:
        return self.cash >= amount

    # -- assets and liabilities (V17.9 - V17.11) ---------------------------
    def register_asset_provider(self, name: str, provider: AssetProvider) -> None:
        """Let another system contribute to total assets (investments, funds...)."""
        self._asset_providers[name] = provider

    def register_liability_provider(self, name: str, provider: AssetProvider) -> None:
        """Let another system contribute to total liabilities (loans...)."""
        self._liability_providers[name] = provider

    def other_assets(self) -> Money:
        total = Money.zero()
        for provider in self._asset_providers.values():
            total = total + provider()
        return total

    def assets(self) -> Money:
        """Cash plus everything else the company owns (V17.9)."""
        return self.cash + self.other_assets()

    def liabilities(self) -> Money:
        """Outstanding loans and other obligations (V17.10)."""
        total = Money.zero()
        for provider in self._liability_providers.values():
            total = total + provider()
        return total

    def net_worth(self) -> Money:
        """Assets minus liabilities (V17.11)."""
        return self.assets() - self.liabilities()

    def company_value(self, level: int = 1) -> Money:
        """Overall worth of the company (V17.12).

        Net worth plus goodwill: a multiple of the last year's profit, so a
        consistently profitable company is worth more than the sum of its parts,
        while a loss-making one is worth less. Goodwill never drags value below
        the company's tangible net worth being negative on its own account.
        """
        multiple = self.config.get_float("company.value_profit_multiple")
        goodwill = self.last_year.profit * multiple
        value = self.net_worth() + goodwill
        return value

    # -- profit (V17.6 - V17.8) -------------------------------------------
    @property
    def revenue_this_week(self) -> Money:
        return self.ledger.week.revenue

    @property
    def expenses_this_week(self) -> Money:
        return self.ledger.week.expenses

    @property
    def profit_this_week(self) -> Money:
        return self.ledger.week.profit

    @property
    def lifetime_profit(self) -> Money:
        return self.ledger.lifetime.profit

    def profit_margin(self) -> Percentage:
        """Profit as a share of revenue over the company's lifetime."""
        revenue = self.ledger.lifetime.revenue
        if revenue.is_zero:
            return Percentage.zero()
        return Percentage(self.ledger.lifetime.profit.amount / revenue.amount)

    # -- period closes -----------------------------------------------------
    def close_week(self) -> PeriodTotals:
        self.last_week = self.ledger.close_week()
        return self.last_week

    def close_month(self, day: int) -> PeriodTotals:
        self.last_month = self.ledger.close_month(day)
        return self.last_month

    def close_year(self) -> PeriodTotals:
        self.last_year = self.ledger.close_year()
        return self.last_year

    # -- reporting (V17.14) ------------------------------------------------
    def report(self, level: int = 1) -> dict[str, Money]:
        """A professional financial summary the player can read at a glance."""
        return {
            "Cash": self.cash,
            "Revenue (year)": self.ledger.year.revenue,
            "Expenses (year)": self.ledger.year.expenses,
            "Profit (year)": self.ledger.year.profit,
            "Assets": self.assets(),
            "Liabilities": self.liabilities(),
            "Net Worth": self.net_worth(),
            "Company Value": self.company_value(level),
        }

    # -- persistence -------------------------------------------------------
    def state(self) -> dict:
        return {
            "cash": str(self.cash.amount),
            "ledger": self.ledger.state(),
            "last_week": {"revenue": str(self.last_week.revenue.amount),
                          "expenses": str(self.last_week.expenses.amount)},
            "last_month": {"revenue": str(self.last_month.revenue.amount),
                           "expenses": str(self.last_month.expenses.amount)},
            "last_year": {"revenue": str(self.last_year.revenue.amount),
                          "expenses": str(self.last_year.expenses.amount)},
        }

    def restore(self, data: dict) -> None:
        self.cash = Money(data.get("cash", "0"))
        self.ledger.restore(data.get("ledger", {}))
        for name in ("last_week", "last_month", "last_year"):
            entry = data.get(name)
            totals = PeriodTotals()
            if entry:
                totals = PeriodTotals(
                    revenue=Money(entry["revenue"]), expenses=Money(entry["expenses"])
                )
            setattr(self, name, totals)
