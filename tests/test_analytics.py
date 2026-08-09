"""Tests for the analytics layer (Design Bible Volume 9)."""

from __future__ import annotations

from dataclasses import dataclass
from random import Random
from typing import Any

import pytest

from apex_horizon.engine.analytics import AnalyticsService, AnalyticsTier, HistoryRecorder
from apex_horizon.engine.company import Player
from apex_horizon.engine.economy import EconomySystem
from apex_horizon.engine.market import MarketSystem
from apex_horizon.engine.simulation import (
    SimulationClock,
    SimulationContext,
    SimulationEngine,
)
from apex_horizon.engine.unlocks import CREATE_COMPANY
from apex_horizon.engine.values import Calendar, Money, set_calendar
from apex_horizon.engine.world import generate_world


@pytest.fixture(autouse=True)
def _shared_calendar():
    set_calendar(Calendar(days_per_week=7, weeks_per_month=4, months_per_year=12))
    yield
    set_calendar(None)


@dataclass
class FakeContext:
    """Just enough of a game for analytics to read (V9.22: it only reads)."""

    player: Any = None
    company: Any = None
    market: Any = None


def build(seed: int = 2026):
    world, allocator, _ = generate_world(seed)
    economy = EconomySystem()
    market = MarketSystem(world, economy=economy)
    market.populate(Random(seed))
    clock = SimulationClock(
        seconds_per_day=1.0, speed=1, speed_options=(1, 2, 3), max_days_per_update=10_000
    )
    engine = SimulationEngine(clock=clock, seed=seed)
    market.register(engine)

    player = Player("Founder", allocator=allocator)
    player.cash = Money(200_000)
    player.unlocks.unlock(CREATE_COMPANY)
    company, _ = player.found_company("Test Capital", 1)
    assert company is not None, "the builder must produce a company"
    company.attach_market(market, allocator)
    company.register(engine)

    context = FakeContext(player=player, company=company, market=market)
    return context, engine


def context_for(engine: SimulationEngine) -> SimulationContext:
    return SimulationContext(
        date=engine.date, rng=engine.rng, day_number=engine.date.day, tick=engine.tick
    )


def report_of(service):
    """The company report, insisted upon rather than assumed."""
    report = service.company_report()
    assert report is not None, "a company exists, so it has a report"
    return report


# -- tiers (V9.4) ---------------------------------------------------------
def test_the_basic_tier_answers_only_what_is_happening():
    context, _ = build()
    service = AnalyticsService(context)

    company = service.company_report()
    assert company is not None
    labels = [metric.label for metric in company.metrics]
    assert "Cash" in labels
    assert "Profit margin" not in labels, "margin belongs to the Detailed tier"


def test_each_tier_adds_depth():
    context, _ = build()
    service = AnalyticsService(context)
    basic = len(report_of(service).metrics)

    service.tier = AnalyticsTier.DETAILED
    detailed = len(report_of(service).metrics)
    service.tier = AnalyticsTier.ADVANCED
    advanced = len(report_of(service).metrics)

    assert basic < detailed < advanced


def test_a_locked_report_is_absent_rather_than_empty():
    """V9.21: better to show nothing than a figure the player cannot use."""
    context, _ = build()
    history = HistoryRecorder(context)
    service = AnalyticsService(context, history=history)

    assert service.historical_report() is None

    service.tier = AnalyticsTier.DETAILED
    assert service.historical_report() is not None


def test_reports_are_skipped_before_there_is_a_company():
    context = FakeContext()
    service = AnalyticsService(context)

    assert service.company_report() is None
    assert service.employee_report() is None
    assert service.reports() == []


# -- history (V9.10) ------------------------------------------------------
def test_a_snapshot_is_taken_each_month():
    context, engine = build()
    recorder = HistoryRecorder(context)
    recorder.register(engine)

    engine.run_days(28 * 3)

    assert len(recorder.snapshots) == 3
    assert recorder.snapshots[0].net_worth.is_positive


def test_a_repeated_month_records_only_once():
    """V15.26: a phase handler must be safe to run twice."""
    context, engine = build()
    recorder = HistoryRecorder(context)

    recorder.record(context_for(engine))
    recorder.record(context_for(engine))

    assert len(recorder.snapshots) == 1


def test_change_over_reports_none_without_enough_history():
    context, engine = build()
    recorder = HistoryRecorder(context)
    recorder.register(engine)
    engine.run_days(28 * 2)

    assert recorder.change_over("net_worth", 12) is None
    assert recorder.change_over("net_worth", 1) is not None


def test_the_history_is_capped():
    context, engine = build()
    recorder = HistoryRecorder(context)
    recorder._limit = 5
    for _ in range(25):
        recorder._last_recorded_day = None
        engine.date = engine.date.advanced(1)
        recorder.record(context_for(engine))

    assert len(recorder.snapshots) == 5


def test_history_survives_a_round_trip():
    context, engine = build()
    recorder = HistoryRecorder(context)
    recorder.register(engine)
    engine.run_days(28 * 2)

    restored = HistoryRecorder(context)
    restored.restore(recorder.state())

    assert len(restored.snapshots) == len(recorder.snapshots)
    assert restored.snapshots[0].net_worth == recorder.snapshots[0].net_worth
    assert restored.snapshots[-1].day == recorder.snapshots[-1].day


def test_the_service_remembers_its_tier():
    context, _ = build()
    service = AnalyticsService(context)
    service.tier = AnalyticsTier.ADVANCED

    restored = AnalyticsService(context)
    restored.restore(service.state())

    assert restored.tier is AnalyticsTier.ADVANCED


def test_a_series_is_ordered_oldest_first():
    context, engine = build()
    recorder = HistoryRecorder(context)
    recorder.register(engine)
    engine.run_days(28 * 4)

    series = recorder.series("net_worth")
    days = [day for day, _ in series]
    assert days == sorted(days)
