"""Opening state, daily movement, supply and demand, and market statistics."""

from __future__ import annotations

from random import Random

import pytest
from market_support import build_market

from apex_horizon.engine.market import MINIMUM_PRICE, PricingWeights, compute_change
from apex_horizon.engine.market.listing import MarketListing
from apex_horizon.engine.values import Money, Percentage
from apex_horizon.engine.world import Industry

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
    assert cap is not None
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
