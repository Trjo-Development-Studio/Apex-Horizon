"""Tests for recruitment pacing, automation, and roster persistence."""

from __future__ import annotations

from random import Random

import pytest
from employees_support import make_engine

from apex_horizon.engine.employees import (
    Department,
    EmployeeRoster,
)
from apex_horizon.engine.values import IdAllocator
from apex_horizon.engine.world import NameGenerator

# -- recruitment pacing and automation (QoL pass, 2026-08-10) -------------
#
# Applicants are not instant (V5.26: co-workers, not a vending machine).
# request_applicants schedules check_recruitment, a registered daily phase
# handler, to draw the pool later via the unchanged refresh_applicants —
# and, once Automated Recruitment is unlocked and switched on, to hire
# through the unchanged hire() and re-arm itself, never a parallel path.


def test_request_applicants_schedules_a_delayed_arrival(company):
    roster = company.employees
    roster.request_applicants(10)
    delay = roster.config.get_int("employees.recruitment_delay_days")
    assert roster.pending_applicants_day == 10 + delay
    assert roster.applicants == []  # nothing drawn yet


def test_applicants_arrive_after_the_configured_delay(company):
    roster = company.employees
    roster.attach_recruitment_sources(NameGenerator(Random(2)), IdAllocator())
    engine = make_engine()
    company.register(engine)
    roster.request_applicants(engine.date.day)
    delay = roster.config.get_int("employees.recruitment_delay_days")

    engine.run_days(delay - 1)
    assert roster.pending_applicants_day is not None
    assert roster.applicants == []

    engine.run_days(2)  # crosses the arrival day
    assert roster.pending_applicants_day is None
    assert roster.applicants, "the pool should have arrived"


def test_an_existing_pool_stays_hireable_while_a_new_one_is_pending(staffed):
    _, roster, engine = staffed
    # staffed already hired one applicant from its own, separate IdAllocator,
    # which also starts counting from 1 - so this one must be advanced past
    # that number first, or the new pool would collide on id with the
    # employee already on the roster (both allocators start fresh).
    from apex_horizon.engine.values import EntityKind

    allocator = IdAllocator()
    allocator.next_id(EntityKind.EMPLOYEE)
    roster.attach_recruitment_sources(NameGenerator(Random(3)), allocator)
    roster.refresh_applicants(Random(3), NameGenerator(Random(3)), allocator, engine.date.day)
    waiting = list(roster.applicants)
    assert waiting

    roster.request_applicants(engine.date.day)
    assert roster.applicants == waiting
    ok, _ = roster.hire(waiting[0], engine.date.day)
    assert ok, "a candidate offered before the request must stay hireable"


def test_recruitment_pacing_survives_a_save_mid_wait(company):
    roster = company.employees
    roster.request_applicants(5)

    restored = EmployeeRoster(company)
    restored.restore(roster.state())
    assert restored.pending_applicants_day == roster.pending_applicants_day


def test_automation_refuses_when_not_unlocked(company):
    roster = company.employees
    assert roster.automation_allowed is False
    ok, message = roster.set_automation(True, 5, 1)
    assert not ok
    assert "unlock" in message.lower()
    assert roster.auto_recruit_enabled is False


def test_automation_hires_up_to_the_threshold_and_rearms(company):
    roster = company.employees
    roster.automation_allowed = True
    roster.attach_recruitment_sources(NameGenerator(Random(4)), IdAllocator())
    engine = make_engine(seed=4)
    company.register(engine)

    ok, _ = roster.set_automation(True, minimum_skill=1, day=engine.date.day)
    assert ok
    delay = roster.config.get_int("employees.recruitment_delay_days")
    engine.run_days(delay + 1)

    assert len(roster) > 0, "automation should have hired someone through hire()"
    # It keeps going: another request should already be scheduled.
    assert roster.pending_applicants_day is not None


def test_automation_never_hires_below_the_threshold(company):
    roster = company.employees
    roster.automation_allowed = True
    roster.attach_recruitment_sources(NameGenerator(Random(5)), IdAllocator())
    engine = make_engine(seed=5)
    company.register(engine)

    roster.set_automation(True, minimum_skill=999, day=engine.date.day)
    delay = roster.config.get_int("employees.recruitment_delay_days")
    engine.run_days(delay + 1)

    assert len(roster) == 0, "no applicant can meet an impossible bar"
    assert roster.applicants, "the pool still arrived, just unhired"


def test_manual_hiring_keeps_working_with_automation_on(company):
    """The hard requirement: automation is a second caller, not a
    replacement — a human Hire click must still work exactly as before."""
    roster = company.employees
    roster.automation_allowed = True
    roster.auto_recruit_enabled = True
    roster.refresh_applicants(Random(6), NameGenerator(Random(6)), IdAllocator(), 1)
    ok, _ = roster.hire(roster.applicants[0], 1)
    assert ok


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
