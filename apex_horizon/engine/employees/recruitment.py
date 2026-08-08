"""Recruitment.

Design Bible V5.3 makes the applicants available depend on company reputation,
recruitment upgrades and company progression — so a stronger, better-regarded
company attracts better people. V18.14 adds that unlocks provide better
applicants, larger pools, and eventually visible strengths and performance.

Applicant names come from the same population as everyone else in the world
(V33.6), so a hire is a person from the Alternative Earth rather than a
generated string.
"""

from __future__ import annotations

from random import Random

from ..config import Config, get_config
from ..values import EntityKind, IdAllocator, Money
from ..world import Industry, NameGenerator
from .employee import (
    ALL_DEPARTMENTS,
    Department,
    Employee,
    HiddenCharacteristics,
    InvestmentStyle,
    RiskTolerance,
)


def skill_ceiling_for_tier(tier: int, config: Config | None = None) -> int:
    """The best skill an applicant can have at a given Better Employees tier.

    V6.7.2 gives ranges of 1-20, 1-30 and 1-40 for the three unlock levels;
    tier 0 is a company that has not yet unlocked any of them.
    """
    source = config or get_config()
    caps = source.get_list("employees.skill_cap_by_tier")
    return int(caps[max(0, min(tier, len(caps) - 1))])


def salary_for(skills: dict[Department, int], config: Config | None = None) -> Money:
    """What an employee of this quality expects to be paid (V5.11)."""
    source = config or get_config()
    base = source.get_int("employees.salary_base")
    per_point = source.get_int("employees.salary_per_skill_point")
    total_skill = sum(skills.values())
    return Money(base + per_point * total_skill)


def generate_applicant(
    rng: Random,
    names: NameGenerator,
    allocator: IdAllocator,
    *,
    tier: int = 0,
    reputation: float = 0.25,
    reputation_weight: float | None = None,
    day: int = 1,
    config: Config | None = None,
) -> Employee:
    """Create one applicant (V5.3).

    Reputation shifts the *distribution* rather than guaranteeing quality: a
    well-regarded company sees better candidates on average, but a poor one can
    still occasionally meet someone excellent, and a strong one someone weak.
    """
    source = config or get_config()
    ceiling = skill_ceiling_for_tier(tier, source)
    minimum = source.get_int("employees.skill_minimum")
    # Better Recruitment raises how much a good reputation counts (V6.7.5).
    weight = (
        reputation_weight if reputation_weight is not None
        else source.get_float("employees.reputation_quality_weight")
    )

    def roll() -> int:
        # Two rolls biased by reputation, taking the better of them: reputation
        # improves the odds without removing the spread.
        first = rng.randint(minimum, ceiling)
        second = rng.randint(minimum, ceiling)
        if rng.random() < reputation * weight:
            return max(first, second)
        return min(first, second) if rng.random() < 0.35 else first

    skills = {department: roll() for department in ALL_DEPARTMENTS}
    priorities = list(ALL_DEPARTMENTS)
    # An applicant arrives already leaning toward what they are best at.
    priorities.sort(key=lambda d: skills[d], reverse=True)

    hidden = HiddenCharacteristics(
        investment_size=round(rng.uniform(0.15, 0.9), 3),
        risk_tolerance=rng.choice(list(RiskTolerance)),
        investment_style=rng.choice(list(InvestmentStyle)),
        market_focus=rng.choice(list(Industry)).value if rng.random() < 0.4 else None,
    )

    employee = Employee(
        id=allocator.next_id(EntityKind.EMPLOYEE),
        name=names.person_name(),
        skills=skills,
        primary=priorities[0],
        secondary=priorities[1],
        third=priorities[2],
        hidden=hidden,
        happiness=source.get_float("employees.starting_happiness"),
        salary=salary_for(skills, source),
        skill_ceiling=ceiling,
        hired_on_day=day,
    )
    return employee


def generate_applicants(
    rng: Random,
    names: NameGenerator,
    allocator: IdAllocator,
    *,
    count: int | None = None,
    tier: int = 0,
    reputation: float = 0.25,
    reputation_weight: float | None = None,
    day: int = 1,
    config: Config | None = None,
) -> list[Employee]:
    """A pool of candidates to choose between (V5.3, V18.14)."""
    source = config or get_config()
    size = count if count is not None else source.get_int("employees.applicant_pool_size")
    return [
        generate_applicant(rng, names, allocator, tier=tier, reputation=reputation,
                           reputation_weight=reputation_weight, day=day, config=source)
        for _ in range(size)
    ]
