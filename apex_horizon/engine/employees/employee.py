"""Employees.

Design Bible Volume 5 asks for people rather than income generators (V5.26):
each with their own strengths, weaknesses and long-term development. V5.19 is
explicit about why — without individually distinct employees, growing a company
would just be watching numbers rise rather than genuinely managing anyone.

Every employee has all three skills of V5.4 and works across all three
departments in a priority order they are assigned (V5.5). That is what lets one
generalist run a small company while specialisation still pays off later (V5.6).
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from enum import Enum

from ..config import Config, get_config
from ..values import Money, Percentage


class Department(Enum):
    """The only three departments an employee can be assigned to (V5.4, V18.6)."""

    RESEARCH = "Research"
    MANAGEMENT = "Management"
    INVESTMENT = "Investment"

    def __str__(self) -> str:
        return self.value


ALL_DEPARTMENTS: tuple[Department, ...] = tuple(Department)

# What an employee is doing right now, shown on their details page (V5.15).
TASK_BY_DEPARTMENT = {
    Department.RESEARCH: "Searching the market for opportunities",
    Department.MANAGEMENT: "Reviewing opportunities for approval",
    Department.INVESTMENT: "Managing the company's investments",
}


class RiskTolerance(Enum):
    CAUTIOUS = "Cautious"
    BALANCED = "Balanced"
    BOLD = "Bold"
    AGGRESSIVE = "Aggressive"

    def __str__(self) -> str:
        return self.value


class InvestmentStyle(Enum):
    VALUE = "Value"
    GROWTH = "Growth"
    MOMENTUM = "Momentum"
    CONTRARIAN = "Contrarian"

    def __str__(self) -> str:
        return self.value


@dataclass
class HiddenCharacteristics:
    """Tendencies the player cannot see at first (V5.7).

    V5.25 asks for these to be stored separately from visible statistics so that
    progression systems can reveal them selectively without restructuring
    employee data. They shape investment behaviour (V8.13) and evolve as an
    employee gains experience.
    """

    # Preferred size of an investment, as a share of the employee's limit.
    investment_size: float = 0.5
    risk_tolerance: RiskTolerance = RiskTolerance.BALANCED
    investment_style: InvestmentStyle = InvestmentStyle.VALUE
    # The industry this employee gravitates toward, or None for no preference.
    market_focus: str | None = None

    def describe(self) -> dict[str, str]:
        return {
            "Investment size": f"{self.investment_size * 100:.0f}% of limit",
            "Risk tolerance": str(self.risk_tolerance),
            "Investment style": str(self.investment_style),
            "Market focus": self.market_focus or "No preference",
        }


@dataclass
class TimelineEntry:
    """One thing that happened to an employee (V5.16).

    ``marker`` is deliberately restricted to plain ASCII. Decorative glyphs are
    absent from many system fonts and render as an empty box, which reads as a
    broken interface.
    """

    day: int
    text: str
    marker: str = "*"


@dataclass
class Training:
    """An employee's current course (V5.9).

    Training is measured entirely in days and continues across weeks and months:
    beginning on a Friday for ten days finishes the following Monday. Changing
    week never resets it (V13.12).
    """

    department: Department
    days_remaining: int
    total_days: int
    started_on_day: int

    @property
    def progress(self) -> float:
        done = self.total_days - self.days_remaining
        return done / self.total_days if self.total_days else 1.0


@dataclass
class Employee:
    """One member of the company's staff."""

    id: str
    name: str
    skills: dict[Department, int]
    primary: Department
    secondary: Department
    third: Department
    hidden: HiddenCharacteristics = field(default_factory=HiddenCharacteristics)
    happiness: float = 0.6
    salary: Money = field(default_factory=Money.zero)
    experience: dict[Department, float] = field(default_factory=dict)
    skill_ceiling: int = 40
    training: Training | None = None
    hired_on_day: int = 1
    # The most money this employee may commit to a single investment (V5.13).
    investment_limit: Money = field(default_factory=Money.zero)
    timeline: deque[TimelineEntry] = field(default_factory=lambda: deque(maxlen=40))
    # Counters shown by Employee Analytics (V9.10).
    research_completed: int = 0
    approvals: int = 0
    investments_made: int = 0

    # -- departments (V5.5) ------------------------------------------------
    @property
    def priorities(self) -> tuple[Department, Department, Department]:
        return (self.primary, self.secondary, self.third)

    def set_priorities(self, primary: Department, secondary: Department,
                       third: Department) -> None:
        """Assign all three departments, which must be the three of V5.4."""
        chosen = (primary, secondary, third)
        if set(chosen) != set(ALL_DEPARTMENTS):
            raise ValueError("An employee must be assigned each department exactly once")
        self.primary, self.secondary, self.third = chosen

    def priority_of(self, department: Department) -> int:
        """1 for primary, 2 for secondary, 3 for third."""
        return self.priorities.index(department) + 1

    def effectiveness_in(self, department: Department,
                         config: Config | None = None) -> float:
        """How well this employee performs in a department (V5.5, V5.10).

        Combines skill, the department's priority, and happiness — an unhappy
        employee still works, just less well, so pay and workload have a
        long-term performance cost rather than only a short-term saving (V5.24).
        """
        source = config or get_config()
        weights = (
            source.get_float("employees.primary_effectiveness"),
            source.get_float("employees.secondary_effectiveness"),
            source.get_float("employees.third_effectiveness"),
        )
        priority_weight = weights[self.priority_of(department) - 1]
        skill = self.skills.get(department, 1) / max(1, self.skill_ceiling)
        floor = source.get_float("employees.unhappy_effectiveness")
        mood = floor + (1.0 - floor) * max(0.0, min(1.0, self.happiness))
        if self.is_training:
            # An employee cannot do their job while training (V5.9).
            return 0.0
        return skill * priority_weight * mood

    # -- state -------------------------------------------------------------
    @property
    def is_training(self) -> bool:
        return self.training is not None and self.training.days_remaining > 0

    @property
    def current_task(self) -> str:
        """What this employee is doing now (V5.15)."""
        if self.is_training:
            return f"Training in {self.training.department} " \
                   f"({self.training.days_remaining} days left)"
        return TASK_BY_DEPARTMENT[self.primary]

    @property
    def overall_skill(self) -> int:
        """A single figure for sorting and comparing employees."""
        return round(sum(self.skills.values()) / len(self.skills))

    @property
    def happiness_percentage(self) -> Percentage:
        return Percentage(str(round(self.happiness, 4)))

    def expected_salary(self, config: Config | None = None) -> Money:
        """What this employee believes they are now worth (V5.10).

        Because it is derived from their *current* skills, an employee who has
        improved since being hired expects more than they are paid — which is
        what gives underpaying a strong employee the long-term performance cost
        V5.24 describes, rather than being a free saving.
        """
        from .recruitment import salary_for

        return salary_for(self.skills, config)

    def pay_fairness(self, config: Config | None = None) -> float:
        """Pay as a share of what the employee expects; 1.0 is the going rate."""
        expected = self.expected_salary(config)
        if expected.is_zero:
            return 1.0
        return float(self.salary / expected)

    def skill_in(self, department: Department) -> int:
        return self.skills.get(department, 1)

    # -- development (V5.8) ------------------------------------------------
    def gain_experience(self, department: Department, amount: float,
                        config: Config | None = None) -> bool:
        """Add experience, raising skill when enough accumulates.

        Returns whether the employee's skill improved, so the caller can record
        it on the timeline.
        """
        source = config or get_config()
        needed = source.get_float("employees.experience_per_skill_point")
        self.experience[department] = self.experience.get(department, 0.0) + amount
        improved = False
        while (
            self.experience[department] >= needed
            and self.skills.get(department, 1) < self.skill_ceiling
        ):
            self.experience[department] -= needed
            self.skills[department] = self.skills.get(department, 1) + 1
            improved = True
        return improved

    # -- timeline (V5.16) --------------------------------------------------
    def record(self, day: int, text: str, marker: str = "*") -> None:
        self.timeline.append(TimelineEntry(day, text, marker))

    def recent_timeline(self, day: int, days: int = 10) -> list[TimelineEntry]:
        """The previous ten in-game days of activity (V5.16)."""
        return [entry for entry in self.timeline if entry.day > day - days]

    # -- persistence -------------------------------------------------------
    def state(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "skills": {d.value: v for d, v in self.skills.items()},
            "primary": self.primary.value,
            "secondary": self.secondary.value,
            "third": self.third.value,
            "hidden": {
                "investment_size": self.hidden.investment_size,
                "risk_tolerance": self.hidden.risk_tolerance.name,
                "investment_style": self.hidden.investment_style.name,
                "market_focus": self.hidden.market_focus,
            },
            "happiness": self.happiness,
            "salary": str(self.salary.amount),
            "experience": {d.value: v for d, v in self.experience.items()},
            "skill_ceiling": self.skill_ceiling,
            "hired_on_day": self.hired_on_day,
            "investment_limit": str(self.investment_limit.amount),
            "training": None if self.training is None else {
                "department": self.training.department.value,
                "days_remaining": self.training.days_remaining,
                "total_days": self.training.total_days,
                "started_on_day": self.training.started_on_day,
            },
            "timeline": [
                {"day": e.day, "text": e.text, "marker": e.marker} for e in self.timeline
            ],
            "research_completed": self.research_completed,
            "approvals": self.approvals,
            "investments_made": self.investments_made,
        }

    @classmethod
    def from_state(cls, data: dict) -> Employee:
        departments = {d.value: d for d in Department}
        hidden = data.get("hidden", {})
        employee = cls(
            id=data["id"],
            name=data["name"],
            skills={departments[k]: int(v) for k, v in data["skills"].items()},
            primary=departments[data["primary"]],
            secondary=departments[data["secondary"]],
            third=departments[data["third"]],
            hidden=HiddenCharacteristics(
                investment_size=float(hidden.get("investment_size", 0.5)),
                risk_tolerance=RiskTolerance[hidden.get("risk_tolerance", "BALANCED")],
                investment_style=InvestmentStyle[hidden.get("investment_style", "VALUE")],
                market_focus=hidden.get("market_focus"),
            ),
            happiness=float(data.get("happiness", 0.6)),
            salary=Money(data.get("salary", "0")),
            experience={departments[k]: float(v)
                        for k, v in data.get("experience", {}).items()},
            skill_ceiling=int(data.get("skill_ceiling", 40)),
            hired_on_day=int(data.get("hired_on_day", 1)),
            investment_limit=Money(data.get("investment_limit", "0")),
            research_completed=int(data.get("research_completed", 0)),
            approvals=int(data.get("approvals", 0)),
            investments_made=int(data.get("investments_made", 0)),
        )
        training = data.get("training")
        if training:
            employee.training = Training(
                department=departments[training["department"]],
                days_remaining=int(training["days_remaining"]),
                total_days=int(training["total_days"]),
                started_on_day=int(training["started_on_day"]),
            )
        for entry in data.get("timeline", []):
            employee.timeline.append(
                TimelineEntry(int(entry["day"]), entry["text"],
                              entry.get("marker", entry.get("icon", "*")))
            )
        return employee
