"""Tests for the simulation engine (Design Bible V13, V29, V15.11)."""

from __future__ import annotations

import pytest

from apex_horizon.engine import errors
from apex_horizon.engine.simulation import (
    PHASE_ORDER,
    PeriodBoundary,
    SimulationClock,
    SimulationEngine,
    SimulationPhase,
)
from apex_horizon.engine.values import Calendar, SimulationDate, set_calendar

CAL = Calendar(days_per_week=7, weeks_per_month=4, months_per_year=12)


@pytest.fixture(autouse=True)
def _shared_calendar():
    set_calendar(CAL)
    errors.clear_error_notifiers()
    yield
    set_calendar(None)
    errors.clear_error_notifiers()


def make_engine(**kwargs) -> SimulationEngine:
    clock = SimulationClock(
        seconds_per_day=1.0, speed=1, speed_options=(1, 2, 3), max_days_per_update=1000
    )
    return SimulationEngine(clock=clock, **kwargs)


# -- phase ordering (V29) -------------------------------------------------


def test_phase_order_matches_volume_29():
    assert [phase.name for phase in PHASE_ORDER] == [
        "NEWS",
        "ECONOMY",
        "BANKS",
        "COMPANIES",
        "EMPLOYEES",
        "RESEARCH",
        "INVESTMENT_FUNDS",
        "MARKET",
        "FINANCIAL_CALCULATIONS",
        "USER_INTERFACE",
    ]


def test_phases_run_in_order_regardless_of_registration_order():
    # V29.13: every system reads only fully-settled data from earlier steps.
    engine = make_engine()
    seen: list[str] = []
    for phase in reversed(PHASE_ORDER):
        engine.register(phase, lambda _ctx, name=phase.name: seen.append(name))
    engine.step_day()
    assert seen == [phase.name for phase in PHASE_ORDER]


def test_multiple_handlers_in_one_phase_run_in_registration_order():
    engine = make_engine()
    seen: list[int] = []
    for index in range(3):
        engine.register(SimulationPhase.MARKET, lambda _ctx, i=index: seen.append(i))
    engine.step_day()
    assert seen == [0, 1, 2]


# -- time progression -----------------------------------------------------


def test_day_advances_once_per_step():
    engine = make_engine(start_date=SimulationDate(1))
    engine.step_day()
    assert engine.date == SimulationDate(2)
    assert engine.tick == 1


def test_context_describes_the_day_being_processed():
    engine = make_engine(start_date=SimulationDate(5))
    seen = []
    engine.register(SimulationPhase.NEWS, seen.append)
    engine.step_day()
    assert seen[0].date == SimulationDate(5)
    assert seen[0].day_number == 5


def test_update_converts_real_time_into_days():
    engine = make_engine()
    assert engine.update(3.0) == 3
    assert engine.date == SimulationDate(4)


def test_run_days_simulates_immediately():
    engine = make_engine()
    engine.run_days(10)
    assert engine.date == SimulationDate(11)


def test_run_days_rejects_negative_input():
    with pytest.raises(ValueError):
        make_engine().run_days(-1)


# -- scheduled progression (V13.9 - V13.11) -------------------------------


def test_weekly_events_fire_on_completed_weeks():
    engine = make_engine()
    weeks: list[int] = []
    engine.register_boundary(PeriodBoundary.WEEK, lambda ctx: weeks.append(ctx.day_number))
    engine.run_days(28)
    # A 7-day week completes on days 7, 14, 21 and 28.
    assert weeks == [7, 14, 21, 28]


def test_monthly_and_yearly_events_fire_on_completed_periods():
    engine = make_engine()
    months: list[int] = []
    years: list[int] = []
    engine.register_boundary(PeriodBoundary.MONTH, lambda ctx: months.append(ctx.day_number))
    engine.register_boundary(PeriodBoundary.YEAR, lambda ctx: years.append(ctx.day_number))
    engine.run_days(CAL.days_per_year)
    assert months[:2] == [28, 56]
    assert len(months) == 12
    assert years == [336]


def test_overlapping_boundaries_all_fire_shortest_first():
    engine = make_engine()
    seen: list[str] = []
    for boundary in (PeriodBoundary.YEAR, PeriodBoundary.MONTH, PeriodBoundary.WEEK):
        engine.register_boundary(boundary, lambda _ctx, b=boundary: seen.append(b.value))
    engine.run_days(CAL.days_per_year)
    # The last day of a year also completes its month and week.
    assert seen[-3:] == ["week", "month", "year"]


def test_boundary_handlers_run_after_the_days_phases():
    engine = make_engine()
    seen: list[str] = []
    engine.register(SimulationPhase.FINANCIAL_CALCULATIONS, lambda _c: seen.append("phase"))
    engine.register_boundary(PeriodBoundary.WEEK, lambda _c: seen.append("week"))
    engine.run_days(7)
    assert seen[-2:] == ["phase", "week"]


# -- background updates (V13.19) ------------------------------------------


def test_background_updates_run_periodically():
    engine = make_engine()
    ticks: list[int] = []
    engine.register_background(lambda ctx: ticks.append(ctx.tick))
    engine.run_days(21)
    # Roughly every five ticks, starting from the first.
    assert ticks == [0, 5, 10, 15, 20]


# -- determinism (V15.11) -------------------------------------------------


def test_same_seed_reproduces_the_same_random_sequence():
    def sample(seed: int) -> list[float]:
        engine = make_engine(seed=seed)
        drawn: list[float] = []
        engine.register(SimulationPhase.MARKET, lambda ctx: drawn.append(ctx.rng.random()))
        engine.run_days(50)
        return drawn

    assert sample(1234) == sample(1234)
    assert sample(1234) != sample(5678)


def test_state_round_trip_continues_the_same_sequence():
    engine = make_engine(seed=99)
    drawn: list[float] = []
    engine.register(SimulationPhase.MARKET, lambda ctx: drawn.append(ctx.rng.random()))
    engine.run_days(10)
    saved = engine.state()
    expected = [engine.rng.random() for _ in range(5)]

    restored = make_engine(seed=1)
    # Round-trip the state through lists, as a save file encoding would.
    saved["rng_state"] = [saved["rng_state"][0], list(saved["rng_state"][1]), saved["rng_state"][2]]
    restored.restore(saved)
    assert restored.date == engine.date
    assert restored.tick == engine.tick
    assert [restored.rng.random() for _ in range(5)] == expected


def test_restore_tolerates_minimal_state():
    engine = make_engine()
    engine.restore({"day": 42})
    assert engine.date == SimulationDate(42)


# -- resilience (V15.13, V15.26) ------------------------------------------


def test_failing_handler_does_not_stop_the_simulation():
    engine = make_engine()
    messages: list[str] = []
    errors.subscribe_error_notifier(messages.append)

    def broken(_ctx):
        raise RuntimeError("system exploded")

    survivors: list[int] = []
    engine.register(SimulationPhase.ECONOMY, broken)
    engine.register(SimulationPhase.MARKET, lambda ctx: survivors.append(ctx.day_number))

    engine.run_days(3)

    # Later phases still ran, and time still advanced.
    assert survivors == [1, 2, 3]
    assert engine.date == SimulationDate(4)
    # The player was told, once per failed day (after retries were exhausted).
    assert len(messages) == 3


# -- random events (V13.18) -----------------------------------------------


def test_random_events_fire_at_roughly_the_configured_rate():
    engine = make_engine(seed=7)
    fired: list[int] = []
    engine.register_random_event(lambda ctx: fired.append(ctx.day_number))
    engine.run_days(1000)
    # Daily rolls at 5% plus weekly/monthly/yearly rolls; well short of every day
    # and clearly more than never.
    assert 30 < len(fired) < 400


def test_no_random_event_rolls_without_handlers():
    engine = make_engine(seed=7)
    engine.run_days(10)
    # With no handlers registered the generator is untouched, keeping the random
    # sequence stable regardless of which systems happen to be present.
    assert engine.rng.random() == pytest.approx(0.32383276483316237)
