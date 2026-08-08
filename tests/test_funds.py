"""Tests for investment funds (Design Bible Volume 11)."""

from __future__ import annotations

from random import Random

import pytest

from apex_horizon.engine.company import Player
from apex_horizon.engine.economy import EconomySystem
from apex_horizon.engine.market import MarketSystem
from apex_horizon.engine.simulation import SimulationClock, SimulationEngine
from apex_horizon.engine.unlocks import CREATE_COMPANY
from apex_horizon.engine.values import Calendar, Money, set_calendar
from apex_horizon.engine.world import generate_world


@pytest.fixture(autouse=True)
def _shared_calendar():
    set_calendar(Calendar(days_per_week=7, weeks_per_month=4, months_per_year=12))
    yield
    set_calendar(None)


def build(unlocked: bool = True, staff: int = 3):
    world, allocator, names = generate_world(2026)
    economy = EconomySystem()
    market = MarketSystem(world, economy=economy)
    market.populate(Random(2026))
    clock = SimulationClock(
        seconds_per_day=1.0, speed=1, speed_options=(1, 2, 3), max_days_per_update=10_000
    )
    engine = SimulationEngine(clock=clock, seed=2026)
    market.register(engine)

    player = Player("Owner", cash=Money(3_000_000), allocator=allocator)
    player.unlocks.unlock(CREATE_COMPANY)
    company, _ = player.found_company("Test Capital", 1)
    company.attach_market(market, allocator)
    company.register(engine)
    player.transfer_to_company(Money(500_000), 1)
    company.funds.unlocked = unlocked

    roster = company.employees
    roster.refresh_applicants(engine.rng, names, allocator, 1)
    for applicant in roster.applicants[:staff]:
        roster.hire(applicant, 1)
    return player, company, market, engine


# -- the unlock (V11.3) ---------------------------------------------------


def test_funds_require_the_final_unlock():
    """V11.3, V6.8: the hardest gate in the game."""
    _, company, _, _ = build(unlocked=False)

    allowed, reason = company.funds.can_create()

    assert not allowed
    assert "unlocked" in reason
    assert company.funds.create("Anything", day=1)[0] is None


# -- creating a fund (V11.6, V11.7) ---------------------------------------


def test_a_fund_opens_with_capital_from_external_investors():
    _, company, _, _ = build()

    fund, message = company.funds.create("Horizon Growth", day=1)

    assert fund is not None, message
    assert fund.name == "Horizon Growth"
    assert fund.assets_under_management().is_positive
    assert fund.contributed.is_positive


def test_funds_are_independent_of_one_another():
    """V11.7: each operates independently while belonging to the company."""
    _, company, _, _ = build()

    first, _ = company.funds.create("Alpha", day=1)
    second, _ = company.funds.create("Beta", day=1)

    assert first is not None and second is not None
    assert first.id != second.id
    assert first.finances is not second.finances


def test_two_funds_cannot_share_a_name():
    _, company, _, _ = build()
    company.funds.create("Alpha", day=1)

    fund, reason = company.funds.create("alpha", day=1)

    assert fund is None
    assert "already" in reason


def test_a_new_fund_with_no_investments_is_a_valid_state():
    """V11.21 says so explicitly: an empty fund is not an error."""
    _, company, _, _ = build()

    fund, _ = company.funds.create("Alpha", day=1)

    assert fund.investments is not None
    assert fund.investments.open_positions() == []
    assert fund.statistics()["Active investments"] == 0


# -- whose money it is (V11.5, V11.14) ------------------------------------


def test_fund_money_is_never_company_money():
    """V11.5: it belongs to the fund's investors."""
    _, company, _, _ = build()
    company_cash = company.finances.cash

    fund, _ = company.funds.create("Alpha", day=1)

    assert company.finances.cash == company_cash, "seeding a fund costs the company nothing"
    assert fund.finances is not company.finances
    assert fund.assets_under_management().is_positive


def test_investor_capital_is_financing_rather_than_revenue():
    """The fund was entrusted with it, it did not earn it (V17.26)."""
    _, company, _, _ = build()
    fund, _ = company.funds.create("Alpha", day=1)

    assert fund.finances.ledger.lifetime.revenue.is_zero
    assert fund.finances.ledger.cash_in.is_positive


def test_a_fund_uses_the_companys_employees():
    """V11.14: employees manage company capital and fund capital alike."""
    _, company, _, _ = build()
    fund, _ = company.funds.create("Alpha", day=1)

    assert fund.employees is company.employees


def test_assets_under_management_are_not_counted_as_company_assets():
    """V11.5: managing money is not owning it."""
    _, company, _, _ = build()
    before = company.finances.assets()

    company.funds.create("Alpha", day=1)

    assert company.finances.assets() == before


# -- operating (V11.9, V11.8) ---------------------------------------------


def test_a_fund_invests_through_the_same_workflow():
    """V11.9, V11.23: composition, not a second implementation."""
    from apex_horizon.engine.investments import InvestmentSystem

    _, company, _, engine = build()
    fund, _ = company.funds.create("Alpha", day=1)
    fund.register(engine)

    engine.run_days(240)

    assert isinstance(fund.investments, InvestmentSystem)
    assert fund.investments.positions, "the fund should be putting money to work"


def test_assets_under_management_add_up_across_funds():
    """V11.8."""
    _, company, _, _ = build()
    first, _ = company.funds.create("Alpha", day=1)
    second, _ = company.funds.create("Beta", day=1)

    total = company.funds.assets_under_management()

    assert total == first.assets_under_management() + second.assets_under_management()


def test_the_company_is_paid_for_managing_a_fund():
    """V11.5: the company earns by managing, not by owning."""
    _, company, _, engine = build()
    fund, _ = company.funds.create("Alpha", day=1)
    fund.register(engine)

    engine.run_days(336)

    assert fund.fees_paid.is_positive
    assert company.finances.ledger.lifetime.revenue.is_positive


# -- investor confidence (V11.11, V11.20) ---------------------------------


def test_confidence_follows_performance():
    """V11.11: well-managed funds become more attractive."""
    _, company, _, engine = build()
    fund, _ = company.funds.create("Alpha", day=1)
    fund.register(engine)
    fund.confidence = 0.5

    # A fund that has made money for its investors earns their trust.
    fund.finances.cash = fund.contributed + fund.contributed
    company.funds._update_confidence(fund)
    grown = fund.confidence

    fund.confidence = 0.5
    fund.finances.cash = Money(fund.contributed.amount / 4)
    company.funds._update_confidence(fund)

    assert grown > 0.5 > fund.confidence


def test_more_money_arrives_without_the_player_doing_anything():
    """V11.20: deposits follow the record, not an action."""
    _, company, _, engine = build()
    fund, _ = company.funds.create("Alpha", day=1)
    fund.register(engine)
    before = fund.contributed

    engine.run_days(336)

    assert fund.contributed > before


# -- persistence (V16.11) -------------------------------------------------


def test_funds_survive_a_round_trip():
    _, company, market, engine = build()
    fund, _ = company.funds.create("Alpha", day=1)
    fund.register(engine)
    engine.run_days(200)
    before = company.funds.state()

    company.funds.restore(before, market=market)

    assert len(company.funds) == 1
    restored = company.funds.funds[0]
    assert restored.name == "Alpha"
    assert restored.contributed == fund.contributed
    assert restored.fees_paid == fund.fees_paid
    assert restored.assets_under_management() == fund.assets_under_management()
