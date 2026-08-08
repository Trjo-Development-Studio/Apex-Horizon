"""Loans.

Design Bible V17.13 gives loans an amount, interest, repayment, and history, and
makes better offers available as the company grows — the terms themselves come
from the banks of V7.10, which already tighten and loosen with the economic
cycle. Repayments fall due weekly (V13.9).

Interest accrues on the declining balance: each week the company pays a fixed
share of the original principal plus interest on what is still outstanding. That
is both realistic and legible, which matters because V17.2 requires the player to
understand where money goes.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..logging_setup import get_logger
from ..values import Money, Percentage, get_calendar

logger = get_logger(__name__)


@dataclass
class Loan:
    """One outstanding borrowing (V17.13)."""

    id: str
    bank_id: str
    bank_name: str
    principal: Money
    outstanding: Money
    interest_rate: Percentage  # annual
    term_weeks: int
    taken_on_day: int
    interest_paid: Money = field(default_factory=Money.zero)
    repaid_on_day: int | None = None

    @property
    def is_active(self) -> bool:
        return self.repaid_on_day is None and self.outstanding.is_positive

    @property
    def weekly_interest_rate(self) -> Percentage:
        weeks_per_year = get_calendar().days_per_year / get_calendar().days_per_week
        return Percentage(self.interest_rate.fraction / int(weeks_per_year))

    def scheduled_principal_payment(self) -> Money:
        """The fixed share of the original principal repaid each week."""
        return self.principal / self.term_weeks

    def weekly_payment(self) -> Money:
        """This week's total payment: principal share plus accrued interest."""
        interest = self.outstanding * self.weekly_interest_rate
        principal = min(self.scheduled_principal_payment(), self.outstanding)
        return principal + interest

    def describe(self) -> str:
        return (
            f"{self.bank_name}: {self.outstanding.format(decimals=0)} outstanding "
            f"of {self.principal.format(decimals=0)} at {self.interest_rate.format()}"
        )


class LoanBook:
    """Every loan the company has taken, active and repaid (V17.13)."""

    MAX_HISTORY = 100

    def __init__(self) -> None:
        self.loans: list[Loan] = []

    # -- borrowing --------------------------------------------------------
    def add(self, loan: Loan) -> Loan:
        self.loans.append(loan)
        del self.loans[: -self.MAX_HISTORY]
        return loan

    def active(self) -> list[Loan]:
        return [loan for loan in self.loans if loan.is_active]

    def total_outstanding(self) -> Money:
        """Total debt, which counts against company value as a liability (V17.10)."""
        total = Money.zero()
        for loan in self.active():
            total = total + loan.outstanding
        return total

    def weekly_commitment(self) -> Money:
        """What the company owes in repayments this week."""
        total = Money.zero()
        for loan in self.active():
            total = total + loan.weekly_payment()
        return total

    # -- repayment (V13.9) -------------------------------------------------
    def process_weekly_repayments(self, finances, day: int) -> Money:
        """Take this week's repayments from company cash.

        Returns the total paid. Repayments are made even when they push the
        company's cash negative — falling behind is precisely how poor financial
        management leads toward bankruptcy (V17.19), and hiding that by skipping
        payments would make the consequence untraceable (V25.7).
        """
        from .ledger import ExpenseCategory

        paid = Money.zero()
        for loan in self.active():
            interest = loan.outstanding * loan.weekly_interest_rate
            principal = min(loan.scheduled_principal_payment(), loan.outstanding)
            payment = principal + interest
            loan.outstanding = loan.outstanding - principal
            loan.interest_paid = loan.interest_paid + interest
            # Only the interest is a cost; repaying principal returns borrowed
            # capital and is financing, not an expense (V17.7, V17.8).
            if interest.is_positive:
                finances.spend(
                    day,
                    ExpenseCategory.LOAN_REPAYMENTS,
                    interest,
                    f"Interest to {loan.bank_name}",
                )
            if principal.is_positive:
                finances.repay_financing(
                    day,
                    ExpenseCategory.LOAN_REPAYMENTS,
                    principal,
                    f"Principal to {loan.bank_name}",
                )
            paid = paid + payment
            if not loan.outstanding.is_positive:
                loan.outstanding = Money.zero()
                loan.repaid_on_day = day
                logger.info("Loan from %s repaid in full.", loan.bank_name)
        return paid

    # -- persistence ------------------------------------------------------
    def state(self) -> dict:
        return {
            "loans": [
                {
                    "id": loan.id,
                    "bank_id": loan.bank_id,
                    "bank_name": loan.bank_name,
                    "principal": str(loan.principal.amount),
                    "outstanding": str(loan.outstanding.amount),
                    "interest_rate": str(loan.interest_rate.fraction),
                    "term_weeks": loan.term_weeks,
                    "taken_on_day": loan.taken_on_day,
                    "interest_paid": str(loan.interest_paid.amount),
                    "repaid_on_day": loan.repaid_on_day,
                }
                for loan in self.loans
            ]
        }

    def restore(self, data: dict) -> None:
        self.loans = [
            Loan(
                id=entry["id"],
                bank_id=entry["bank_id"],
                bank_name=entry["bank_name"],
                principal=Money(entry["principal"]),
                outstanding=Money(entry["outstanding"]),
                interest_rate=Percentage(entry["interest_rate"]),
                term_weeks=int(entry["term_weeks"]),
                taken_on_day=int(entry["taken_on_day"]),
                interest_paid=Money(entry.get("interest_paid", "0")),
                repaid_on_day=entry.get("repaid_on_day"),
            )
            for entry in data.get("loans", [])
        ]
