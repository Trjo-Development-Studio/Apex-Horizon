"""Employees — Design Bible Volumes 5 and 18.

Employees should feel like intelligent colleagues rather than automated income
generators (V5.26): the player builds the organisation, and employees operate
it. Success comes from hiring the right people, assigning them well, training
them, and managing the company efficiently.
"""

from .employee import (
    ALL_DEPARTMENTS,
    Department,
    Employee,
    HiddenCharacteristics,
    InvestmentStyle,
    RiskTolerance,
    TimelineEntry,
    Training,
)
from .recruitment import generate_applicant, generate_applicants, salary_for, skill_ceiling_for_tier
from .roster import EmployeeRoster

__all__ = [
    "ALL_DEPARTMENTS",
    "Department",
    "Employee",
    "EmployeeRoster",
    "HiddenCharacteristics",
    "InvestmentStyle",
    "RiskTolerance",
    "TimelineEntry",
    "Training",
    "generate_applicant",
    "generate_applicants",
    "salary_for",
    "skill_ceiling_for_tier",
]
