"""Tests for personal investing (Design Bible V1.4, V1.19, V1.20, V3.4).

The player is an individual investor before they are a CEO, and may remain one
indefinitely. These tests hold that opening in place: trading with personal
money, without a company, from the first day.
"""

from __future__ import annotations

from random import Random

import pytest

from apex_horizon.engine.company import Player
from apex_horizon.engine.market import MarketSystem
from apex_horizon.engine.unlocks import CREATE_COMPANY
from apex_horizon.engine.values import Calendar, Money, set_calendar
from apex_horizon.engine.world import generate_world


@pytest.fixture(autouse=True)
def _shared_calendar():
    set_calendar(Calendar(days_per_week=7, weeks_per_month=4, months_per_year=12))
    yield
    set_calendar(None)


def build(cash: int = 10_000, seed: int = 2026):
    world, allocator, _ = generate_world(seed)
    market = MarketSystem(world)
    market.populate(Random(seed))
    player = Player("Founder", cash=Money(cash), allocator=allocator)
    portfolio = player.attach_market(market)
    return player, portfolio, market


# -- the opening (V1.19) --------------------------------------------------


def test_a_new_player_can_invest_without_a_company():
    """V1.20: a player may remain an individual investor indefinitely."""
    player, portfolio, market = build()
    listing = market.active_listings()[0]

    assert player.company is None
    ok, message = portfolio.buy(listing.company_id, 10, day=1)

    assert ok, message
    assert portfolio.shares_of(listing.company_id) == 10


def test_buying_spends_personal_cash_only():
    player, portfolio, market = build()
    listing = market.active_listings()[0]
    before = player.cash

    portfolio.buy(listing.company_id, 5, day=1)

    spent = before - player.cash
    assert spent == Money(listing.price.amount * 5)


def test_a_player_cannot_spend_money_they_do_not_have():
    player, portfolio, market = build(cash=100)
    listing = market.active_listings()[0]

    ok, reason = portfolio.buy(listing.company_id, 1_000, day=1)

    assert not ok
    assert "you have" in reason.lower()
    assert player.cash == Money(100)


def test_a_player_cannot_sell_shares_they_do_not_hold():
    _, portfolio, market = build()
    listing = market.active_listings()[0]

    ok, reason = portfolio.sell(listing.company_id, 5, day=1)

    assert not ok
    assert "hold 0" in reason


# -- profit and loss ------------------------------------------------------


def test_selling_returns_cash_and_books_the_gain():
    player, portfolio, market = build(cash=100_000)
    listing = market.active_listings()[0]
    portfolio.buy(listing.company_id, 10, day=1)
    cash_after_buying = player.cash

    listing.price = Money(listing.price.amount * 2)  # the price doubles
    ok, message = portfolio.sell(listing.company_id, 10, day=2)

    assert ok, message
    assert player.cash > cash_after_buying
    assert portfolio.realised.is_positive
    assert portfolio.shares_of(listing.company_id) == 0


def test_selling_part_of_a_holding_leaves_the_rest_carrying_its_own_cost():
    _, portfolio, market = build(cash=100_000)
    listing = market.active_listings()[0]
    portfolio.buy(listing.company_id, 10, day=1)
    original = portfolio.holding_for(listing.company_id).cost_basis

    portfolio.sell(listing.company_id, 4, day=2)

    holding = portfolio.holding_for(listing.company_id)
    assert holding.shares == 6
    # Six tenths of the original outlay stays with the six remaining shares.
    assert holding.cost_basis == Money(original.amount * 6 / 10)


def test_averaging_in_keeps_one_honest_cost_basis():
    _, portfolio, market = build(cash=100_000)
    listing = market.active_listings()[0]
    first = listing.price

    portfolio.buy(listing.company_id, 10, day=1)
    listing.price = Money(first.amount * 3)
    portfolio.buy(listing.company_id, 10, day=2)

    holding = portfolio.holding_for(listing.company_id)
    assert holding.shares == 20
    # Ten at one price and ten at triple it average to twice the first.
    assert holding.average_price == Money(first.amount * 2)


def test_a_loss_is_booked_as_a_loss():
    _, portfolio, market = build(cash=100_000)
    listing = market.active_listings()[0]
    portfolio.buy(listing.company_id, 10, day=1)

    listing.price = Money(listing.price.amount / 2)
    portfolio.sell(listing.company_id, 10, day=2)

    assert portfolio.realised.is_negative


# -- the market notices (V4.8) --------------------------------------------


def test_a_personal_order_reaches_the_market():
    """Personal buying pushes a price like any other demand (V4.8)."""
    _, portfolio, market = build(cash=100_000)
    listing = market.active_listings()[0]

    portfolio.buy(listing.company_id, 25, day=1)
    assert listing.pending_demand == 25

    portfolio.sell(listing.company_id, 10, day=1)
    assert listing.pending_demand == 15


# -- net worth (V1.6) -----------------------------------------------------


def test_holdings_count_toward_personal_net_worth():
    player, portfolio, market = build(cash=100_000)
    listing = market.active_listings()[0]
    before = player.net_worth()

    portfolio.buy(listing.company_id, 10, day=1)

    # Cash became shares; nothing was created or destroyed.
    assert player.net_worth() == before
    assert player.holdings_value().is_positive


def test_personal_money_is_never_company_money():
    """V1.4, V3.4: two separate financial systems that must not merge."""
    player, portfolio, market = build(cash=100_000)
    player.unlocks.unlock(CREATE_COMPANY)
    company, _ = player.found_company("Test Capital", day=1)
    listing = market.active_listings()[0]
    company_cash_before = company.finances.cash

    portfolio.buy(listing.company_id, 10, day=1)

    assert company.finances.cash == company_cash_before
    assert company.investments is None or not company.investments.open_positions()


# -- persistence (V16.11) -------------------------------------------------


def test_a_portfolio_survives_a_round_trip():
    player, portfolio, market = build(cash=100_000)
    listing = market.active_listings()[0]
    portfolio.buy(listing.company_id, 10, day=1)
    portfolio.sell(listing.company_id, 4, day=2)

    restored_player = Player("Founder", allocator=player.allocator)
    restored_player.restore(player.state())
    restored = restored_player.attach_market(market)

    assert restored.shares_of(listing.company_id) == 6
    assert restored.realised == portfolio.realised
    assert len(restored.trades) == len(portfolio.trades)
    assert restored.value() == portfolio.value()


def test_statistics_report_what_the_player_has_done():
    _, portfolio, market = build(cash=100_000)
    listing = market.active_listings()[0]
    portfolio.buy(listing.company_id, 10, day=1)
    listing.price = Money(listing.price.amount * 2)
    portfolio.sell(listing.company_id, 10, day=2)

    stats = portfolio.statistics()
    assert stats["Trades"] == 2
    assert stats["Companies held"] == 0
    assert stats["Realised"].is_positive
    assert stats["Win rate"] == "100.00%"
