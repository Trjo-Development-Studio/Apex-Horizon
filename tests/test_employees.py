"""Tests for the Employee System (Design Bible Volumes 5 and 18)."""

from __future__ import annotations

from random import Random

import pytest

from apex_horizon.engine.company import Player
from apex_horizon.engine.employees import (
    ALL_DEPARTMENTS,
    Department,
    EmployeeRoster,
    generate_applicants,
    salary_for,
    skill_ceiling_for_tier,
)
from apex_horizon.engine.simulation import SimulationClock, SimulationEngine
from apex_horizon.engine.unlocks import CREATE_COMPANY
from apex_horizon.engine.values import Calendar, IdAllocator, Money, set_calendar
from apex_horizon.engine.world import NameGenerator


@pytest.fixture(autouse=True)
def _calendar():
    set_calendar(Calendar(7, 4, 12))
    yield
    set_calendar(None)


def make_engine(seed: int = 1) -> SimulationEngine:
    clock = SimulationClock(seconds_per_day=1.0, speed=1, speed_options=(1,),
                            max_days_per_update=100_000)
    return SimulationEngine(clock=clock, seed=seed)


@pytest.fixture
def company():
    player = Player("Owner", cash=Money(400_000))
    player.unlocks.unlock(CREATE_COMPANY)
    company, _ = player.found_company("Test Capital", day=1)
    assert company is not None, "the builder must produce a company"
    # Training is opened by the Training branch (V6.7.4); these tests are about
    # what training does, not about earning it.
    company.employees.training_allowed = True
    return company


@pytest.fixture
def staffed(company):
    engine = make_engine()
    company.register(engine)
    roster = company.employees
    roster.refresh_applicants(Random(1), NameGenerator(Random(1)), IdAllocator(), 1)
    roster.hire(roster.applicants[0], 1)
    return company, roster, engine


# -- the three skills and departments (V5.4, V5.5, V18.6) -----------------


def test_there_are_exactly_three_departments():
    assert [str(d) for d in ALL_DEPARTMENTS] == ["Research", "Management", "Investment"]


def test_every_employee_has_all_three_skills(staffed):
    _, roster, _ = staffed
    employee = roster.employees[0]
    assert set(employee.skills) == set(ALL_DEPARTMENTS)
    assert set(employee.priorities) == set(ALL_DEPARTMENTS)


def test_departments_must_each_be_assigned_once(staffed):
    _, roster, _ = staffed
    employee = roster.employees[0]
    with pytest.raises(ValueError):
        employee.set_priorities(Department.RESEARCH, Department.RESEARCH,
                                Department.INVESTMENT)


def test_effectiveness_falls_with_priority(staffed):
    _, roster, _ = staffed
    employee = roster.employees[0]
    employee.skills = dict.fromkeys(ALL_DEPARTMENTS, 20)
    employee.set_priorities(Department.RESEARCH, Department.MANAGEMENT,
                            Department.INVESTMENT)
    first = employee.effectiveness_in(Department.RESEARCH)
    second = employee.effectiveness_in(Department.MANAGEMENT)
    third = employee.effectiveness_in(Department.INVESTMENT)
    assert first > second > third > 0


def test_a_single_generalist_can_cover_every_department(staffed):
    # V5.6: a small company runs on one person doing several jobs.
    _, roster, _ = staffed
    employee = roster.employees[0]
    employee.happiness = 0.8
    assert all(employee.effectiveness_in(d) > 0 for d in ALL_DEPARTMENTS)
    assert roster.research_output > 0
    assert roster.management_output > 0
    assert roster.investment_output > 0


def test_reassignment_swaps_rather_than_duplicating(staffed):
    _, roster, _ = staffed
    employee = roster.employees[0]
    roster.assign_departments(employee, Department.INVESTMENT, Department.RESEARCH,
                              Department.MANAGEMENT, day=2)
    assert employee.primary is Department.INVESTMENT
    assert set(employee.priorities) == set(ALL_DEPARTMENTS)


# -- recruitment (V5.3, V6.7.2) -------------------------------------------


def test_skill_ceilings_follow_the_unlock_tiers():
    # V6.7.2 gives 1-20, 1-30 and 1-40 for the three Better Employees levels.
    assert skill_ceiling_for_tier(1) == 20
    assert skill_ceiling_for_tier(2) == 30
    assert skill_ceiling_for_tier(3) == 40
    assert skill_ceiling_for_tier(99) == 40


def test_applicants_never_exceed_their_tier_ceiling():
    applicants = generate_applicants(Random(2), NameGenerator(Random(2)), IdAllocator(),
                                     count=40, tier=1)
    assert all(max(a.skills.values()) <= 20 for a in applicants)


def test_reputation_improves_candidate_quality_on_average():
    def average(reputation: float) -> float:
        applicants = generate_applicants(
            Random(7), NameGenerator(Random(7)), IdAllocator(),
            count=120, tier=3, reputation=reputation,
        )
        return sum(a.overall_skill for a in applicants) / len(applicants)

    assert average(0.95) > average(0.05)


def test_applicants_arrive_leaning_toward_their_best_skill():
    applicants = generate_applicants(Random(3), NameGenerator(Random(3)), IdAllocator(),
                                     count=20, tier=2)
    for applicant in applicants:
        assert applicant.skills[applicant.primary] >= applicant.skills[applicant.third]


def test_better_employees_cost_more():
    weak = salary_for(dict.fromkeys(ALL_DEPARTMENTS, 3))
    strong = salary_for(dict.fromkeys(ALL_DEPARTMENTS, 30))
    assert strong > weak


# -- hiring and capacity (V5.17, V18.29) ----------------------------------


def test_hiring_adds_to_the_roster(staffed):
    _, roster, _ = staffed
    assert len(roster) == 1
    assert roster.employees[0].timeline


def test_a_full_company_cannot_hire(company):
    roster = company.employees
    roster.refresh_applicants(Random(4), NameGenerator(Random(4)), IdAllocator(), 1)
    names = NameGenerator(Random(9))
    allocator = IdAllocator()
    for _ in range(company.employee_capacity):
        applicant = generate_applicants(Random(5), names, allocator, count=1)[0]
        assert roster.hire(applicant, 1)[0]
    assert roster.is_full
    extra = generate_applicants(Random(6), names, allocator, count=1)[0]
    ok, message = roster.hire(extra, 1)
    assert not ok
    assert "Company Level" in message


def test_capacity_follows_company_level(company):
    assert company.employees.capacity == 10
    company.set_level(3)
    assert company.employees.capacity == 50


def test_employees_can_be_dismissed(staffed):
    _, roster, _ = staffed
    employee = roster.employees[0]
    assert roster.fire(employee)[0]
    assert len(roster) == 0
    assert roster.fire(employee)[0] is False


# -- training (V5.9, V13.12) ----------------------------------------------


def test_training_is_measured_in_days_and_crosses_weeks(staffed):
    _, roster, engine = staffed
    employee = roster.employees[0]
    ok, _ = roster.start_training(employee, Department.RESEARCH, day=1, days=10)
    assert ok
    assert employee.is_training
    engine.run_days(9)
    assert employee.is_training  # a week boundary has passed without resetting
    engine.run_days(1)
    assert not employee.is_training
    assert any("Completed" in e.text for e in employee.timeline)


def test_an_employee_cannot_work_while_training(staffed):
    _, roster, _ = staffed
    employee = roster.employees[0]
    roster.start_training(employee, Department.RESEARCH, day=1)
    assert employee.effectiveness_in(Department.RESEARCH) == 0
    assert roster.research_output == 0
    assert roster.can_operate is False


def test_training_raises_skill(staffed):
    _, roster, engine = staffed
    employee = roster.employees[0]
    before = employee.skill_in(Department.MANAGEMENT)
    for _ in range(6):
        roster.start_training(employee, Department.MANAGEMENT, engine.date.day, days=10)
        engine.run_days(11)
    assert employee.skill_in(Department.MANAGEMENT) > before


def test_an_employee_cannot_train_twice_at_once(staffed):
    _, roster, _ = staffed
    employee = roster.employees[0]
    roster.start_training(employee, Department.RESEARCH, 1)
    ok, message = roster.start_training(employee, Department.INVESTMENT, 1)
    assert not ok and "already training" in message


# -- development, pay and morale (V5.8, V5.10, V5.11, V5.24) --------------


def test_experience_raises_skill_over_time(staffed):
    _, roster, engine = staffed
    employee = roster.employees[0]
    before = dict(employee.skills)
    engine.run_days(336)
    assert sum(employee.skills.values()) > sum(before.values())


def test_skill_never_passes_the_ceiling(staffed):
    _, roster, engine = staffed
    employee = roster.employees[0]
    employee.skill_ceiling = 12
    employee.skills = dict.fromkeys(ALL_DEPARTMENTS, 12)
    engine.run_days(336)
    assert all(value <= 12 for value in employee.skills.values())


def test_salaries_are_paid_monthly(staffed):
    company, roster, engine = staffed
    engine.run_days(30)
    assert "Salaries" in company.finances.ledger.by_category
    assert company.finances.ledger.by_category["Salaries"] == roster.monthly_salary_bill()


def test_no_salaries_are_paid_without_staff(company):
    engine = make_engine()
    company.register(engine)
    engine.run_days(60)
    assert "Salaries" not in company.finances.ledger.by_category


def test_an_underpaid_employee_becomes_unhappy(staffed):
    # V5.24: underpaying a strong employee costs performance over time.
    _, roster, engine = staffed
    employee = roster.employees[0]
    roster.set_salary(employee, employee.salary * 0.3, 1)
    before = employee.happiness
    engine.run_days(280)
    assert employee.happiness < before
    assert employee.pay_fairness() < 1


def test_paying_the_market_rate_restores_morale(staffed):
    _, roster, engine = staffed
    employee = roster.employees[0]
    roster.set_salary(employee, employee.salary * 0.3, 1)
    engine.run_days(280)
    unhappy = employee.happiness
    roster.set_salary(employee, employee.expected_salary(), engine.date.day)
    engine.run_days(280)
    assert employee.happiness > unhappy


def test_unhappiness_reduces_effectiveness_without_stopping_work(staffed):
    _, roster, _ = staffed
    employee = roster.employees[0]
    employee.happiness = 1.0
    happy = employee.effectiveness_in(employee.primary)
    employee.happiness = 0.0
    miserable = employee.effectiveness_in(employee.primary)
    assert 0 < miserable < happy


def test_a_raise_is_recorded_on_the_timeline(staffed):
    _, roster, _ = staffed
    employee = roster.employees[0]
    roster.set_salary(employee, employee.salary * 2, 5)
    assert any("Pay raised" in e.text for e in employee.timeline)
    assert roster.set_salary(employee, Money(-1), 5)[0] is False


# -- the timeline (V5.16) --------------------------------------------------


def test_the_timeline_covers_the_last_ten_days(staffed):
    _, roster, engine = staffed
    employee = roster.employees[0]
    employee.record(1, "Long ago")
    engine.run_days(40)
    employee.record(engine.date.day, "Just now")
    recent = employee.recent_timeline(engine.date.day)
    assert any(e.text == "Just now" for e in recent)
    assert not any(e.text == "Long ago" for e in recent)


def test_hidden_characteristics_exist_and_describe_themselves(staffed):
    _, roster, _ = staffed
    employee = roster.employees[0]
    described = employee.hidden.describe()
    for key in ("Investment size", "Risk tolerance", "Investment style", "Market focus"):
        assert key in described
    # V5.7: not shown until the Recruitment branch reveals them.
    assert roster.strengths_visible is False


# -- bankruptcy (project manager ruling) -----------------------------------


def test_bankruptcy_releases_staff_and_cancels_training(staffed):
    company, roster, _ = staffed
    employee = roster.employees[0]
    roster.start_training(employee, Department.RESEARCH, 1)
    company.declare_bankruptcy(day=20)
    assert len(roster) == 0
    assert employee.training is None
    assert any("Company closed" in e.text for e in employee.timeline)


def test_a_bankrupt_company_cannot_hire(staffed):
    """Bug fix, 2026-08-09: the game-state check itself, not just the UI.

    Matches the refusal ``SubsidiaryBook.can_acquire`` and ``FundBook.can_create``
    already give a bankrupt company, rather than letting a dead company still
    grow its (soon to be immediately released) staff.
    """
    company, roster, _ = staffed
    company.declare_bankruptcy(day=20)
    applicant = generate_applicants(Random(9), NameGenerator(Random(9)),
                                    IdAllocator(), count=1)[0]

    ok, message = roster.hire(applicant, 21)

    assert not ok
    assert "bankrupt" in message.lower()
    assert len(roster) == 0


# -- statistics and persistence -------------------------------------------


def test_roster_statistics_cover_the_workforce(staffed):
    _, roster, _ = staffed
    stats = roster.statistics()
    for key in ("Employees", "Average skill", "Average happiness", "In training",
                "Monthly salaries"):
        assert key in stats


def test_an_empty_roster_still_reports(company):
    assert company.employees.statistics()["Employees"] == "0 of 10"


def test_the_roster_survives_a_save(staffed):
    company, roster, engine = staffed
    employee = roster.employees[0]
    roster.start_training(employee, Department.INVESTMENT, engine.date.day)
    engine.run_days(60)

    restored = EmployeeRoster(company)
    restored.restore(roster.state())
    other = restored.employees[0]
    assert other.name == employee.name
    assert other.skills == employee.skills
    assert other.priorities == employee.priorities
    assert other.happiness == pytest.approx(employee.happiness)
    assert other.salary == employee.salary
    assert other.hidden.risk_tolerance is employee.hidden.risk_tolerance
    assert len(other.timeline) == len(employee.timeline)


def test_employees_are_retry_safe(staffed):
    _, roster, engine = staffed
    engine.run_days(5)
    employee = roster.employees[0]
    experience = dict(employee.experience)
    from apex_horizon.engine.simulation import SimulationContext

    context = SimulationContext(date=engine.date - 1, rng=engine.rng,
                                day_number=engine.date.day - 1, tick=0)
    roster.work_day(context)
    assert employee.experience == experience
