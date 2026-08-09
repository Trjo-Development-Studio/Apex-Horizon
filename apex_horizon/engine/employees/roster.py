"""The company's staff.

Design Bible V5.2 makes employees belong to the company rather than the player,
and V5.12 has them working continuously throughout every day rather than in
weekly batches. They run during the Employees phase, which V29.7 places fifth in
the day — after companies have settled, and before Research reads what they
produced.

What employees actually *do* with their working day is the Investment Workflow
of Volume 8. This module owns the people: their development, training,
happiness, pay and history. It exposes each department's daily output so the
Investment System can consume it without either system knowing the other's
internals (V15.7).
"""

from __future__ import annotations

from collections.abc import Iterator
from random import Random
from typing import Any

from ..config import Config, get_config
from ..logging_setup import get_logger
from ..simulation import PeriodBoundary, SimulationContext, SimulationEngine, SimulationPhase
from ..values import IdAllocator, Money
from ..world import NameGenerator
from .employee import ALL_DEPARTMENTS, Department, Employee, Training
from .recruitment import generate_applicants, skill_ceiling_for_tier

logger = get_logger(__name__)


class EmployeeRoster:
    """Everyone who works for the player's company."""

    def __init__(self, company, *, config: Config | None = None):
        self.config = config or get_config()
        self.company = company
        self.employees: list[Employee] = []
        self.applicants: list[Employee] = []
        #: Raised by the Better Employees unlocks of V6.7.2 (Unlock Tree, later).
        self.recruitment_tier: int = 0
        #: Whether hidden characteristics are visible (Recruitment branch, V6.7.5).
        self.strengths_visible: bool = False
        #: Whether performance statistics are shown (Recruitment branch, V6.7.5).
        self.performance_visible: bool = False
        #: Training is gated behind its own unlock (V6.7.4); hiring is not.
        self.training_allowed: bool = False
        #: How much faster training teaches, raised by the Training branch.
        self.training_speed: float = 1.0
        #: How strongly this employer's staff lean toward risk. Zero for the
        #: player; AI companies skew higher (V26.4).
        self.risk_bias: float = 0.0
        #: Applicants offered, and how strongly reputation shapes their quality,
        #: both raised by the Recruitment branch (V6.7.5).
        self.applicant_pool: int = self.config.get_int("employees.applicant_pool_size")
        self.reputation_weight: float = self.config.get_float(
            "employees.reputation_quality_weight"
        )
        self._last_worked_day: int | None = None
        #: Called with each person taken on, so anything that wants to count
        #: hires can, without this module knowing what it is (V15.7).
        self.on_hire: list = []

    # -- the roster --------------------------------------------------------
    def __len__(self) -> int:
        return len(self.employees)

    def __iter__(self) -> Iterator[Employee]:
        return iter(self.employees)

    @property
    def capacity(self) -> int:
        """Maximum staff at the company's current level (V5.17, V18.5)."""
        return self.company.employee_capacity

    @property
    def is_full(self) -> bool:
        return len(self.employees) >= self.capacity

    def by_id(self, employee_id: str) -> Employee | None:
        return next((e for e in self.employees if e.id == employee_id), None)

    def in_department(self, department: Department) -> list[Employee]:
        """Everyone whose primary department is this one."""
        return [e for e in self.employees if e.primary is department]

    # -- hiring and firing (V5.3) -----------------------------------------
    def refresh_applicants(self, rng: Random, names: NameGenerator,
                           allocator: IdAllocator, day: int) -> list[Employee]:
        """Draw a new pool of candidates, shaped by company reputation."""
        self.applicants = generate_applicants(
            rng, names, allocator,
            count=self.applicant_pool,
            tier=self.recruitment_tier,
            reputation=self.company.reputation,
            reputation_weight=self.reputation_weight,
            risk_bias=self.risk_bias,
            day=day,
            config=self.config,
        )
        return self.applicants

    def hire(self, applicant: Employee, day: int) -> tuple[bool, str]:
        """Take on an applicant, if there is room for them (V5.17).

        A company at capacity cannot hire even an excellent candidate; V18.29
        asks for that limit to be made clear rather than surfacing as a
        confusing failure.

        This is the state check itself, not just what the UI happens to show:
        the Employees page already stops offering candidates once the company
        is bankrupt, but the game must refuse the hire here too, the same way
        :meth:`~apex_horizon.engine.acquisitions.subsidiaries.SubsidiaryBook.can_acquire`
        and :meth:`~apex_horizon.engine.funds.book.FundBook.can_create` already
        refuse their own actions for a bankrupt company.
        """
        if self.company.bankrupt:
            return False, "A bankrupt company cannot hire anyone."
        if self.is_full:
            return False, (
                f"Your company can hold {self.capacity} employees. "
                "Raise your Company Level to hire more."
            )
        if any(e.id == applicant.id for e in self.employees):
            return False, "That person already works here."

        applicant.hired_on_day = day
        applicant.skill_ceiling = skill_ceiling_for_tier(self.recruitment_tier, self.config)
        self.employees.append(applicant)
        self.applicants = [a for a in self.applicants if a.id != applicant.id]
        applicant.record(day, f"Joined the company as {applicant.primary}", "+")
        logger.info("%s hired %s.", self.company.name, applicant.name)
        for callback in list(self.on_hire):
            callback(applicant)
        return True, f"{applicant.name} joined the company."

    def fire(self, employee: Employee) -> tuple[bool, str]:
        if employee not in self.employees:
            return False, "That person does not work here."
        self.employees.remove(employee)
        logger.info("%s left %s.", employee.name, self.company.name)
        return True, f"{employee.name} has left the company."

    def release_all(self, day: int) -> None:
        """Let everyone go, cancelling any training (bankruptcy).

        The project manager's ruling: on bankruptcy training is cancelled and
        employees return to their normal state, free to be hired elsewhere.
        """
        for employee in self.employees:
            employee.training = None
            employee.record(day, "Company closed; contract ended", "!")
        logger.info("%s released %d employees.", self.company.name, len(self.employees))
        self.employees.clear()

    # -- assignments and limits -------------------------------------------
    def assign_departments(self, employee: Employee, primary: Department,
                           secondary: Department, third: Department, day: int) -> None:
        """Set an employee's three department priorities (V5.5, V18.6)."""
        if employee.priorities == (primary, secondary, third):
            return
        employee.set_priorities(primary, secondary, third)
        employee.record(day, f"Reassigned to {primary} as primary", ">")

    def set_salary(self, employee: Employee, salary: Money, day: int) -> tuple[bool, str]:
        """Change what an employee is paid (V5.11).

        Raising pay toward what they now expect restores morale over the
        following weeks; cutting it below has the opposite effect.
        """
        if salary.is_negative:
            return False, "A salary cannot be negative."
        previous = employee.salary
        employee.salary = salary
        if salary > previous:
            employee.record(day, f"Pay raised to {salary.format(decimals=0)} a month", "+")
            return True, f"{employee.name} received a raise."
        if salary < previous:
            employee.record(day, f"Pay cut to {salary.format(decimals=0)} a month", "-")
            return True, f"{employee.name}'s pay was reduced."
        return True, "Salary unchanged."

    def set_investment_limit(self, employee: Employee, limit: Money) -> None:
        """Cap what this employee may commit (V5.13, V8.8, V18.13)."""
        employee.investment_limit = limit

    # -- training (V5.9) ---------------------------------------------------
    def start_training(self, employee: Employee, department: Department, day: int,
                       days: int | None = None) -> tuple[bool, str]:
        """Send an employee on a course measured in days, not weeks."""
        if not self.training_allowed:
            # V6.7.4: training is earned through the Unlock Tree.
            return False, (
                "Employee Training has not been unlocked yet."
            )
        if employee.is_training:
            return False, f"{employee.name} is already training."
        length = days or self.config.get_int("employees.training_default_days")
        employee.training = Training(department, length, length, day)
        employee.record(day, f"Started {length} days of {department} training", "~")
        return True, f"{employee.name} began training in {department}."

    def _advance_training(self, employee: Employee, context: SimulationContext) -> None:
        training = employee.training
        if training is None or training.days_remaining <= 0:
            return
        training.days_remaining -= 1
        employee.gain_experience(
            training.department,
            self.config.get_float("employees.training_experience_per_day")
            * self.training_speed,
            self.config,
        )
        if training.days_remaining <= 0:
            employee.training = None
            employee.record(context.day_number,
                            f"Completed {training.department} training", "+")
            logger.info("%s finished training.", employee.name)

    # -- the working day (V5.12) ------------------------------------------
    def register(self, engine: SimulationEngine) -> None:
        """Attach to the simulation (V29.7, V13.10)."""
        engine.register(SimulationPhase.EMPLOYEES, self.work_day)
        engine.register_boundary(PeriodBoundary.MONTH, self.pay_salaries)
        engine.register_boundary(PeriodBoundary.WEEK, self.update_happiness)

    def work_day(self, context: SimulationContext) -> None:
        """Advance training and let everyone work for a day."""
        if self._last_worked_day == context.day_number:
            return  # a retried phase must not work the same day twice (V15.26)

        gain = self.config.get_float("employees.experience_per_day")
        for employee in self.employees:
            if employee.is_training:
                self._advance_training(employee, context)
                continue
            # Experience accrues where the work is actually done, weighted by
            # how much of the day each department gets (V5.8).
            for department in ALL_DEPARTMENTS:
                share = employee.effectiveness_in(department, self.config)
                if share <= 0:
                    continue
                if employee.gain_experience(department, gain * share, self.config):
                    employee.record(
                        context.day_number,
                        f"{department} skill improved to {employee.skill_in(department)}",
                        "+",
                    )
        self._last_worked_day = context.day_number

    # -- department output, consumed by the Investment System --------------
    def output(self, department: Department) -> float:
        """Total effective capacity in a department today (V5.5)."""
        return sum(e.effectiveness_in(department, self.config) for e in self.employees)

    @property
    def research_output(self) -> float:
        return self.output(Department.RESEARCH)

    @property
    def management_output(self) -> float:
        return self.output(Department.MANAGEMENT)

    @property
    def investment_output(self) -> float:
        return self.output(Department.INVESTMENT)

    @property
    def can_operate(self) -> bool:
        """Whether the company can run the investment loop at all (V2.18).

        A company with no employees can still hold what it owns, but cannot
        discover, approve or execute anything.
        """
        return any(not e.is_training for e in self.employees)

    # -- pay and morale ----------------------------------------------------
    def monthly_salary_bill(self) -> Money:
        total = Money.zero()
        for employee in self.employees:
            total = total + employee.salary
        return total

    def pay_salaries(self, context: SimulationContext) -> None:
        """Pay everyone, monthly (V5.11, V13.10, V17.7)."""
        from ..company.ledger import ExpenseCategory

        if not self.employees or self.company.bankrupt:
            return
        bill = self.monthly_salary_bill()
        # Salaries are paid even when they push cash negative: falling behind is
        # how poor management leads toward bankruptcy (V17.19).
        self.company.finances.spend(
            context.day_number, ExpenseCategory.SALARIES, bill,
            f"Salaries for {len(self.employees)} employees",
        )

    def update_happiness(self, context: SimulationContext) -> None:
        """Move morale toward what pay, workload and success justify (V5.10)."""
        if not self.employees:
            return
        drift = self.config.get_float("employees.happiness_drift")
        profitable = self.company.finances.last_month.profit.is_positive
        # Workload: a company running close to capacity stretches its people.
        load = len(self.employees) / max(1, self.capacity)

        for employee in self.employees:
            # Pay measured against what the employee now believes they are
            # worth. An employee who has grown since being hired expects more,
            # so leaving them on their starting salary slowly costs performance
            # rather than saving money for free (V5.24).
            fairness = employee.pay_fairness(self.config)
            target = 0.35 + 0.35 * max(0.0, min(1.5, fairness)) / 1.5
            target += 0.15 if profitable else -0.12
            # A company running close to capacity stretches its people.
            target -= 0.20 * max(0.0, load - 0.85)
            if employee.is_training:
                target += 0.05  # people value being invested in
            target = max(0.0, min(1.0, target))
            employee.happiness += (target - employee.happiness) * drift
            employee.happiness = max(0.0, min(1.0, employee.happiness))

    # -- statistics (V9.10, V28.3) ----------------------------------------
    def statistics(self) -> dict[str, Any]:
        if not self.employees:
            return {"Employees": f"0 of {self.capacity}"}
        average = sum(e.overall_skill for e in self.employees) / len(self.employees)
        happiness = sum(e.happiness for e in self.employees) / len(self.employees)
        return {
            "Employees": f"{len(self.employees)} of {self.capacity}",
            "Average skill": f"{average:.1f}",
            "Average happiness": f"{happiness * 100:.0f}%",
            "In training": str(sum(1 for e in self.employees if e.is_training)),
            "Monthly salaries": self.monthly_salary_bill(),
        }

    # -- persistence -------------------------------------------------------
    def state(self) -> dict:
        return {
            "employees": [e.state() for e in self.employees],
            "applicants": [a.state() for a in self.applicants],
            "recruitment_tier": self.recruitment_tier,
            "strengths_visible": self.strengths_visible,
            "last_worked_day": self._last_worked_day,
        }

    def restore(self, data: dict) -> None:
        self.employees = [Employee.from_state(e) for e in data.get("employees", [])]
        self.applicants = [Employee.from_state(a) for a in data.get("applicants", [])]
        self.recruitment_tier = int(data.get("recruitment_tier", 0))
        self.strengths_visible = bool(data.get("strengths_visible", False))
        self._last_worked_day = data.get("last_worked_day")
