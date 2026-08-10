"""Helpers shared by the market tests."""

from __future__ import annotations

from random import Random

from apex_horizon.engine.market import MarketSystem
from apex_horizon.engine.simulation import SimulationClock, SimulationEngine
from apex_horizon.engine.world import generate_world


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
