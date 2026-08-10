"""Tests for AI companies (Design Bible Volume 26)."""

from __future__ import annotations

from random import Random

import pytest

from apex_horizon.engine.ai import AICompanies
from apex_horizon.engine.company import InvestmentCompany
from apex_horizon.engine.economy import EconomySystem
from apex_horizon.engine.employees import Department, RiskTolerance
from apex_horizon.engine.market import MarketSystem
from apex_horizon.engine.simulation import SimulationClock, SimulationEngine
from apex_horizon.engine.values import Calendar, IdAllocator, Money, set_calendar
from apex_horizon.engine.world import generate_world


@pytest.fixture(autouse=True)
def _shared_calendar():
    set_calendar(Calendar(days_per_week=7, weeks_per_month=4, months_per_year=12))
    yield
    set_calendar(None)


def build(seed: int = 2026):
    world, allocator, names = generate_world(seed)
    economy = EconomySystem()
    market = MarketSystem(world, economy=economy)
    market.populate(Random(seed))
    clock = SimulationClock(
        seconds_per_day=1.0, speed=1, speed_options=(1, 2, 3), max_days_per_update=10_000
    )
    engine = SimulationEngine(clock=clock, seed=seed)
    economy.register(engine)
    market.register(engine)

    ai = AICompanies(allocator=allocator)
    ai.populate(Random(seed + 1), market, names)
    ai.register(engine)
    return ai, market, engine, names, allocator


# -- what an AI company is (V26.10) ---------------------------------------


def test_ai_companies_are_ordinary_investment_companies():
    """V26.10: the same structure as the player's, not a parallel model."""
    ai, _, _, _, _ = build()

    assert ai.companies
    for company in ai.companies:
        assert isinstance(company, InvestmentCompany)
        assert company.investments is not None
        assert company.employees is not None


def test_they_are_founded_with_capital_and_names_from_the_world():
    ai, _, _, _, _ = build()

    names = [company.name for company in ai.companies]
    assert len(set(names)) == len(names), "each company is its own organisation"
    assert all(company.finances.cash.is_positive for company in ai.companies)


# -- a population, not an opponent (V26.3, V26.4, V26.11) -----------------


def test_no_two_companies_are_alike():
    """V26.3: behaviour comes from who each one hired, so they differ."""
    ai, _, _, _, _ = build()

    biases = {round(company.employees.risk_bias, 4) for company in ai.companies}
    assert len(biases) > 1, "a population, not one repeated company"


def test_ai_staff_lean_riskier_than_the_players():
    """V26.4: skewed toward higher risk on average, through V5.7 not a new system."""
    from apex_horizon.engine.employees.recruitment import generate_applicants
    from apex_horizon.engine.world import NameGenerator

    bold = {RiskTolerance.BOLD, RiskTolerance.AGGRESSIVE}

    def share_bold(risk_bias: float) -> float:
        rng = Random(7)
        names = NameGenerator(Random(7))
        people = generate_applicants(
            rng, names, IdAllocator(), count=400, risk_bias=risk_bias, day=1
        )
        return sum(
            1 for person in people if person.hidden.risk_tolerance in bold
        ) / len(people)

    assert share_bold(0.6) > share_bold(0.0)


def test_a_bias_shifts_the_distribution_rather_than_forcing_it():
    """V26.3: some AI companies still end up conservative."""
    from apex_horizon.engine.employees.recruitment import generate_applicants
    from apex_horizon.engine.world import NameGenerator

    people = generate_applicants(
        Random(3), NameGenerator(Random(3)), IdAllocator(),
        count=300, risk_bias=0.75, day=1,
    )
    tolerances = {person.hidden.risk_tolerance for person in people}
    assert RiskTolerance.CAUTIOUS in tolerances, "risk is skewed, never forced"


# -- they act (V26.7, V26.8, V18.16) --------------------------------------


def test_they_hire_and_staff_their_weakest_department():
    ai, _, engine, _, _ = build()

    engine.run_days(60)

    staffed = [company for company in ai.companies if len(company.employees)]
    assert staffed, "AI companies employ their own staff (V5.18)"
    company = staffed[0]
    assert any(
        company.employees.output(department) > 0 for department in Department
    )


def test_their_trading_reaches_the_market_as_ordinary_demand():
    """V26.8, V4.8: their combined activity is part of supply and demand."""
    ai, _, engine, _, _ = build()

    engine.run_days(240)

    positions = sum(
        len(company.investments.open_positions())
        for company in ai.operating if company.investments
    )
    assert positions > 0, "AI companies invest through the V8.3 workflow"


def test_they_use_the_same_investment_workflow():
    """V26.7: research, approval, execution — not a separate decision system."""
    ai, _, engine, _, _ = build()
    engine.run_days(200)

    company = max(ai.operating,
                  key=lambda c: len(c.investments.positions) if c.investments else 0)
    assert company.investments is not None
    stats = company.investments.statistics()
    assert set(stats) >= {"Holdings value", "Open positions", "Realised"}


def test_they_operate_under_the_same_financial_rules():
    """V17.18: they earn, spend, and can fail, exactly as the player does."""
    ai, _, engine, _, _ = build()
    engine.run_days(336)

    for company in ai.operating:
        # Salaries and running costs are real, so the ledger is not empty.
        assert company.finances.ledger.lifetime.expenses.is_positive


# -- growth (V26.5, V18.17) -----------------------------------------------


def test_a_company_grows_as_it_becomes_worth_more():
    ai, _, _, _, _ = build()
    company = ai.companies[0]
    director = ai.directors[company.id]
    thresholds = director.config.get_list("ai.level_value_thresholds")

    assert company.level == 1
    company.finances.cash = Money(int(thresholds[0]) + 1)
    director._consider_growth()

    assert company.level == 2


# -- persistence (V16.11, V15.11) -----------------------------------------


def test_ai_companies_survive_a_round_trip():
    ai, market, engine, names, _ = build()
    engine.run_days(120)
    before = {c.id: (c.name, c.value(), len(c.employees)) for c in ai.companies}

    restored = AICompanies(allocator=ai.allocator)
    restored.restore(ai.state(), market=market, names=names, rng=Random(1))

    after = {c.id: (c.name, c.value(), len(c.employees)) for c in restored.companies}
    assert after == before


def test_ai_companies_can_still_acquire_once_subsidiaries_is_a_gated_unlock():
    """Bug found while gating Subsidiaries behind an unlock (2026-08-10): AI
    companies never run through the player's Unlock Tree at all, so without
    an explicit bypass here — the same one training_allowed already gets —
    every AI company would silently lose the ability to acquire outright the
    moment the gate existed, contradicting V12.14 (AI organisations expand
    by acquisition too)."""
    ai, _, _, _, _ = build()
    assert all(company.subsidiaries.unlocked for company in ai.companies)


def test_the_acquisition_bypass_survives_a_round_trip():
    ai, market, engine, names, _ = build()
    engine.run_days(30)

    restored = AICompanies(allocator=ai.allocator)
    restored.restore(ai.state(), market=market, names=names, rng=Random(1))

    for company in restored.companies:
        if company.subsidiaries is not None:  # None only for a bankrupt company
            assert company.subsidiaries.unlocked


def test_a_directors_random_stream_is_saved():
    """V15.11: their decisions reach the market, so they must not restart.

    A restored director continues from where the live one had got to, which is
    what makes a reloaded world take the same decisions the saved one would.
    """
    ai, market, engine, names, _ = build()
    engine.run_days(60)
    company = ai.companies[0]
    saved = ai.state()

    restored = AICompanies(allocator=ai.allocator)
    restored.restore(saved, market=market, names=names, rng=Random(99))

    live = ai.directors[company.id]
    reloaded = restored.directors[company.id]
    assert [reloaded.random() for _ in range(5)] == [live.random() for _ in range(5)]


def test_statistics_describe_the_population():
    ai, _, engine, _, _ = build()
    engine.run_days(120)

    stats = ai.statistics()
    assert stats["Operating"] == len(ai.operating)
    assert stats["Operating"] + stats["Failed"] == len(ai.companies)
    assert isinstance(stats["Combined value"], Money)


def test_an_ai_company_can_fail_like_any_other():
    """V26.11, V17.18: some failing, under the rules the player plays by."""
    ai, _, engine, _, _ = build()
    victim = ai.companies[0]
    threshold = victim.config.get_int("company.bankruptcy_cash_threshold")
    victim.finances.cash = Money(threshold - 1)

    engine.run_days(30)

    assert victim.bankrupt
    assert victim not in ai.operating
    assert victim not in ai.ranked()
    assert len(victim.employees) == 0, "staff are released on bankruptcy"
    assert ai.statistics()["Failed"] == 1

    # The rest of the world carries on without it (V4.10).
    engine.run_days(60)
    assert ai.operating
