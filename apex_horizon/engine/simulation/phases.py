"""The daily simulation phases.

Design Bible Volume 29 defines the exact order in which systems process each
in-game day, and V29.13 explains why: every system must read only fully-settled
data from the systems before it, never partially-computed data from later ones.
News (step 1) therefore reports on yesterday's settled outcomes, the Market
(step 8) reflects the full day's investment activity, and the User Interface
(step 10) always renders a fully consistent snapshot.

V29.15 requires each step to be a distinct phase that completes fully before the
next begins, rather than allowing systems to interleave in an order that could
vary between runs — this is what preserves the Deterministic Simulation
guarantee of V15.11.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - type-checking imports only
    from random import Random

    from ..values import SimulationDate


class SimulationPhase(Enum):
    """The ten daily steps of V29.2, in their defined execution order."""

    NEWS = 1
    ECONOMY = 2
    BANKS = 3
    COMPANIES = 4
    EMPLOYEES = 5
    RESEARCH = 6
    INVESTMENT_FUNDS = 7
    MARKET = 8
    FINANCIAL_CALCULATIONS = 9
    USER_INTERFACE = 10

    @property
    def order(self) -> int:
        return self.value


# The canonical execution order, derived from the phase numbering above so the
# two can never drift apart.
PHASE_ORDER: tuple[SimulationPhase, ...] = tuple(
    sorted(SimulationPhase, key=lambda phase: phase.order)
)


class PeriodBoundary(Enum):
    """Scheduled progression points beyond the daily cycle."""

    WEEK = "week"    # V13.9  — weekly profit, loan repayments, weekly statistics
    MONTH = "month"  # V13.10 — salaries, monthly reports, monthly autosave
    YEAR = "year"    # V13.11 — taxes, annual statistics, long-term summaries


@dataclass(frozen=True)
class SimulationContext:
    """Everything a phase handler needs to process one in-game day.

    Handlers receive the context rather than reaching back into the engine, so a
    system never depends on engine internals and stays independently testable
    (V15.7).
    """

    date: SimulationDate
    rng: Random
    day_number: int
    tick: int

    def __str__(self) -> str:
        return f"day {self.day_number} ({self.date.label()})"


# A phase handler processes one day and returns nothing; systems mutate their own
# state and communicate through the engine's event hooks (V15.6).
PhaseHandler = Callable[[SimulationContext], None]
BoundaryHandler = Callable[[SimulationContext], None]
