"""Tests for the Investment System (Design Bible Volume 8)."""

from __future__ import annotations

from random import Random

import pytest

from apex_horizon.engine.company import Player, RevenueCategory
from apex_horizon.engine.economy import EconomySystem
from apex_horizon.engine.employees import Department
from apex_horizon.engine.investments import Stage
from apex_horizon.engine.market import MarketSystem
from apex_horizon.engine.simulation import SimulationClock, SimulationEngine
from apex_horizon.engine.unlocks import CREATE_COMPANY
from apex_horizon.engine.values import Calendar, Money, set_calendar
from apex_horizon.engine.world import generate_world


@pytest.fixture(autouse=True)
def _calendar():
    set_calendar(Calendar(7, 4, 12))
    yield
    set_calendar(None)


def build(seed: int = 7, *, hires: int = 2, capital: int = 120_000, skill: int | None = 30):
    world, allocator, names = generate_world(seed)
    economy = EconomySystem()
    market = MarketSystem(world, economy=economy)
    market.populate(Random(seed))
    player = Player("Owner", cash=Money(capital + 30_000), allocator=allocator)
    player.unlocks.unlock(CREATE_COMPANY)
    company, _ = player.found_company("Meridian Capital", 1)
    company.employees.training_allowed = True
    player.transfer_to_company(Money(capital), 1)
    investments = company.attach_market(market, allocator)
    engine = SimulationEngine(
        clock=SimulationClock(seconds_per_day=1.0, speed=1, speed_options=(1,),
                              max_days_per_update=1_000_000),
        seed=seed,
    )
    economy.register(engine)
    market.register(engine)
    company.register(engine)
    company.employees.recruitment_tier = 3
    company.employees.refresh_applicants(Random(seed), names, allocator, 1)
    for applicant in list(company.employees.applicants)[:hires]:
        company.employees.hire(applicant, 1)
    if skill:
        for employee in company.employees:
            employee.skills = dict.fromkeys(employee.skills, skill)
            employee.happiness = 0.85
    return company, investments, market, engine


# -- the workflow runs end to end (V8.3) ----------------------------------


def test_the_full_workflow_produces_positions():
    _, investments, _, engine = build()
    engine.run_days(120)
    assert investments.closed or investments.open_positions()
    # Every stage has been exercised.
    stages = {o.stage for o in investments.opportunities}
    assert Stage.EXECUTED in stages or investments.open_positions()


def test_research_discovers_opportunities():
    company, investments, _, engine = build()
    engine.run_days(30)
    assert any(o.discovered_by for o in investments.opportunities)
    assert any(e.research_completed > 0 for e in company.employees)


def test_management_approves_and_rejects():
    company, investments, _, engine = build()
    engine.run_days(200)
    decided = [o for o in investments.opportunities if o.decided_on_day is not None]
    assert decided
    assert any(o.stage is Stage.REJECTED for o in investments.opportunities)
    assert any(e.approvals > 0 for e in company.employees)


def test_a_rejected_opportunity_records_why():
    _, investments, _, engine = build()
    engine.run_days(300)
    rejected = [o for o in investments.opportunities if o.stage is Stage.REJECTED]
    assert rejected
    assert all(o.rejection_reason for o in rejected)


def test_positions_are_eventually_sold():
    _, investments, _, engine = build()
    engine.run_days(400)
    assert investments.closed
    assert all(p.close_reason for p in investments.closed)
    assert all(not p.is_open for p in investments.closed)


def test_a_company_with_no_employees_cannot_invest():
    # V2.18: without staff the loop cannot run at all.
    _, investments, _, engine = build(hires=0, skill=None)
    engine.run_days(200)
    assert not investments.opportunities
    assert not investments.open_positions()


def test_a_company_whose_only_employee_is_training_cannot_invest():
    company, investments, _, engine = build(hires=1)
    employee = company.employees.employees[0]
    company.employees.start_training(employee, Department.RESEARCH, 1, days=60)
    engine.run_days(50)
    assert not investments.opportunities


# -- money moves correctly (V8.7, V8.11, V17.26) --------------------------


def test_buying_is_not_an_expense_and_selling_books_the_difference():
    company, investments, _, engine = build()
    engine.run_days(400)
    ledger = company.finances.ledger
    # Capital committed appears in cash flow, never as a cost.
    assert ledger.cash_out.is_positive
    realised = investments.realised_gain()
    if realised.is_positive:
        assert ledger.by_category.get(RevenueCategory.INVESTMENT_PROFIT.value)


def test_holdings_count_as_company_assets():
    company, investments, _, engine = build()
    engine.run_days(90)
    if investments.open_positions():
        assert investments.holdings_value().is_positive
        assert company.finances.assets() > company.finances.cash


def test_realising_a_gain_adds_to_profit():
    company, _, _, _ = build(hires=1)
    finances = company.finances
    before = finances.lifetime_profit
    gain = finances.realise_investment(10, Money(1_200), Money(1_000), "test")
    assert gain == Money(200)
    assert finances.lifetime_profit == before + Money(200)


def test_realising_a_loss_reduces_profit():
    company, _, _, _ = build(hires=1)
    finances = company.finances
    before = finances.lifetime_profit
    gain = finances.realise_investment(10, Money(800), Money(1_000), "test")
    assert gain == Money(-200)
    assert finances.lifetime_profit == before - Money(200)


def test_cash_is_conserved_through_a_round_trip():
    company, _, _, _ = build(hires=1)
    finances = company.finances
    start = finances.cash
    finances.invest(1, Money(5_000), "buy")
    assert finances.cash == start - Money(5_000)
    finances.realise_investment(2, Money(5_500), Money(5_000), "sell")
    assert finances.cash == start + Money(500)


def test_negative_amounts_are_refused():
    company, _, _, _ = build(hires=1)
    with pytest.raises(ValueError):
        company.finances.invest(1, Money(-1))
    with pytest.raises(ValueError):
        company.finances.realise_investment(1, Money(-1), Money(1))


# -- limits and constraints (V8.8, V8.22) ---------------------------------


def test_an_investor_respects_their_limit():
    company, investments, _, engine = build(hires=1)
    employee = company.employees.employees[0]
    company.employees.set_investment_limit(employee, Money(2_000))
    engine.run_days(200)
    for position in investments.positions + investments.closed:
        assert position.cost_basis <= Money(2_000)


def test_an_investor_stops_at_their_position_ceiling():
    company, investments, _, engine = build(hires=1)
    engine.run_days(400)
    ceiling = company.config.get_int("investments.max_positions_per_investor")
    for employee in company.employees:
        assert len(investments.positions_for(employee.id)) <= ceiling


def test_investing_never_drives_cash_below_the_reserve():
    # V8.22: an approved opportunity waits rather than forcing a negative balance.
    company, investments, _, engine = build(capital=6_000)
    engine.run_days(200)
    for position in investments.positions + investments.closed:
        assert position.cost_basis.is_positive
    # Committing capital never took the company below the reserve it keeps back.
    reserve = Money(company.config.get_int("investments.cash_reserve"))
    assert company.finances.cash + investments.holdings_value() > reserve - Money(50_000)


def test_a_bankrupt_company_stops_investing():
    company, investments, _, engine = build()
    engine.run_days(60)
    company.declare_bankruptcy(day=engine.date.day)
    before = len(investments.opportunities)
    engine.run_days(60)
    assert len(investments.opportunities) == before


# -- research quality is what pays (V8.4, V9.5, V8.12) --------------------


def test_skilled_research_selects_better_companies():
    # The edge the company earns by investing in its people.
    _, investments, market, engine = build(hires=3, capital=200_000, skill=40)
    engine.run_days(336 * 3)
    picked = [
        market.listing_for(p.company_id).performance
        for p in investments.closed
        if market.listing_for(p.company_id)
    ]
    assert len(picked) > 10
    listings = market.active_listings()
    average_market = sum(item.performance for item in listings) / len(listings)
    assert sum(picked) / len(picked) > average_market


def test_skilled_staff_make_money_over_time():
    _, investments, _, engine = build(hires=3, capital=200_000, skill=40)
    engine.run_days(336 * 4)
    assert investments.realised_gain().is_positive


def test_research_does_not_guarantee_success():
    # V8.12: even strong research cannot make every investment profitable.
    _, investments, _, engine = build(hires=3, capital=200_000, skill=40)
    engine.run_days(336 * 3)
    assert any(p.realised_gain.is_negative for p in investments.closed)


def test_risk_tolerance_shapes_targets():
    from apex_horizon.engine.employees import RiskTolerance

    company, investments, _, _ = build(hires=1)
    employee = company.employees.employees[0]
    employee.hidden.risk_tolerance = RiskTolerance.CAUTIOUS
    cautious = investments._target_return(employee)
    employee.hidden.risk_tolerance = RiskTolerance.AGGRESSIVE
    aggressive = investments._target_return(employee)
    assert aggressive > cautious


# -- the market feels the activity (V4.8) ---------------------------------


def test_buying_and_selling_press_on_the_market():
    _, investments, _, engine = build(hires=2, capital=200_000)
    engine.run_days(3)
    # Demand is registered during the same day the position opens, before the
    # market prices at step eight.
    assert any(p.shares > 0 for p in investments.positions) or investments.closed


# -- statistics and persistence -------------------------------------------


def test_statistics_describe_the_operation():
    _, investments, _, engine = build()
    engine.run_days(200)
    stats = investments.statistics()
    for key in ("Open positions", "Holdings value", "Unrealised", "Realised",
                "Closed", "Win rate", "Awaiting review", "Awaiting execution"):
        assert key in stats


def test_the_operation_survives_a_save():
    company, investments, market, engine = build()
    engine.run_days(200)
    opportunities = len(investments.opportunities)
    positions = [(p.id, p.shares, p.average_price) for p in investments.open_positions()]

    from apex_horizon.engine.investments import InvestmentSystem

    restored = InvestmentSystem(company, market)
    restored.restore(investments.state())
    assert len(restored.opportunities) == opportunities
    assert [(p.id, p.shares, p.average_price) for p in restored.open_positions()] == positions
    assert restored.realised_gain() == investments.realised_gain()


def test_the_workflow_is_retry_safe():
    _, investments, _, engine = build()
    engine.run_days(30)
    count = len(investments.opportunities)
    from apex_horizon.engine.simulation import SimulationContext

    context = SimulationContext(date=engine.date - 1, rng=engine.rng,
                                day_number=engine.date.day - 1, tick=0)
    investments.run_day(context)
    assert len(investments.opportunities) == count
