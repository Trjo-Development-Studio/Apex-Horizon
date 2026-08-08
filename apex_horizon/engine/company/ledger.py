"""The financial ledger.

Design Bible V17.27 is specific about how company finances should be recorded:
every category of expense should write to a single, append-only ledger, from
which both the continuous profit calculation (V17.8) and the periodic financial
reports (V17.14) are derived — rather than maintaining separate running totals
that could drift out of sync with one another.

That is the rule this module enforces. Every figure the game reports about
company money is produced by :meth:`Ledger.record`; nothing anywhere else may
adjust a total directly, so the reports and the profit line can never disagree.

A save cannot hold every entry from hundreds of in-game years (V16.20), so the
ledger keeps recent entries in full, monthly summaries for history, and lifetime
totals. All three are updated by the same single call, so they remain consistent
by construction rather than by discipline.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from enum import Enum

from ..values import Money


class EntryKind(Enum):
    """What kind of movement an entry records.

    Financing is deliberately distinct from revenue and expense. Money the owner
    puts in, and money a bank lends, is cash the company *receives* but has not
    *earned* — counting it as revenue would inflate profit and let the player
    mistake borrowing for trading well, which is precisely the confusion V17.26
    requires the interface to make impossible. Financing therefore moves cash and
    appears in cash flow (V17.5), but never touches revenue, expenses or profit.
    """

    REVENUE = "revenue"
    EXPENSE = "expense"
    FINANCING_IN = "financing_in"
    FINANCING_OUT = "financing_out"


class RevenueCategory(Enum):
    """Where company money comes from (V17.5)."""

    INVESTMENT_PROFIT = "Investment profit"
    DIVIDENDS = "Dividend income"
    SUBSIDIARY_INCOME = "Subsidiary income"
    FUND_INCOME = "Fund management income"
    ASSET_SALE = "Asset sales"
    CAPITAL_INJECTION = "Owner capital"
    LOAN_DRAWDOWN = "Loan drawdown"
    OTHER = "Other income"


class ExpenseCategory(Enum):
    """Where company money goes (V17.7)."""

    SALARIES = "Salaries"
    RESEARCH = "Research"
    LOAN_REPAYMENTS = "Loan repayments"
    INVESTMENTS = "Investments"
    OPERATIONAL = "Operational costs"
    ACQUISITIONS = "Acquisitions"
    FUND_MANAGEMENT = "Fund management fees"
    TAX = "Tax"
    OTHER = "Other costs"


@dataclass(frozen=True)
class LedgerEntry:
    """One movement of company money."""

    day: int
    kind: EntryKind
    category: str
    amount: Money
    description: str = ""


@dataclass
class PeriodTotals:
    """Revenue and expenses accumulated over one period (V17.6, V17.8)."""

    revenue: Money = field(default_factory=Money.zero)
    expenses: Money = field(default_factory=Money.zero)

    @property
    def profit(self) -> Money:
        """Profit is revenue minus expenses (V17.8)."""
        return self.revenue - self.expenses

    def reset(self) -> PeriodTotals:
        """Return these totals and start a fresh period."""
        closed = PeriodTotals(revenue=self.revenue, expenses=self.expenses)
        self.revenue = Money.zero()
        self.expenses = Money.zero()
        return closed


class Ledger:
    """An append-only record of every movement of company money."""

    # Recent entries kept in full; older detail survives as monthly summaries.
    MAX_ENTRIES = 2_000
    MAX_MONTHLY_SUMMARIES = 240  # twenty in-game years

    def __init__(self) -> None:
        self.entries: deque[LedgerEntry] = deque(maxlen=self.MAX_ENTRIES)
        self.week = PeriodTotals()
        self.month = PeriodTotals()
        self.year = PeriodTotals()
        self.lifetime = PeriodTotals()
        # Total cash movements, including financing, for cash flow (V17.5).
        self.cash_in = Money.zero()
        self.cash_out = Money.zero()
        # Lifetime totals per category, for the expense breakdown of V17.7.
        self.by_category: dict[str, Money] = {}
        self.monthly_summaries: deque[dict] = deque(maxlen=self.MAX_MONTHLY_SUMMARIES)

    # -- recording --------------------------------------------------------
    def record(self, entry: LedgerEntry) -> LedgerEntry:
        """Append an entry and update every derived total in one place."""
        if entry.amount.is_negative:
            raise ValueError("Ledger amounts must be positive; use the matching kind")

        self.entries.append(entry)
        periods = (self.week, self.month, self.year, self.lifetime)
        if entry.kind is EntryKind.REVENUE:
            for period in periods:
                period.revenue = period.revenue + entry.amount
            self.cash_in = self.cash_in + entry.amount
        elif entry.kind is EntryKind.EXPENSE:
            for period in periods:
                period.expenses = period.expenses + entry.amount
            self.cash_out = self.cash_out + entry.amount
        elif entry.kind is EntryKind.FINANCING_IN:
            self.cash_in = self.cash_in + entry.amount
        else:
            self.cash_out = self.cash_out + entry.amount
        self.by_category[entry.category] = (
            self.by_category.get(entry.category, Money.zero()) + entry.amount
        )
        return entry

    def record_revenue(
        self, day: int, category: RevenueCategory, amount: Money, description: str = ""
    ) -> LedgerEntry:
        return self.record(
            LedgerEntry(day, EntryKind.REVENUE, category.value, amount, description)
        )

    def record_expense(
        self, day: int, category: ExpenseCategory, amount: Money, description: str = ""
    ) -> LedgerEntry:
        return self.record(
            LedgerEntry(day, EntryKind.EXPENSE, category.value, amount, description)
        )

    def record_financing_in(
        self, day: int, category: RevenueCategory, amount: Money, description: str = ""
    ) -> LedgerEntry:
        """Cash received that was not earned: owner capital, loan drawdowns."""
        return self.record(
            LedgerEntry(day, EntryKind.FINANCING_IN, category.value, amount, description)
        )

    def record_financing_out(
        self, day: int, category: ExpenseCategory, amount: Money, description: str = ""
    ) -> LedgerEntry:
        """Cash repaid that is not a cost: loan principal."""
        return self.record(
            LedgerEntry(day, EntryKind.FINANCING_OUT, category.value, amount, description)
        )

    # -- periods ----------------------------------------------------------
    def close_week(self) -> PeriodTotals:
        """Close the week and return its totals (V13.9)."""
        return self.week.reset()

    def close_month(self, day: int) -> PeriodTotals:
        """Close the month, keeping a summary for financial history (V17.15)."""
        totals = self.month.reset()
        self.monthly_summaries.append(
            {
                "day": day,
                "revenue": str(totals.revenue.amount),
                "expenses": str(totals.expenses.amount),
            }
        )
        return totals

    def close_year(self) -> PeriodTotals:
        """Close the year and return its totals (V13.11)."""
        return self.year.reset()

    # -- reporting (V17.14) ------------------------------------------------
    def expense_breakdown(self) -> dict[str, Money]:
        """Lifetime spend per expense category, largest first."""
        expenses = {category.value for category in ExpenseCategory}
        found = {k: v for k, v in self.by_category.items() if k in expenses}
        return dict(sorted(found.items(), key=lambda kv: kv[1].amount, reverse=True))

    def revenue_breakdown(self) -> dict[str, Money]:
        """Lifetime income per revenue category, largest first."""
        revenues = {category.value for category in RevenueCategory}
        found = {k: v for k, v in self.by_category.items() if k in revenues}
        return dict(sorted(found.items(), key=lambda kv: kv[1].amount, reverse=True))

    def recent(self, count: int = 20) -> list[LedgerEntry]:
        return list(self.entries)[-count:]

    # -- persistence ------------------------------------------------------
    def state(self) -> dict:
        return {
            "entries": [
                {
                    "day": e.day,
                    "kind": e.kind.value,
                    "category": e.category,
                    "amount": str(e.amount.amount),
                    "description": e.description,
                }
                for e in self.entries
            ],
            "week": _totals_state(self.week),
            "month": _totals_state(self.month),
            "year": _totals_state(self.year),
            "lifetime": _totals_state(self.lifetime),
            "cash_in": str(self.cash_in.amount),
            "cash_out": str(self.cash_out.amount),
            "by_category": {k: str(v.amount) for k, v in self.by_category.items()},
            "monthly_summaries": list(self.monthly_summaries),
        }

    def restore(self, data: dict) -> None:
        self.entries = deque(
            (
                LedgerEntry(
                    day=int(e["day"]),
                    kind=EntryKind(e["kind"]),
                    category=e["category"],
                    amount=Money(e["amount"]),
                    description=e.get("description", ""),
                )
                for e in data.get("entries", [])
            ),
            maxlen=self.MAX_ENTRIES,
        )
        self.week = _totals_from(data.get("week"))
        self.month = _totals_from(data.get("month"))
        self.year = _totals_from(data.get("year"))
        self.lifetime = _totals_from(data.get("lifetime"))
        self.cash_in = Money(data.get("cash_in", "0"))
        self.cash_out = Money(data.get("cash_out", "0"))
        self.by_category = {
            k: Money(v) for k, v in data.get("by_category", {}).items()
        }
        self.monthly_summaries = deque(
            data.get("monthly_summaries", []), maxlen=self.MAX_MONTHLY_SUMMARIES
        )


def _totals_state(totals: PeriodTotals) -> dict:
    return {"revenue": str(totals.revenue.amount), "expenses": str(totals.expenses.amount)}


def _totals_from(data: dict | None) -> PeriodTotals:
    if not data:
        return PeriodTotals()
    return PeriodTotals(revenue=Money(data["revenue"]), expenses=Money(data["expenses"]))
