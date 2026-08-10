"""Long-term evolution, determinism, persistence and the day's top movers."""

from __future__ import annotations

from random import Random

import pytest
from market_support import build_market

from apex_horizon.engine.market import MarketSystem
from apex_horizon.engine.market.listing import PriceChange
from apex_horizon.engine.simulation import SimulationClock, SimulationEngine
from apex_horizon.engine.values import Money, Percentage
from apex_horizon.engine.world import generate_world

# -- long-term evolution (V4.14) ------------------------------------------


def test_collapsed_companies_are_delisted_after_a_grace_period():
    market, engine = build_market()
    listing = next(iter(market.listings.values()))
    listing.price = Money("0.05")
    listing.performance = -1.0
    listing.volatility = Percentage("0.0001")
    engine.run_days(40)
    assert listing.delisted
    assert listing.delisted_on_day is not None
    assert listing not in market.active_listings()


def test_a_brief_dip_does_not_delist_a_company():
    market, engine = build_market()
    listing = next(iter(market.listings.values()))
    listing.price = Money("0.10")
    engine.run_days(3)
    listing.price = Money(50)
    engine.run_days(3)
    assert listing.days_below_floor == 0
    assert not listing.delisted


def test_delisted_companies_stop_trading():
    market, engine = build_market()
    listing = next(iter(market.listings.values()))
    listing.delisted = True
    frozen = listing.price
    engine.run_days(10)
    assert listing.price == frozen


def test_new_companies_can_list_over_time():
    # V4.14: the market should keep generating new opportunities.
    world, allocator, names = generate_world(77)
    from apex_horizon.engine.world import WorldGenerator

    generator = WorldGenerator(Random(77), allocator=allocator, names=names)
    market = MarketSystem(world, generator=generator)
    market.populate(Random(77))
    clock = SimulationClock(
        seconds_per_day=1.0, speed=1, speed_options=(1,), max_days_per_update=10_000
    )
    engine = SimulationEngine(clock=clock, seed=77)
    market.register(engine)

    before = len(market.listings)
    engine.run_days(365 * 2)
    assert len(market.listings) > before
    # Newly listed companies are real world entities with names and industries.
    for listing in market.listings.values():
        assert market.world.company_by_id(listing.company_id) is not None


def test_listing_count_respects_its_ceiling():
    from apex_horizon.engine.world import WorldGenerator

    world, allocator, names = generate_world(21)
    generator = WorldGenerator(Random(21), allocator=allocator, names=names)
    market = MarketSystem(world, generator=generator)
    market.populate(Random(21))
    clock = SimulationClock(
        seconds_per_day=1.0, speed=1, speed_options=(1,), max_days_per_update=10_000
    )
    engine = SimulationEngine(clock=clock, seed=21)
    market.register(engine)
    # The ceiling is reached within about five in-game years, so eight is ample
    # to prove it holds without making the suite slow.
    engine.run_days(336 * 8)
    ceiling = market.config.get_int("market.max_listings")
    assert len(market.active_listings()) == ceiling


# -- determinism and persistence (V4.22, V15.11) --------------------------


def test_same_seed_produces_the_same_market():
    def sample(seed: int) -> list[str]:
        market, engine = build_market(seed)
        engine.run_days(120)
        return [str(listing.price.amount) for listing in market.listings.values()]

    assert sample(99) == sample(99)
    assert sample(99) != sample(100)


def test_retried_phase_does_not_move_prices_twice():
    # Simulation handlers must be retry-safe (V15.26).
    market, engine = build_market()
    listing = next(iter(market.listings.values()))
    engine.run_days(1)
    price_after_one_day = listing.price
    history_length = len(listing.history)

    # Re-running the same day, as a retry would.
    from apex_horizon.engine.simulation import SimulationContext

    context = SimulationContext(date=engine.date - 1, rng=engine.rng, day_number=1, tick=0)
    market.update_prices(context)
    assert listing.price == price_after_one_day
    assert len(listing.history) == history_length


def test_state_round_trip_restores_the_market_exactly():
    market, engine = build_market()
    engine.run_days(100)
    saved = market.state()

    restored = MarketSystem(market.world)
    restored.restore(saved)

    assert restored.sentiment == market.sentiment
    assert restored.industry_trends == market.industry_trends
    for company_id, listing in market.listings.items():
        other = restored.listings[company_id]
        assert other.price == listing.price
        assert other.shares_outstanding == listing.shares_outstanding
        # V4.22: price history is saved in its entirety.
        assert list(other.history) == list(listing.history)
        assert other.performance == pytest.approx(listing.performance)
        assert other.delisted == listing.delisted


def test_restored_market_continues_identically():
    market, engine = build_market(seed=55)
    engine.run_days(50)
    saved = market.state()
    engine_state = engine.state()

    market_continued = MarketSystem(market.world)
    market_continued.restore(saved)
    clock = SimulationClock(
        seconds_per_day=1.0, speed=1, speed_options=(1,), max_days_per_update=10_000
    )
    engine_continued = SimulationEngine(clock=clock, seed=55)
    engine_continued.restore(engine_state)
    market_continued.register(engine_continued)

    engine.run_days(20)
    engine_continued.run_days(20)

    for company_id, listing in market.listings.items():
        assert market_continued.listings[company_id].price == listing.price


def test_price_change_defaults_are_zero():
    change = PriceChange()
    assert change.total.is_zero
    assert change.dominant_cause() in {"company performance", "industry conditions",
                                       "market sentiment", "supply and demand",
                                       "ordinary variation"}


# -- the day's top gainer (V4.15) -----------------------------------------


def _fix_change(listing, fraction: str) -> None:
    """Force a listing to show an exact change against yesterday's close.

    ``previous_close`` is the entry *before* the last, since the last is today's
    close (V4.22), so both are written rather than one appended.
    """
    from decimal import Decimal

    today = Money(Decimal(100) * (1 + Decimal(fraction)))
    while len(listing.history) < 2:
        listing.history.append(Money(100))
    listing.history[-2] = Money(100)
    listing.history[-1] = today
    listing.price = today


def test_the_top_gainer_is_the_largest_actual_rise():
    """Chosen from real price movement, never at random."""
    market, _ = build_market()
    listings = market.active_listings()[:4]
    for listing, change in zip(listings, ("0.024", "0.078", "-0.012", "0.041"),
                               strict=True):
        _fix_change(listing, change)
    for other in market.active_listings()[4:]:
        _fix_change(other, "0")

    assert market.top_gainer() is listings[1], "the +7.8% company must win"


def test_the_top_gainer_is_not_merely_the_highest_price():
    """Ranked on movement, not on the size of the price (V4.15)."""
    market, _ = build_market()
    expensive, riser = market.active_listings()[:2]
    for other in market.active_listings():
        _fix_change(other, "0")

    # Dear, but unchanged: both closes are the same, so it has not moved.
    expensive.history[-2] = Money(10_000)
    expensive.history[-1] = Money(10_000)
    expensive.price = Money(10_000)
    _fix_change(riser, "0.05")

    assert expensive.price > riser.price
    assert market.top_gainer() is riser


def test_the_top_gainer_changes_when_the_market_does():
    market, _ = build_market()
    first, second = market.active_listings()[:2]
    for other in market.active_listings():
        _fix_change(other, "0")
    _fix_change(first, "0.03")
    assert market.top_gainer() is first

    _fix_change(second, "0.09")
    assert market.top_gainer() is second


def test_a_market_where_nothing_rose_has_no_top_gainer():
    """The least bad loser is not a gainer."""
    market, _ = build_market()
    for listing in market.active_listings():
        _fix_change(listing, "-0.03")

    assert market.top_gainer() is None


def test_a_flat_market_has_no_top_gainer():
    market, _ = build_market()
    for listing in market.active_listings():
        _fix_change(listing, "0")

    assert market.top_gainer() is None


def test_a_tie_is_broken_deterministically():
    """Never at random: the same market always gives the same answer."""
    market, _ = build_market()
    for other in market.active_listings():
        _fix_change(other, "0")
    tied = market.active_listings()[:3]
    for listing in tied:
        _fix_change(listing, "0.05")

    picks = [market.top_gainer() for _ in range(20)]
    assert all(pick is not None for pick in picks)
    answers = {pick.company_id for pick in picks if pick}
    assert len(answers) == 1
    # And it is a company that genuinely tied for the lead.
    assert answers.pop() in {listing.company_id for listing in tied}


def test_top_movers_never_consults_the_random_generator(monkeypatch):
    """A guard against randomness creeping back into the ranking."""
    market, engine = build_market()
    for listing in market.active_listings():
        _fix_change(listing, "0.01")

    def explode(*args, **kwargs):  # pragma: no cover - only runs on failure
        raise AssertionError("ranking must not use randomness")

    monkeypatch.setattr(engine.rng, "random", explode)
    monkeypatch.setattr(engine.rng, "choice", explode)
    monkeypatch.setattr(engine.rng, "shuffle", explode)

    assert market.top_gainer() is not None
    gainers, losers = market.top_movers(3)
    assert len(gainers) == 3 and len(losers) == 3


def test_top_movers_are_measured_over_the_configured_period():
    """V4.15: a defined period, not whatever happened in the last second."""
    market, _ = build_market()
    assert market.top_mover_period > 1

    listing = market.active_listings()[0]
    period = market.top_mover_period

    # Flat for a day, but a tenth lower than it was a week ago: the period is
    # what decides, not the last session.
    listing.history.clear()
    for _ in range(period + 2):
        listing.history.append(Money(100))
    listing.history.append(Money(90))
    listing.price = Money(90)

    assert listing.daily_change().is_negative
    assert market.change_over_period(listing) == listing.change_over(period)
    assert float(market.change_over_period(listing).fraction) == pytest.approx(-0.10)


def test_the_top_loser_is_the_largest_actual_fall():
    market, _ = build_market()
    listings = market.active_listings()[:4]
    for other in market.active_listings():
        _fix_change(other, "0")
    for listing, change in zip(listings, ("0.021", "0.084", "-0.032", "-0.071"),
                               strict=True):
        _fix_change(listing, change)

    assert market.top_gainer() is listings[1], "+8.4% wins"
    assert market.top_loser() is listings[3], "-7.1% loses"


def test_a_market_where_nothing_fell_has_no_top_loser():
    market, _ = build_market()
    for listing in market.active_listings():
        _fix_change(listing, "0.02")

    assert market.top_loser() is None


def test_company_order_never_changes():
    """A company holds its place however the market moves."""
    market, engine = build_market()
    before = [listing.company_id for listing in market.active_listings()]

    engine.run_days(200)

    after = [listing.company_id for listing in market.active_listings()]
    assert after[: len(before)] == [c for c in before if c in set(after)][: len(before)]
    # And repeated reads never differ.
    assert [listing.company_id for listing in market.active_listings()] == after


def test_company_order_survives_a_reload():
    market, engine = build_market()
    engine.run_days(120)
    before = [listing.company_id for listing in market.active_listings()]

    restored = MarketSystem(market.world)
    restored.restore(market.state())

    assert [listing.company_id for listing in restored.active_listings()] == before
