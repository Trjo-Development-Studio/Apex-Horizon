"""Tests for SimulationDate and the derived calendar (V30.4, V13.6)."""

from __future__ import annotations

import pytest

from apex_horizon.engine.values import Calendar, SimulationDate, get_calendar, set_calendar
from apex_horizon.engine.values.simulation_date import WEEKDAY_NAMES

CAL = Calendar(days_per_week=7, weeks_per_month=4, months_per_year=12)


@pytest.fixture(autouse=True)
def _shared_calendar():
    set_calendar(CAL)
    yield
    set_calendar(None)


def test_calendar_derives_its_own_sizes():
    assert CAL.days_per_month == 28
    assert CAL.days_per_year == 336


def test_calendar_loads_from_shipped_config():
    set_calendar(None)
    calendar = get_calendar()
    assert calendar.days_per_week == 7
    assert calendar.weeks_per_month == 4
    assert calendar.months_per_year == 12


def test_first_day_is_year_one_month_one_week_one_day_one():
    date = SimulationDate(1)
    assert (date.year(), date.month(), date.week_of_month(), date.day_of_week()) == (1, 1, 1, 1)
    assert date.label() == "Year 1, Month 1, Week 1, Day 1"


def test_day_counter_is_the_only_stored_state():
    # V30.4: the calendar is derived from the counter, never the reverse.
    assert SimulationDate(100).day == 100
    assert repr(SimulationDate(100)) == "SimulationDate(day=100)"


def test_calendar_components_across_boundaries():
    # Day 28 is the last day of month 1; day 29 begins month 2.
    assert SimulationDate(28).month() == 1
    assert SimulationDate(28).week_of_month() == 4
    assert SimulationDate(29).month() == 2
    assert SimulationDate(29).week_of_month() == 1
    # Day 336 is the last day of year 1; day 337 begins year 2.
    assert SimulationDate(336).year() == 1
    assert SimulationDate(337).year() == 2
    assert SimulationDate(337).month() == 1


def test_label_matches_design_bible_example_format():
    # V13.6 gives "Year 3, Month 8, Week 2, Day 4" as the display format.
    date = SimulationDate(1 + 2 * 336 + 7 * 28 + 1 * 7 + 3)
    assert date.label() == "Year 3, Month 8, Week 2, Day 4"
    assert date.short_label() == "Y3 M8 W2 D4"


def test_weekday_names_cycle_and_training_example_holds():
    # V5.9/V13.12: training beginning on a Friday for 10 days completes on a Monday.
    friday = next(
        SimulationDate(day) for day in range(1, 15)
        if SimulationDate(day).weekday_name() == "Friday"
    )
    assert friday.advanced(10).weekday_name() == "Monday"


def test_weekday_name_for_first_day():
    assert SimulationDate(1).weekday_name() == WEEKDAY_NAMES[0] == "Monday"


def test_advancing_and_differences():
    start = SimulationDate(10)
    assert start.advanced(5) == SimulationDate(15)
    assert start + 5 == SimulationDate(15)
    assert SimulationDate(15) - SimulationDate(10) == 5
    assert SimulationDate(15) - 5 == SimulationDate(10)
    assert start.days_until(SimulationDate(20)) == 10
    assert start.days_until(SimulationDate(5)) == -5


def test_dates_are_immutable_and_ordered():
    start = SimulationDate(10)
    start.advanced(5)
    assert start.day == 10
    assert SimulationDate(1) < SimulationDate(2)
    assert len({SimulationDate(1), SimulationDate(1)}) == 1


def test_period_boundaries_used_for_scheduled_events():
    # Weekly (V13.9), monthly (V13.10) and yearly (V13.11) progression hooks.
    assert SimulationDate(8).starts_new_week()
    assert not SimulationDate(9).starts_new_week()
    assert SimulationDate(29).starts_new_month()
    assert not SimulationDate(30).starts_new_month()
    assert SimulationDate(337).starts_new_year()
    # Day 1 is the start of everything but does not "start a new" period.
    first = SimulationDate(1)
    assert first.is_first_day_of_year()
    assert not first.starts_new_year()
    assert not first.starts_new_month()
    assert not first.starts_new_week()


def test_invalid_days_are_rejected():
    with pytest.raises(ValueError):
        SimulationDate(0)
    with pytest.raises(TypeError):
        SimulationDate("5")  # type: ignore[arg-type]  # deliberately wrong
    with pytest.raises(TypeError):
        SimulationDate(True)


def test_explicit_calendar_overrides_shared_one():
    small = Calendar(days_per_week=5, weeks_per_month=2, months_per_year=4)
    assert small.days_per_month == 10
    assert SimulationDate(11).month(small) == 2
    # The shared calendar is unaffected.
    assert SimulationDate(11).month() == 1
