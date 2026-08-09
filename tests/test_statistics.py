"""Tests for lifetime statistics (Design Bible V28)."""

from __future__ import annotations

import pytest

from apex_horizon.engine.statistics import LifetimeStatistics
from apex_horizon.engine.values import Calendar, Money, set_calendar


@pytest.fixture(autouse=True)
def _shared_calendar():
    set_calendar(Calendar(days_per_week=7, weeks_per_month=4, months_per_year=12))
    yield
    set_calendar(None)


# -- lifetime statistics (V28.7) ------------------------------------------


def test_counters_start_at_nothing():
    stats = LifetimeStatistics()

    assert stats.employees_hired == 0
    assert stats.total_profit.is_zero
    assert stats.net_lifetime_profit().is_zero


def test_profit_and_losses_are_recorded_separately():
    """V28.7 asks for totals, and a total that nets out hides the scale."""
    stats = LifetimeStatistics()

    stats.record_closed_position(Money(500))
    stats.record_closed_position(Money(-200))

    assert stats.total_profit == Money(500)
    assert stats.total_losses == Money(200)
    assert stats.net_lifetime_profit() == Money(300)
    assert stats.positions_closed == 2


def test_high_water_marks_only_rise():
    """V28.7: 'the most you have ever been worth' cannot fall."""
    stats = LifetimeStatistics()

    stats.observe(net_worth=Money(1_000), company_value=Money(500))
    stats.observe(net_worth=Money(400), company_value=Money(100))

    assert stats.highest_net_worth == Money(1_000)
    assert stats.highest_company_value == Money(500)


def test_records_survive_losing_a_company():
    """The counters describe the playthrough, not the current company."""
    stats = LifetimeStatistics()
    stats.record_founding()
    stats.record_hire()
    stats.record_hire()
    stats.record_closed_position(Money(900))

    stats.record_bankruptcy()
    stats.record_founding()

    assert stats.companies_founded == 2
    assert stats.companies_lost == 1
    assert stats.employees_hired == 2, "hires from the lost company still count"
    assert stats.total_profit == Money(900)


def test_a_summary_answers_questions_a_player_would_ask():
    """V28.8: statistics serve judgment rather than exist for their own sake."""
    stats = LifetimeStatistics()
    summary = stats.summary()

    assert "Employees ever hired" in summary
    assert "Companies acquired" in summary
    assert "Highest net worth" in summary


def test_statistics_survive_a_round_trip():
    stats = LifetimeStatistics()
    stats.record_hire()
    stats.record_closed_position(Money(1_500))
    stats.observe(net_worth=Money(9_000))

    restored = LifetimeStatistics()
    restored.restore(stats.state())

    assert restored.employees_hired == 1
    assert restored.total_profit == Money(1_500)
    assert restored.highest_net_worth == Money(9_000)
    assert restored.summary() == stats.summary()
