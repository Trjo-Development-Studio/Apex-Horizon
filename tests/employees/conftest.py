"""Fixtures for the Employee System tests (Design Bible Volumes 5 and 18)."""

from __future__ import annotations

from random import Random

import pytest
from employees_support import make_engine

from apex_horizon.engine.company import Player
from apex_horizon.engine.unlocks import CREATE_COMPANY
from apex_horizon.engine.values import Calendar, IdAllocator, Money, set_calendar
from apex_horizon.engine.world import NameGenerator


@pytest.fixture(autouse=True)
def _calendar():
    set_calendar(Calendar(7, 4, 12))
    yield
    set_calendar(None)


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
