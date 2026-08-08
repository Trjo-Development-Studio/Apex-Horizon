"""Tests for the news system (Design Bible Volume 10)."""

from __future__ import annotations

from random import Random

import pytest

from apex_horizon.engine.economy import EconomySystem
from apex_horizon.engine.market import MarketSystem
from apex_horizon.engine.news import NewsArticle, NewsSystem, NewsTier
from apex_horizon.engine.simulation import (
    SimulationClock,
    SimulationContext,
    SimulationEngine,
)
from apex_horizon.engine.values import Calendar, Money, Percentage, set_calendar
from apex_horizon.engine.world import generate_world


@pytest.fixture(autouse=True)
def _shared_calendar():
    set_calendar(Calendar(days_per_week=7, weeks_per_month=4, months_per_year=12))
    yield
    set_calendar(None)


def context_for(engine: SimulationEngine) -> SimulationContext:
    return SimulationContext(
        date=engine.date, rng=engine.rng, day_number=engine.date.day, tick=engine.tick
    )


def build(seed: int = 2026) -> tuple[NewsSystem, MarketSystem, SimulationEngine]:
    world, allocator, _ = generate_world(seed)
    economy = EconomySystem()
    market = MarketSystem(world, economy=economy)
    market.populate(Random(seed))
    news = NewsSystem(world, market, economy, allocator=allocator)
    market.news = news
    clock = SimulationClock(
        seconds_per_day=1.0, speed=1, speed_options=(1, 2, 3), max_days_per_update=10_000
    )
    engine = SimulationEngine(clock=clock, seed=seed)
    news.register(engine)
    economy.register(engine)
    market.register(engine)
    return news, market, engine


def move_price(listing, fraction: float) -> None:
    """Force a listing to have moved by ``fraction`` since yesterday."""
    opening = listing.price
    listing.history.append(opening)
    listing.price = Money(opening.amount * (1 + Percentage(fraction).fraction))


def test_a_large_move_is_reported():
    news, market, engine = build()
    listing = market.active_listings()[0]
    move_price(listing, 0.05)

    engine.run_days(1)

    assert news.articles, "a move past the reporting threshold should produce a story"
    assert any(a.company_id == listing.company_id for a in news.articles)


def test_an_ordinary_move_is_not_reported():
    """V10.9: news reports what happened, so a quiet day has nothing to say."""
    news, market, engine = build()
    for listing in market.active_listings():
        listing.history.append(listing.price)  # no change at all

    engine.run_days(1)

    company_news = [a for a in news.articles if a.tier is NewsTier.BASIC]
    assert not company_news


def test_breaking_news_is_withheld_until_it_is_unlocked():
    """V10.16: the biggest stories belong to the Breaking tier."""
    news, market, engine = build()
    listing = market.active_listings()[0]
    move_price(listing, 0.30)

    engine.run_days(1)
    assert not [a for a in news.articles if a.company_id == listing.company_id]

    news.tier = NewsTier.BREAKING
    news._last_generated_day = None
    move_price(listing, 0.30)
    news.generate(context_for(engine))

    breaking = [a for a in news.articles if a.is_breaking]
    assert breaking and breaking[0].tier is NewsTier.BREAKING


def test_a_headline_states_the_size_of_a_fall_without_a_double_negative():
    """"slides 4.9%", never "slides -4.9%" — the template supplies the direction."""
    news, market, engine = build()
    listing = market.active_listings()[0]
    move_price(listing, -0.05)

    engine.run_days(1)

    falls = [a for a in news.articles if a.company_id == listing.company_id]
    assert falls
    assert "-" not in falls[0].headline


def test_a_story_pushes_the_price_it_concerns():
    """V10.10: news is one of the causes of price movement (V4.4)."""
    news, market, engine = build()
    listing = market.active_listings()[0]
    move_price(listing, 0.05)

    engine.run_days(1)

    assert news.impact_for(listing.company_id) > 0
    assert market._news_influence(listing.company_id) > 0

    # And it fades rather than pushing forever.
    before = news.impact_for(listing.company_id)
    news._decay_impacts()
    assert news.impact_for(listing.company_id) < before


def test_news_appears_as_a_named_cause_of_a_price_change():
    _, market, engine = build()
    listing = market.active_listings()[0]
    move_price(listing, 0.05)
    engine.run_days(2)

    assert listing.last_change.news is not None


def test_the_archive_is_capped():
    """V10.15 keeps past stories readable, but not without limit."""
    news, _, engine = build()
    limit = news.config.get_int("news.archive_size")
    for day in range(limit + 40):
        news.articles.append(NewsArticle(
            id=f"news-{day}", day=day, tier=NewsTier.BASIC,
            headline="Something happened", body="", agency="The Register",
        ))
    news._last_generated_day = None
    news.generate(context_for(engine))

    assert len(news.articles) <= limit


def test_only_unlocked_tiers_are_offered():
    news, _, _ = build()
    assert news.available_tiers == [NewsTier.BASIC]

    news.tier = NewsTier.ECONOMIC
    assert NewsTier.MARKET in news.available_tiers
    assert NewsTier.BREAKING not in news.available_tiers


def test_state_survives_a_round_trip():
    news, market, engine = build()
    listing = market.active_listings()[0]
    move_price(listing, 0.05)
    engine.run_days(1)
    news.tier = NewsTier.MARKET

    restored = NewsSystem(news.world, market, news.economy)
    restored.restore(news.state())

    assert len(restored.articles) == len(news.articles)
    assert restored.tier is NewsTier.MARKET
    assert restored.impacts == news.impacts
    assert restored.articles[0].headline == news.articles[0].headline


def test_every_article_carries_a_byline_from_the_world():
    """V33.10: stories come from the world's own news agencies."""
    news, market, engine = build()
    for listing in market.active_listings()[:5]:
        move_price(listing, 0.05)
    engine.run_days(1)

    agencies = {agency.name for agency in news.world.news_agencies}
    assert news.articles
    assert all(article.agency in agencies for article in news.articles)


def test_the_breaking_threshold_is_reachable():
    """A tier the market can never trigger would make its unlock worthless.

    The breaking threshold is sized against what prices actually do, not against
    the clamp in [market]: over 45,733 observed daily moves the largest was
    7.23%, so a double-digit threshold would never once fire.
    """
    news, _, _ = build()
    threshold = news.config.get_float("news.breaking_move_threshold")
    largest_observed = 0.0723

    assert threshold < largest_observed
    assert threshold > news.config.get_float("news.company_move_threshold")
