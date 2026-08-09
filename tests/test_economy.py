"""Tests for the economy and banking (Design Bible Volumes 7 and 25)."""

from __future__ import annotations

from itertools import pairwise
from random import Random

import pytest

from apex_horizon.engine.economy import (
    BankingSystem,
    EconomicState,
    EconomySystem,
    derive_state,
    industry_sensitivity,
)
from apex_horizon.engine.economy.states import INDUSTRY_SENSITIVITY
from apex_horizon.engine.market import MarketSystem
from apex_horizon.engine.simulation import SimulationClock, SimulationEngine
from apex_horizon.engine.values import Calendar, Money, Percentage, set_calendar
from apex_horizon.engine.world import ALL_INDUSTRIES, Industry, generate_world


@pytest.fixture(autouse=True)
def _shared_calendar():
    set_calendar(Calendar(days_per_week=7, weeks_per_month=4, months_per_year=12))
    yield
    set_calendar(None)


def build(seed: int = 2026):
    economy = EconomySystem()
    clock = SimulationClock(
        seconds_per_day=1.0, speed=1, speed_options=(1,), max_days_per_update=10_000
    )
    engine = SimulationEngine(clock=clock, seed=seed)
    economy.register(engine)
    return economy, engine


# -- state derivation (V7.4, V7.21) ---------------------------------------


def test_all_five_states_exist():
    assert {state.value for state in EconomicState} == {
        "Economic Growth", "Stable Economy", "Slowdown", "Recession", "Recovery",
    }


def test_state_is_derived_from_health_and_direction():
    # Health alone cannot separate a Slowdown from a Recovery: what differs is
    # the direction of travel.
    assert derive_state(0.8, 0.0) is EconomicState.GROWTH
    assert derive_state(-0.8, 0.0) is EconomicState.RECESSION
    assert derive_state(0.0, 0.0) is EconomicState.STABLE
    assert derive_state(0.1, -0.01) is EconomicState.SLOWDOWN
    assert derive_state(-0.1, 0.01) is EconomicState.RECOVERY


def test_hysteresis_prevents_flickering_on_a_threshold():
    # Sitting just below the growth line, an economy already in Growth stays
    # there rather than oscillating.
    assert derive_state(0.33, 0.0, previous=EconomicState.GROWTH) is EconomicState.GROWTH
    assert derive_state(0.33, 0.0, previous=EconomicState.STABLE) is not EconomicState.GROWTH


def test_recession_never_jumps_straight_to_growth():
    # V7.19: recovery must pass through intermediate states.
    economy, engine = build(seed=13)
    economy.health = -0.9
    economy.state = EconomicState.RECESSION
    seen = [economy.state]
    for _ in range(2000):
        engine.run_days(1)
        if economy.state is not seen[-1]:
            seen.append(economy.state)
        if economy.state is EconomicState.GROWTH:
            break
    for previous, current in pairwise(seen):
        assert not (previous is EconomicState.RECESSION and current is EconomicState.GROWTH)


# -- economic health (V7.3, V7.12) ----------------------------------------


def test_health_stays_within_bounds_over_a_long_run():
    economy, engine = build(seed=4)
    for _ in range(200):
        engine.run_days(20)
        assert -1.0 <= economy.health <= 1.0


def test_the_economy_moves_through_several_conditions_over_time():
    # V7.11: years of simulation should produce multiple economic cycles.
    economy, engine = build(seed=9)
    seen = set()
    for _ in range(60):
        engine.run_days(336)
        seen.add(economy.state)
    assert len(seen) >= 4


def test_transitions_are_recorded_for_news_to_use():
    economy, engine = build(seed=9)
    engine.run_days(336 * 5)
    assert economy.transitions
    transition = economy.transitions[-1]
    assert transition.previous is not transition.current
    assert "moved from" in transition.describe()
    assert len(economy.recent_transitions(3)) <= 3


def test_transition_history_is_bounded():
    economy, engine = build(seed=9)
    engine.run_days(336 * 40)
    assert len(economy.transitions) <= economy.MAX_TRANSITIONS


def test_economy_is_retry_safe():
    # A retried phase must not advance the economy twice (V15.26).
    economy, engine = build()
    engine.run_days(1)
    health = economy.health
    from apex_horizon.engine.simulation import SimulationContext

    context = SimulationContext(date=engine.date - 1, rng=engine.rng, day_number=1, tick=0)
    economy.update_daily(context)
    assert economy.health == health


# -- inflation (V7.5, V25.2) ----------------------------------------------


def test_inflation_stays_within_configured_bounds():
    economy, engine = build(seed=6)
    low = economy.config.get_float("economy.inflation_min")
    high = economy.config.get_float("economy.inflation_max")
    for _ in range(100):
        engine.run_days(30)
        assert low <= economy.annual_inflation <= high


def test_price_level_rises_over_a_long_playthrough():
    # V25.2: raw currency values should lose meaning over very long runs.
    economy, engine = build(seed=6)
    engine.run_days(336 * 25)
    assert economy.price_level > 1.2
    assert isinstance(economy.inflation, Percentage)


def test_inflation_is_higher_in_a_boom_than_in_a_slump():
    strong, strong_engine = build(seed=2)
    strong.health = 0.9
    weak, weak_engine = build(seed=2)
    weak.health = -0.9
    # Hold each economy at its extreme so only the inflation target differs.
    for _ in range(400):
        strong.health = 0.9
        weak.health = -0.9
        strong_engine.run_days(1)
        weak_engine.run_days(1)
    assert strong.annual_inflation > weak.annual_inflation


# -- industry response (V7.6) ---------------------------------------------


def test_every_industry_has_a_documented_sensitivity():
    assert set(INDUSTRY_SENSITIVITY) == set(ALL_INDUSTRIES)
    assert all(value > 0 for value in INDUSTRY_SENSITIVITY.values())


def test_defensive_industries_move_less_than_cyclical_ones():
    economy, _ = build()
    economy.health = -0.8
    healthcare = economy.industry_condition(Industry.HEALTHCARE)
    construction = economy.industry_condition(Industry.CONSTRUCTION)
    # Both suffer in a downturn, but construction far more (V4.21).
    assert construction < healthcare < 0
    assert industry_sensitivity(Industry.CONSTRUCTION) > industry_sensitivity(Industry.HEALTHCARE)


def test_industry_condition_is_bounded():
    economy, _ = build()
    economy.health = 1.0
    assert all(-1.0 <= economy.industry_condition(i) <= 1.0 for i in ALL_INDUSTRIES)


# -- banking (V7.10, V25.3) -----------------------------------------------


def build_banking(seed: int = 5):
    world, _, _ = generate_world(seed)
    economy, engine = build(seed)
    banking = BankingSystem(world, economy)
    banking.populate(Random(seed))
    banking.register(engine)
    return world, economy, banking, engine


def test_every_bank_gets_a_profile():
    world, _, banking, _ = build_banking()
    assert len(banking.profiles) == len(world.banks)


def test_borrowing_is_cheaper_in_a_strong_economy():
    _, economy, banking, _ = build_banking()
    economy.health = 0.9
    strong = banking.interest_rate()
    economy.health = -0.9
    weak = banking.interest_rate()
    assert strong < weak


def test_banks_lend_more_in_a_strong_economy():
    _, economy, banking, _ = build_banking()
    economy.health = 0.9
    generous = banking.lending_multiple()
    economy.health = -0.9
    cautious = banking.lending_multiple()
    assert generous > cautious


def test_trust_requirements_tighten_in_a_downturn():
    # V7.19: refinancing becomes harder exactly when it is most needed.
    _, economy, banking, _ = build_banking()
    economy.health = 0.9
    easy = banking.trust_requirement()
    economy.health = -0.9
    hard = banking.trust_requirement()
    assert hard > easy


def test_reputation_decides_which_banks_will_lend():
    # V33.4: bank tiers make company reputation meaningful.
    _, economy, banking, _ = build_banking()
    economy.health = 0.0
    poor = banking.offers(company_value=Money(1_000_000), reputation=0.05)
    strong = banking.offers(company_value=Money(1_000_000), reputation=0.95)
    assert sum(1 for t in strong if t.available) > sum(1 for t in poor if t.available)


def test_best_offer_is_the_cheapest_available():
    _, _, banking, _ = build_banking()
    offers = banking.offers(company_value=Money(1_000_000), reputation=0.9)
    best = banking.best_offer(company_value=Money(1_000_000), reputation=0.9)
    available = [t for t in offers if t.available]
    assert best is not None
    assert best.interest_rate == min(t.interest_rate for t in available)


def test_no_offer_when_reputation_is_too_low():
    _, economy, banking, _ = build_banking()
    economy.health = -1.0
    assert banking.best_offer(company_value=Money(1_000_000), reputation=0.0) is None


def test_maximum_loan_scales_with_company_value():
    _, _, banking, _ = build_banking()
    small = banking.best_offer(company_value=Money(100_000), reputation=0.9)
    large = banking.best_offer(company_value=Money(10_000_000), reputation=0.9)
    assert large is not None and small is not None
    assert large.maximum_loan > small.maximum_loan


def test_terms_describe_themselves():
    _, _, banking, _ = build_banking()
    terms = banking.offers(company_value=Money(1_000_000), reputation=0.9)[0]
    assert terms.bank_name in terms.describe()


def test_unknown_bank_is_rejected():
    _, _, banking, _ = build_banking()
    with pytest.raises(KeyError):
        banking.terms_for("bank-999999", company_value=Money(1), reputation=1.0)


# -- market integration (V4.6, V7.9) --------------------------------------


def build_market_with_economy(seed: int = 30):
    world, _, _ = generate_world(seed)
    economy = EconomySystem()
    market = MarketSystem(world, economy=economy)
    market.populate(Random(seed))
    clock = SimulationClock(
        seconds_per_day=1.0, speed=1, speed_options=(1,), max_days_per_update=10_000
    )
    engine = SimulationEngine(clock=clock, seed=seed)
    economy.register(engine)
    market.register(engine)
    return economy, market, engine


def test_economic_conditions_are_a_distinct_price_cause():
    economy, market, engine = build_market_with_economy()
    economy.health = 0.9
    engine.run_days(1)
    listing = next(iter(market.listings.values()))
    assert not listing.last_change.economy.is_zero
    # The total still equals the sum of its causes.
    change = listing.last_change
    parts = (
        change.performance.fraction + change.industry.fraction + change.economy.fraction
        + change.sentiment.fraction + change.supply_demand.fraction + change.variation.fraction
    )
    assert change.total.fraction == pytest.approx(parts, abs=1e-9)


def test_market_mood_follows_the_economy():
    # V7.9: the economy changes investment confidence.
    economy, market, engine = build_market_with_economy(seed=31)
    economy.health = 0.9
    for _ in range(300):
        economy.health = 0.9  # hold conditions steady
        engine.run_days(1)
    assert market.sentiment > 0.2


def test_industries_diverge_according_to_the_economy():
    # V7.6: a downturn hurts cyclical industries far more than defensive ones.
    economy, market, engine = build_market_with_economy(seed=32)
    for _ in range(150):
        economy.health = -0.9
        engine.run_days(7)
    assert market.industry_trends[Industry.CONSTRUCTION] < market.industry_trends[
        Industry.HEALTHCARE
    ]


def test_market_still_runs_without_an_economy():
    # The market must remain independently testable (V15.7).
    world, _, _ = generate_world(33)
    market = MarketSystem(world)
    market.populate(Random(33))
    clock = SimulationClock(
        seconds_per_day=1.0, speed=1, speed_options=(1,), max_days_per_update=10_000
    )
    engine = SimulationEngine(clock=clock, seed=33)
    market.register(engine)
    engine.run_days(30)
    assert all(listing.last_change.economy.is_zero for listing in market.listings.values())


# -- persistence (V15.11, V16.11) -----------------------------------------


def test_state_round_trip_restores_the_economy():
    economy, engine = build(seed=44)
    engine.run_days(500)
    saved = economy.state_data()

    restored = EconomySystem()
    restored.restore(saved)
    assert restored.health == economy.health
    assert restored.state is economy.state
    assert restored.annual_inflation == economy.annual_inflation
    assert restored.price_level == economy.price_level
    assert len(restored.transitions) == len(economy.transitions)


def test_restore_tolerates_minimal_state():
    economy = EconomySystem()
    economy.restore({})
    assert economy.state is EconomicState.STABLE


def test_banking_state_round_trip():
    _, _, banking, _ = build_banking()
    restored = BankingSystem(banking.world, banking.economy)
    restored.restore(banking.state_data())
    assert {b: p.tier for b, p in restored.profiles.items()} == {
        b: p.tier for b, p in banking.profiles.items()
    }


def test_same_seed_reproduces_the_same_economy():
    def sample(seed: int) -> list[float]:
        economy, engine = build(seed)
        values = []
        for _ in range(50):
            engine.run_days(7)
            values.append(economy.health)
        return values

    assert sample(77) == sample(77)
    assert sample(77) != sample(78)


def test_description_is_human_readable():
    economy, engine = build()
    engine.run_days(10)
    text = economy.describe()
    assert str(economy.state) in text
    assert "inflation" in text
