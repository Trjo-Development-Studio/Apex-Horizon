"""The player's investment company.

Design Bible Volume 3 makes the company the heart of the game: a persistent,
ownable entity that survives beyond any single decision, separate from the
player themselves (V3.16). It owns cash, employees, investments, subsidiaries,
funds, reputation, and statistics (V3.2).

The company updates in the Companies phase, which V29.6 places fourth in the
day — after the economy and banks, so its condition reflects them — and its
financial figures settle in the Financial Calculations phase, ninth (V29.11),
once the day's activity is complete.
"""

from __future__ import annotations

from collections.abc import Callable

from ..config import Config, get_config
from ..logging_setup import get_logger
from ..simulation import PeriodBoundary, SimulationContext, SimulationEngine, SimulationPhase
from ..values import EntityKind, IdAllocator, Money, Percentage
from .finances import CompanyFinances
from .ledger import ExpenseCategory, RevenueCategory
from .loans import Loan, LoanBook

logger = get_logger(__name__)


class PlayerCompany:
    """The single investment company the player owns and manages (V1.3, V3.3)."""

    def __init__(
        self,
        company_id: str,
        name: str,
        founded_on_day: int,
        *,
        opening_cash: Money | None = None,
        config: Config | None = None,
    ):
        self.config = config or get_config()
        self.id = company_id
        self.name = name
        self.founded_on_day = founded_on_day
        self.finances = CompanyFinances(cash=opening_cash, config=self.config)
        self.loans = LoanBook()
        # Reputation in [0, 1] affects loans, applicants and opportunities (V3.8).
        self.reputation: float = self.config.get_float("company.starting_reputation")
        # Company Level is raised by purchasing unlocks in the Company branch of
        # the Unlock Tree (V6.7.3), not automatically by growth.
        self.level: int = 1
        self.bankrupt: bool = False
        self.bankrupt_on_day: int | None = None
        # Systems that must react to bankruptcy register here, so this module
        # never needs to know about employees, subsidiaries, or funds (V15.7).
        self.on_bankruptcy: list[Callable[[PlayerCompany], None]] = []

        # Employees belong to the company, not the player (V5.2).
        from ..employees import EmployeeRoster

        self.employees = EmployeeRoster(self, config=self.config)
        # On bankruptcy, training is cancelled and staff are released (project
        # manager ruling, recorded in docs/design-decisions.md).
        self.on_bankruptcy.append(
            lambda company: company.employees.release_all(company.bankrupt_on_day or 0)
        )

        #: Created when the company is connected to a market (V8.7).
        self.investments = None

        self.finances.register_liability_provider("loans", self.loans.total_outstanding)
        self._last_daily_day: int | None = None

    # -- progression -------------------------------------------------------
    @property
    def employee_capacity(self) -> int:
        """Maximum employees at the current level (V5.17, V18.5)."""
        capacities = self.config.get_list("company.employee_capacity_per_level")
        index = max(1, min(self.level, len(capacities))) - 1
        return int(capacities[index])

    @property
    def max_level(self) -> int:
        return self.config.get_int("company.max_level")

    def set_level(self, level: int) -> None:
        """Set the company level, as purchased through the Unlock Tree (V6.7.3)."""
        self.level = max(1, min(level, self.max_level))
        logger.info("%s reached Company Level %d.", self.name, self.level)

    # -- money -------------------------------------------------------------
    def value(self) -> Money:
        return self.finances.company_value(self.level)

    def receive_capital(self, day: int, amount: Money) -> None:
        """Accept money transferred in by the owner (V1.4, V3.4)."""
        self.finances.receive_financing(
            day, RevenueCategory.CAPITAL_INJECTION, amount, "Owner capital transfer"
        )

    def take_loan(self, terms, amount: Money, day: int, allocator: IdAllocator) -> Loan | None:
        """Borrow from a bank on the terms it currently offers (V17.13).

        Returns ``None`` when the bank will not lend, or the amount is outside
        what it will provide — the offer's own conditions decide, so lending
        stays governed by the economy (V7.10).
        """
        minimum = Money(self.config.get_int("loans.minimum_amount"))
        if not terms.available or amount < minimum or amount > terms.maximum_loan:
            return None

        loan = Loan(
            id=allocator.next_id(EntityKind.LOAN),
            bank_id=terms.bank_id,
            bank_name=terms.bank_name,
            principal=amount,
            outstanding=amount,
            interest_rate=terms.interest_rate,
            term_weeks=self.config.get_int("loans.default_term_weeks"),
            taken_on_day=day,
        )
        self.loans.add(loan)
        self.finances.receive_financing(
            day, RevenueCategory.LOAN_DRAWDOWN, amount, f"Loan from {terms.bank_name}"
        )
        logger.info("%s borrowed %s from %s.", self.name, amount.format(decimals=0),
                    terms.bank_name)
        return loan

    def attach_market(self, market, allocator=None) -> None:
        """Give the company an investment operation on a market (V8.7)."""
        from ..investments import InvestmentSystem

        self.investments = InvestmentSystem(
            self, market, allocator=allocator, config=self.config
        )
        return self.investments

    # -- simulation --------------------------------------------------------
    def register(self, engine: SimulationEngine) -> None:
        """Attach to the simulation (V29.6, V29.11, V13.9-V13.11)."""
        engine.register(SimulationPhase.COMPANIES, self.update_daily)
        self.employees.register(engine)
        if self.investments is not None:
            self.investments.register(engine)
        engine.register_boundary(PeriodBoundary.WEEK, self.close_week)
        engine.register_boundary(PeriodBoundary.MONTH, self.close_month)
        engine.register_boundary(PeriodBoundary.YEAR, self.close_year)

    def update_daily(self, context: SimulationContext) -> None:
        """Update reputation and test for bankruptcy."""
        if self.bankrupt or self._last_daily_day == context.day_number:
            return
        self._drift_reputation()
        self._check_bankruptcy(context)
        self._last_daily_day = context.day_number

    def _drift_reputation(self) -> None:
        """Reputation follows sustained profitability (V3.8).

        It moves slowly and in small steps, so a single good week never buys
        standing in the industry — trust is earned over time.
        """
        drift = self.config.get_float("company.reputation_drift")
        profitable = self.finances.last_month.profit.is_positive
        target = 0.9 if profitable else 0.1
        self.reputation += (target - self.reputation) * drift
        self.reputation = max(0.0, min(1.0, self.reputation))

    def close_week(self, context: SimulationContext) -> None:
        """Weekly operating costs, loan repayments and profit (V13.9)."""
        if self.bankrupt:
            return
        base = self.config.get_int("company.weekly_operational_cost")
        per_level = self.config.get_int("company.operational_cost_per_level")
        running_cost = Money(base + per_level * (self.level - 1))
        self.finances.spend(
            context.day_number, ExpenseCategory.OPERATIONAL, running_cost,
            "Weekly running costs",
        )
        self.loans.process_weekly_repayments(self.finances, context.day_number)
        self.finances.close_week()

    def close_month(self, context: SimulationContext) -> None:
        """Monthly reporting (V13.10). Salaries are paid by the Employee System."""
        if self.bankrupt:
            return
        self.finances.close_month(context.day_number)

    def close_year(self, context: SimulationContext) -> None:
        """Yearly tax and reporting (V13.11)."""
        if self.bankrupt:
            return
        profit = self.finances.ledger.year.profit
        if profit.is_positive:
            rate = Percentage(str(self.config.get_float("tax.yearly_profit_rate")))
            tax = profit * rate
            self.finances.spend(
                context.day_number, ExpenseCategory.TAX, tax, "Annual profit tax"
            )
        self.finances.close_year()

    # -- bankruptcy (V3.14, V17.19) ----------------------------------------
    def _check_bankruptcy(self, context: SimulationContext) -> None:
        threshold = Money(self.config.get_int("company.bankruptcy_cash_threshold"))
        if self.finances.cash <= threshold:
            self.declare_bankruptcy(context.day_number)

    def declare_bankruptcy(self, day: int) -> None:
        """Wind the company up.

        The project manager's ruling (recorded in docs/design-decisions.md) is
        that employee training is cancelled and employees released, subsidiaries
        leave the group to become independent or be liquidated according to
        their condition, and investment funds — being separate financial
        entities — do not simply vanish. Those systems arrive in later
        milestones and react through the registered callbacks, so this module
        stays independent of them (V15.7).
        """
        if self.bankrupt:
            return
        self.bankrupt = True
        self.bankrupt_on_day = day
        logger.info(
            "%s has gone bankrupt on day %d with cash %s.",
            self.name, day, self.finances.cash.format(decimals=0),
        )
        for callback in list(self.on_bankruptcy):
            callback(self)

    # -- statistics (V3.13) ------------------------------------------------
    def statistics(self) -> dict[str, object]:
        return {
            "Company Value": self.value(),
            "Cash": self.finances.cash,
            "Net Worth": self.finances.net_worth(),
            "Weekly Profit": self.finances.last_week.profit,
            "Lifetime Profit": self.finances.lifetime_profit,
            "Reputation": Percentage(str(self.reputation)),
            "Company Level": self.level,
            "Employees": f"{len(self.employees)} of {self.employee_capacity}",
            "Debt": self.loans.total_outstanding(),
        }

    # -- persistence -------------------------------------------------------
    def state(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "founded_on_day": self.founded_on_day,
            "reputation": self.reputation,
            "level": self.level,
            "bankrupt": self.bankrupt,
            "bankrupt_on_day": self.bankrupt_on_day,
            "last_daily_day": self._last_daily_day,
            "finances": self.finances.state(),
            "loans": self.loans.state(),
            "employees": self.employees.state(),
            "investments": self.investments.state() if self.investments else {},
        }

    def restore(self, data: dict) -> None:
        self.id = data.get("id", self.id)
        self.name = data.get("name", self.name)
        self.founded_on_day = int(data.get("founded_on_day", self.founded_on_day))
        self.reputation = float(data.get("reputation", self.reputation))
        self.level = int(data.get("level", 1))
        self.bankrupt = bool(data.get("bankrupt", False))
        self.bankrupt_on_day = data.get("bankrupt_on_day")
        self._last_daily_day = data.get("last_daily_day")
        self.finances.restore(data.get("finances", {}))
        self.loans.restore(data.get("loans", {}))
        self.employees.restore(data.get("employees", {}))
        if self.investments is not None:
            self.investments.restore(data.get("investments", {}))
