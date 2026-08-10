"""Helpers shared by the company and finance tests."""

from __future__ import annotations

from apex_horizon.engine.company import InvestmentCompany, Player
from apex_horizon.engine.simulation import SimulationClock, SimulationEngine
from apex_horizon.engine.unlocks import CREATE_COMPANY
from apex_horizon.engine.values import Money


def make_engine(seed: int = 1) -> SimulationEngine:
    clock = SimulationClock(
        seconds_per_day=1.0, speed=1, speed_options=(1,), max_days_per_update=100_000
    )
    return SimulationEngine(clock=clock, seed=seed)


def founded_player(cash: int = 100_000) -> tuple[Player, InvestmentCompany]:
    player = Player("Test Owner", cash=Money(cash))
    player.unlocks.unlock(CREATE_COMPANY)
    company, _ = player.found_company("Test Capital", day=1)
    assert company is not None, "the builder must produce a company"
    # Borrowing is opened by the Finance branch (V6.7.1); these tests are about
    # what loans do, not about earning them.
    company.borrowing_allowed = True
    return player, company
