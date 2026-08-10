"""Tests for acquisitions and subsidiaries (Design Bible Volume 12)."""

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


def build(capital: int = 200_000_000, level: int = 3, unlocked: bool = True):
    world, allocator, _ = generate_world(2026)
    economy = EconomySystem()
    market = MarketSystem(world, economy=economy)
    market.populate(Random(2026))
    clock = SimulationClock(
        seconds_per_day=1.0, speed=1, speed_options=(1, 2, 3), max_days_per_update=10_000
    )
    engine = SimulationEngine(clock=clock, seed=2026)
    market.register(engine)

    player = Player("Owner", cash=Money(capital + 100_000), allocator=allocator)
    player.unlocks.unlock(CREATE_COMPANY)
    company, _ = player.found_company("Test Capital", 1)
    assert company is not None, "the builder must produce a company"
    company.attach_market(market, allocator)
    company.register(engine)
    company.set_level(level)
    company.subsidiaries.unlocked = unlocked
    player.transfer_to_company(Money(capital), 1)
    return player, company, market, world, engine


def cheapest(market, world):
    """The company that would cost least to buy outright."""
    return min(market.active_listings(),
               key=lambda listing: listing.market_cap.amount).company_id


def buy(company, target, day: int = 1):
    """Acquire a company and insist it worked, so a failure is reported here."""
    subsidiary, message = book(company).acquire(target, day=day)
    assert subsidiary is not None, message
    return subsidiary


def book(company):
    """The company's subsidiaries, which attaching a market always creates."""
    assert company.subsidiaries is not None
    return company.subsidiaries


# -- buying a company (V12.4, V12.22, V12.23) -----------------------------


def test_acquiring_transfers_ownership_on_the_existing_company():
    """V12.23: an ownership reference, not a second data model."""
    _, company, market, world, _ = build()
    target = cheapest(market, world)

    subsidiary, message = book(company).acquire(target, day=1)

    assert subsidiary is not None, message
    record = world.company_by_id(target)
    assert record is not None
    assert record.owner_id == company.id
    assert record.is_subsidiary


def test_the_full_price_leaves_company_cash():
    """V12.22: paid in full from company cash, with no financing."""
    _, company, market, world, _ = build()
    target = cheapest(market, world)
    price = book(company).price_of(target)
    assert price is not None
    before = company.finances.cash

    book(company).acquire(target, day=1)

    assert company.finances.cash == before - price


def test_personal_money_is_never_touched():
    """V12.4, V1.4: acquisitions use company money only."""
    player, company, market, world, _ = build()
    target = cheapest(market, world)
    personal = player.cash

    book(company).acquire(target, day=1)

    assert player.cash == personal


def test_buying_a_company_is_not_an_expense():
    """It is an exchange of cash for an asset, like any investment (V17.26)."""
    _, company, market, world, _ = build()
    target = cheapest(market, world)

    book(company).acquire(target, day=1)

    assert company.finances.ledger.lifetime.expenses.is_zero


def test_an_unaffordable_acquisition_fails_gracefully():
    """V12.21: never a negative balance."""
    _, company, market, world, _ = build(capital=1_000)
    target = cheapest(market, world)

    subsidiary, reason = book(company).acquire(target, day=1)

    assert subsidiary is None
    assert "would cost" in reason
    assert company.finances.cash.is_positive
    still_free = world.company_by_id(target)
    assert still_free is not None and not still_free.is_subsidiary


def test_acquisitions_require_a_grown_company():
    """V12.15 places acquisitions among the later stages of growth."""
    _, company, market, world, _ = build(level=1)
    target = cheapest(market, world)

    allowed, reason = book(company).can_acquire(target)

    assert not allowed
    assert "Company Level" in reason


def test_acquisitions_require_subsidiaries_to_be_unlocked():
    """Subsidiaries, one unlock past Investment Funds (project manager
    ruling, 2026-08-10): a locked company cannot acquire, however grown."""
    _, company, market, world, _ = build(unlocked=False)
    target = cheapest(market, world)

    allowed, reason = book(company).can_acquire(target)

    assert not allowed
    assert "unlock" in reason.lower()
    subsidiary, _ = book(company).acquire(target, day=1)
    assert subsidiary is None


def test_a_subsidiary_owned_before_the_unlock_stays_owned():
    """Grandfathered: unlocked only gates new acquisitions, never what is
    already owned — an old save must not lose or freeze existing income."""
    _, company, market, world, _ = build()
    target = cheapest(market, world)
    subsidiary, message = book(company).acquire(target, day=1)
    assert subsidiary is not None, message

    # The unlock is later revoked (e.g. an old save with the flag defaulting
    # False), the way it would for anyone who owned subsidiaries before this
    # system existed.
    book(company).unlocked = False

    assert book(company).owns(target)
    assert book(company).total_value() == subsidiary.valuation
    another = next(c for c in market.active_listings() if c.company_id != target)
    allowed, _ = book(company).can_acquire(another.company_id)
    assert not allowed, "the gate still blocks a *new* acquisition"


def test_a_company_cannot_be_owned_twice():
    _, company, market, world, _ = build()
    target = cheapest(market, world)
    book(company).acquire(target, day=1)

    allowed, reason = book(company).can_acquire(target)

    assert not allowed
    assert "already" in reason


def test_an_acquired_company_stops_trading():
    """Project manager ruling: owning it outright leaves nothing to trade."""
    _, company, market, world, _ = build()
    target = cheapest(market, world)

    book(company).acquire(target, day=1)

    listing = market.listing_for(target)
    assert listing is not None and listing.delisted
    assert target not in {listing.company_id for listing in market.active_listings()}


# -- what a subsidiary does (V12.5, V12.11) -------------------------------


def test_a_subsidiary_keeps_its_own_industry():
    """V12.5: it does not merge into the parent."""
    _, company, market, world, _ = build()
    target = cheapest(market, world)
    record = world.company_by_id(target)
    assert record is not None
    industry = record.industry.value

    subsidiary = buy(company, target)

    assert subsidiary.industry == industry


def test_subsidiaries_count_toward_company_value():
    """V12.11, V17.12."""
    _, company, market, world, _ = build()
    target = cheapest(market, world)
    before = company.finances.assets()

    book(company).acquire(target, day=1)

    # Cash became an asset of equal worth, so nothing was created or destroyed.
    assert company.finances.assets() == before
    assert book(company).total_value().is_positive


def test_a_subsidiary_pays_income_to_its_parent():
    """V12.5: ongoing operations are an additional stream of income."""
    _, company, market, world, engine = build()
    target = cheapest(market, world)
    subsidiary = buy(company, target)

    engine.run_days(336)

    assert subsidiary.lifetime_income.is_positive
    assert company.finances.ledger.lifetime.revenue.is_positive


def test_income_is_revenue_rather_than_financing():
    """The group genuinely earned it (V17.26)."""
    _, company, market, world, engine = build()
    book(company).acquire(cheapest(market, world), day=1)

    engine.run_days(90)

    categories = {
        entry.category for entry in company.finances.ledger.entries
    }
    assert any("Subsidiary" in str(category) for category in categories)


# -- persistence (V16.11) -------------------------------------------------


def test_subsidiaries_survive_a_round_trip():
    _, company, market, world, engine = build()
    book(company).acquire(cheapest(market, world), day=1)
    engine.run_days(90)
    before = [s.state() for s in book(company)]

    book(company).restore(book(company).state())

    assert [s.state() for s in book(company)] == before


def test_a_group_reports_what_it_is_worth_and_has_paid():
    _, company, market, world, engine = build()
    book(company).acquire(cheapest(market, world), day=1)
    engine.run_days(200)

    owned = book(company)
    assert len(owned) == 1
    assert owned.total_value().is_positive
    assert owned.total_income().is_positive
    assert owned.by_id(next(iter(owned)).company_id) is not None
