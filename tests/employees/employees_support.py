"""Helpers shared by the Employee System tests."""

from __future__ import annotations

from apex_horizon.engine.simulation import SimulationClock, SimulationEngine


def make_engine(seed: int = 1) -> SimulationEngine:
    clock = SimulationClock(seconds_per_day=1.0, speed=1, speed_options=(1,),
                            max_days_per_update=100_000)
    return SimulationEngine(clock=clock, seed=seed)
