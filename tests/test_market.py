"""Tests for the market system (Design Bible Volume 4)."""

from __future__ import annotations

from random import Random

import pytest

from apex_horizon.engine.market import MINIMUM_PRICE, MarketSystem, PricingWeights, compute_change
from apex_horizon.engine.market.listing import MarketListing, PriceChange
from apex_horizon.engine.simulation import SimulationClock, SimulationEngine
from apex_horizon.engine.values import Calendar, Money, Percentage, set_calendar
from apex_horizon.engine.world import Industry, generate_world


@pytest.fixture(autouse=True)
def _shared_calendar():
    set_calendar(Calendar(days_per_week=7, weeks_per_month=4, months_per_year=12))
    yield
    set_calendar(None)


def build_market(seed: int = 2026) -> tuple[MarketSystem, SimulationEngine]:
    world, _, _ = generate_world(seed)
    market = MarketSystem(world)
    market.populate(Random(seed))
    clock = SimulationClock(
        seconds_per_day=1.0, speed=1, speed_options=(1, 2, 3), max_days_per_update=10_000
    )
    engine = SimulationEngine(clock=clock, seed=seed)
    market.register(engine)
    return market, engine


# -- opening state (V4.3) -------------------------------------------------


def test_every_company_gets_a_listing():
    market, _ = build_market()
    assert len(market.listings) == len(market.world.companies)
    for listing in market.listings.values():
        assert listing.price.is_positive
        assert listing.shares_outstanding > 0
        assert listing.market_cap.is_positive
        assert len(listing.history) == 1


def test_listings_vary_in_price_and_size():
    # A market where every company looked identical would not feel believable.
    market, _ = build_market()
    prices = {listing.price for listing in market.listings.values()}
    caps = {listing.shares_outstanding for listing in market.listings.values()}
    assert len(prices) > 20
    assert len(caps) > 20


# -- daily movement (V4.4, V13.14) ----------------------------------------


def test_prices_move_each_day():
    market, engine = build_market()
    before = {cid: listing.price for cid, listing in market.listings.items()}
    engine.run_days(1)
    after = {cid: listing.price for cid, listing in market.listings.items()}
    assert sum(1 for cid in before if before[cid] != after[cid]) > len(before) // 2


def test_price_movement_is_broken_down_by_cause():
    # V4.4 / V4.21: every movement must have a traceable explanation.
    market, engine = build_market()
    engine.run_days(1)
    listing = next(iter(market.listings.values()))
    change = listing.last_change
    parts = (
        change.performance.fraction
        + change.industry.fraction
        + change.sentiment.fraction
        + change.supply_demand.fraction
        + change.variation.fraction
    )
    # The total is the sum of its causes (before clamping).
    assert change.total.fraction == pytest.approx(parts, abs=1e-9)
    assert change.dominant_cause() in {
        "company performance", "industry conditions", "market sentiment",
        "supply and demand", "ordinary variation",
    }


def test_daily_movement_is_bounded():
    # No combination of causes may produce an implausible overnight jump.
    market, engine = build_market()
    limit = float(market.weights.max_daily_change)
    engine.run_days(200)
    for listing in market.listings.values():
        assert abs(float(listing.last_change.total.fraction)) <= limit + 1e-9


def test_strong_companies_outperform_weak_ones_over_time():
    # V4.11: strong companies generally grow, weak ones struggle.
    market, engine = build_market(seed=11)
    listings = list(market.listings.values())
    for index, listing in enumerate(listings):
        listing.performance = 0.9 if index % 2 == 0 else -0.9
        listing.volatility = Percentage("0.002")  # isolate the performance signal
    starts = {listing.company_id: listing.price for listing in listings}

    engine.run_days(365)

    strong = [listings[i] for i in range(0, len(listings), 2)]
    weak = [listings[i] for i in range(1, len(listings), 2)]
    strong_growth = sum(float(x.price / starts[x.company_id]) for x in strong) / len(strong)
    weak_growth = sum(float(x.price / starts[x.company_id]) for x in weak) / len(weak)
    assert strong_growth > weak_growth


def test_price_never_falls_below_the_minimum():
    market, engine = build_market()
    for listing in market.listings.values():
        listing.price = Money("0.02")
        listing.performance = -1.0
    engine.run_days(20)
    assert all(listing.price >= MINIMUM_PRICE for listing in market.listings.values())


# -- supply and demand (V4.8) ---------------------------------------------


def test_buying_pressure_lifts_a_price_relative_to_selling_pressure():
    market, engine = build_market(seed=3)
    listings = list(market.listings.values())
    bought, sold = listings[0], listings[1]
    for listing in (bought, sold):
        listing.price = Money(100)
        listing.performance = 0.0
        listing.volatility = Percentage("0.0001")
    market.sentiment = 0.0

    # Equal and opposite pressure, as a fraction of each company's shares.
    market.record_demand(bought.company_id, bought.shares_outstanding // 10)
    market.record_demand(sold.company_id, -(sold.shares_outstanding // 10))
    engine.run_days(1)

    assert bought.last_change.supply_demand.fraction > 0
    assert sold.last_change.supply_demand.fraction < 0
    assert bought.price > sold.price


def test_pressure_is_consumed_by_the_price_it_produces():
    market, engine = build_market()
    listing = next(iter(market.listings.values()))
    market.record_demand(listing.company_id, 10_000)
    engine.run_days(1)
    assert listing.pending_demand == 0


def test_the_same_order_moves_a_small_company_more_than_a_large_one():
    weights = PricingWeights.from_config()
    small = MarketListing("a", Money(100), 1_000_000, Percentage("0.0"))
    large = MarketListing("b", Money(100), 100_000_000, Percentage("0.0"))
    for listing in (small, large):
        listing.add_demand(500_000)
    rng = Random(0)
    small_change = compute_change(small, industry_trend=0, sentiment=0, rng=rng, weights=weights)
    large_change = compute_change(large, industry_trend=0, sentiment=0, rng=rng, weights=weights)
    assert small_change.supply_demand.fraction > large_change.supply_demand.fraction


def test_demand_for_an_unknown_or_delisted_company_is_ignored():
    market, _ = build_market()
    market.record_demand("company-999999", 1000)  # must not raise
    listing = next(iter(market.listings.values()))
    listing.delisted = True
    market.record_demand(listing.company_id, 1000)
    assert listing.pending_demand == 0


# -- market-wide behaviour (V4.5, V4.12) ----------------------------------


def test_sentiment_stays_bounded_and_moves():
    market, engine = build_market(seed=5)
    seen = set()
    for _ in range(200):
        engine.run_days(1)
        seen.add(round(market.sentiment, 4))
        assert -1.0 <= market.sentiment <= 1.0
    assert len(seen) > 50


def test_bull_and_bear_markets_both_occur_over_time():
    market, engine = build_market(seed=8)
    moods = set()
    for _ in range(600):
        engine.run_days(1)
        if market.is_bull_market():
            moods.add("bull")
        if market.is_bear_market():
            moods.add("bear")
    assert moods == {"bull", "bear"}


def test_industries_diverge_from_one_another():
    # V4.5 / V4.12: different industries perform differently in the same period.
    market, engine = build_market(seed=4)
    engine.run_days(365)
    trends = [market.industry_trends[industry] for industry in Industry]
    assert max(trends) - min(trends) > 0.1


def test_industry_performance_reports_a_percentage():
    market, engine = build_market()
    engine.run_days(60)
    value = market.industry_performance(Industry.TECHNOLOGY, days=28)
    assert isinstance(value, Percentage)


def test_industry_performance_without_listings_is_zero():
    market, _ = build_market()
    market.listings.clear()
    assert market.industry_performance(Industry.MINING).is_zero


# -- statistics and access (V4.15) ----------------------------------------


def test_market_index_starts_at_1000_and_then_moves():
    market, engine = build_market()
    assert market.market_index() == pytest.approx(1000.0)
    engine.run_days(90)
    assert market.market_index() != pytest.approx(1000.0)


def test_top_movers_are_ranked():
    market, engine = build_market()
    engine.run_days(5)
    gainers, losers = market.top_movers(3)
    assert len(gainers) == 3 and len(losers) == 3
    assert gainers[0].daily_change() >= gainers[-1].daily_change()
    assert losers[0].daily_change() <= losers[-1].daily_change()


def test_history_supports_past_prices_and_ranged_change():
    market, engine = build_market()
    listing = next(iter(market.listings.values()))
    engine.run_days(30)
    assert listing.price_on(1) is not None
    assert listing.price_on(0) is None
    assert listing.price_on(10_000) is None
    assert isinstance(listing.change_over(7), Percentage)


def test_history_is_bounded_so_saves_cannot_grow_without_limit():
    market, engine = build_market()
    listing = next(iter(market.listings.values()))
    cap = listing.history.maxlen
    engine.run_days(cap + 100)
    assert len(listing.history) == cap


def test_explanation_is_human_readable():
    market, engine = build_market()
    engine.run_days(1)
    company = market.world.companies[0]
    text = market.explain(company.id)
    assert company.name in text
    assert "driven mainly by" in text
    assert market.explain("company-999999") == "No market data available."


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

    answers = {market.top_gainer().company_id for _ in range(20)}
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
    assert market.top_movers(3)
